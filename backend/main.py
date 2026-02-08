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
from agent.investment_agent import InvestmentAgent
from models.user import DUMMY_USER

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

# In-memory session store for conversation history
sessions: Dict[str, List[Dict[str, str]]] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

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
    
    # Initialize session history if not exists
    if session_id not in sessions:
        sessions[session_id] = []
    
    # Add user message to history
    sessions[session_id].append({"role": "user", "content": user_message})
    
    async def event_generator():
        try:
            # Initialize agent
            agent = InvestmentAgent()
            
            # Stream agent response
            async for event in agent.stream_response(user_message, sessions[session_id]):
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
    
    # Initialize session history if not exists
    if session_id not in sessions:
        sessions[session_id] = []
    
    # Add user message to history
    sessions[session_id].append({"role": "user", "content": user_message})
    
    try:
        agent = InvestmentAgent()
        response = await agent.get_response(user_message, sessions[session_id])
        
        # Add assistant response to history
        sessions[session_id].append({"role": "assistant", "content": response["data"]["content"]})
        
        return ChatResponse(response=response["data"]["content"], debug=response.get("debug", {}))
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
