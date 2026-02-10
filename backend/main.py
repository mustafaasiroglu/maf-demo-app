from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
import os
from dotenv import load_dotenv
from typing import List, Dict, Any
import asyncio
import json
from datetime import datetime
from agent.investment_agent import InvestmentAgent
from agent_framework import AgentThread
from models.user import DUMMY_USER
from tools.pii import analyze_text_with_details as pii_analyze_detailed, unmask_response as pii_unmask, set_pii_replacements

# Load environment variables
load_dotenv()

app = FastAPI(title="Investment Bot API", version="1.0.0")

# Configure CORS
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared agent instance (stateless, thread carries state)
agent = InvestmentAgent()

# In-memory session store: session_id -> AgentThread
sessions: Dict[str, AgentThread] = {}

# Per-session PII masking state (stores pii_masking_enabled flag)
session_pii_enabled: Dict[str, bool] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    pii_masking_enabled: bool = False

class ChatResponse(BaseModel):
    response: str
    debug: Dict[str, Any] = {}

@app.get("/api/health")
async def health():
    return {"message": "Investment Bot API", "status": "running"}

@app.get("/user/me")
async def get_current_user():
    """Get current logged-in user information."""
    return DUMMY_USER.to_dict()

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint using SSE.
    Returns structured events: {type: "message"|"tool_call"|"error"|"done", data: {...}, debug: {...}}
    """
    session_id = request.session_id
    user_message = request.message
    pii_masking_enabled = request.pii_masking_enabled
    
    # Store PII masking preference for the session
    session_pii_enabled[session_id] = pii_masking_enabled
    
    # Get or create AgentThread for this session
    if session_id not in sessions:
        sessions[session_id] = agent.get_new_thread()
    
    # Apply PII masking if enabled
    pii_replacements: list = []
    pii_debug_info: dict = {}
    message_for_llm = user_message
    if pii_masking_enabled:
        pii_result = pii_analyze_detailed(user_message)
        message_for_llm = pii_result["masked_text"]
        pii_replacements = pii_result["replacements"]
        pii_debug_info = {
            "pii_enabled": True,
            "pii_status": pii_result["status"],
            "pii_detail": pii_result["detail"],
            "pii_http_status": pii_result["http_status"],
            "pii_entities_found": pii_result["entities_found"],
            "pii_duration_ms": pii_result["duration_ms"],
            "pii_masked_message": message_for_llm,
            "pii_redactions": [
                {"original": orig, "mask": mask} for orig, mask in pii_replacements
            ],
            "pii_request_input": pii_result["request_body"],
            "pii_request_output": pii_result["response_body"],
            "pii_timeline_event": {
                "order": 0,
                "event_type": "pii_masking",
                "label": "PII Masking",
                "start_ms": 0,
                "duration_ms": pii_result["duration_ms"],
                "timestamp": datetime.now().isoformat(),
            },
        }
    
    # Thread carries conversation history; no manual append needed
    thread = sessions[session_id]
    
    async def event_generator():
        try:
            # Emit PII debug event first if masking is enabled
            if pii_masking_enabled:
                yield {
                    "event": "pii_result",
                    "data": json.dumps({
                        "type": "pii_result",
                        "data": pii_debug_info
                    })
                }
            
            # Stream agent response (send masked message to LLM)
            # Set PII replacements so tool functions can unmask their parameters
            set_pii_replacements(pii_replacements)
            async for event in agent.stream_response(message_for_llm, thread):
                # Unmask PII in response content before sending to client
                if pii_masking_enabled and pii_replacements:
                    if event.get("type") == "message" and "data" in event:
                        event["data"]["content"] = pii_unmask(event["data"]["content"], pii_replacements)
                    elif event.get("type") == "message_chunk" and "data" in event:
                        event["data"]["content"] = pii_unmask(event["data"]["content"], pii_replacements)
                
                # Attach PII debug info to the final message event
                if pii_masking_enabled and event.get("type") == "message":
                    if "debug" not in event:
                        event["debug"] = {}
                    event["debug"].update(pii_debug_info)
                    # Inject PII as the first timeline event (order 0)
                    if "pii_timeline_event" in pii_debug_info:
                        timeline = event["debug"].get("timeline_events", [])
                        # Shift all agent timeline start_ms by PII duration (agent timer starts after PII)
                        pii_ms = pii_debug_info.get("pii_duration_ms", 0)
                        for te in timeline:
                            if "start_ms" in te:
                                te["start_ms"] = round(te["start_ms"] + pii_ms, 2)
                        timeline.insert(0, pii_debug_info["pii_timeline_event"])
                        event["debug"]["timeline_events"] = timeline
                    # Include PII duration in total request duration
                    pii_ms = pii_debug_info.get("pii_duration_ms", 0)
                    if "total_request_time_ms" in event["debug"]:
                        event["debug"]["total_request_time_ms"] = round(event["debug"]["total_request_time_ms"] + pii_ms, 2)
                
                # Use the event type as SSE event name
                event_type = event.get("type", "message")
                yield {
                    "event": event_type,
                    "data": json.dumps(event)
                }
            
            # Send done event
            yield {
                "event": "done",
                "data": json.dumps({"type": "done"})
            }
            
        except Exception as e:
            # Send error event
            error_event = {
                "type": "error",
                "data": {"error": str(e)},
                "debug": {"error_type": type(e).__name__}
            }
            yield {
                "event": "error",
                "data": json.dumps(error_event)
            }
    
    return EventSourceResponse(event_generator())

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Non-streaming chat endpoint for testing.
    """
    session_id = request.session_id
    user_message = request.message
    pii_masking_enabled = request.pii_masking_enabled
    
    # Get or create AgentThread for this session
    if session_id not in sessions:
        sessions[session_id] = agent.get_new_thread()
    
    # Apply PII masking if enabled
    pii_replacements: list = []
    message_for_llm = user_message
    if pii_masking_enabled:
        pii_result = pii_analyze_detailed(user_message)
        message_for_llm = pii_result["masked_text"]
        pii_replacements = pii_result["replacements"]
    
    thread = sessions[session_id]
    
    try:
        # Set PII replacements so tool functions can unmask their parameters
        set_pii_replacements(pii_replacements)
        response = await agent.get_response(message_for_llm, thread)
        
        # Unmask PII in response before returning to client
        response_content = response["data"]["content"]
        if pii_masking_enabled and pii_replacements:
            response_content = pii_unmask(response_content, pii_replacements)
        
        return ChatResponse(response=response_content, debug=response.get("debug", {}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    if session_id in sessions:
        del sessions[session_id]
        return {"message": f"Session {session_id} cleared"}
    return {"message": "Session not found"}

# Serve static files from Next.js build (for production)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    # Serve static assets
    app.mount("/_next", StaticFiles(directory=os.path.join(static_dir, "_next")), name="next-static")
    
    # Catch-all route for SPA - must be last
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the Next.js static export."""
        # Try to serve the exact file
        file_path = os.path.join(static_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # Try with .html extension
        html_path = os.path.join(static_dir, full_path, "index.html")
        if os.path.isfile(html_path):
            return FileResponse(html_path)
        
        # Fallback to index.html for SPA routing
        index_path = os.path.join(static_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        
        raise HTTPException(status_code=404, detail="Not found")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", 8000))
    uvicorn.run(app, host=host, port=port)
