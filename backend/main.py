import os
from dotenv import load_dotenv

# Load environment variables BEFORE any application imports
# (modules like tools.pii read env vars at import time)
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from typing import List, Dict, Any
import asyncio
import json
from datetime import datetime
from agent.investment_agent import InvestmentAgent
from agent_framework import Workflow
from models.user import DUMMY_USER
from tools.pii import analyze_text_with_details as pii_analyze_detailed, unmask_response as pii_unmask, set_pii_replacements
from tools.span_collector import setup_otel

# Initialize OTel tracing BEFORE creating agents (must be first)
setup_otel()

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

# In-memory session store: session_id -> {"workflow": Workflow, "pending_request_id": str | None}
sessions: Dict[str, dict] = {}

# Per-session PII masking state (stores pii_masking_enabled flag)
session_pii_enabled: Dict[str, bool] = {}

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    pii_masking_enabled: bool = False
    model: str = ""
    language: str = "tr"

class ChatResponse(BaseModel):
    response: str
    debug: Dict[str, Any] = {}

@app.get("/api/health")
async def health():
    return {"message": "Investment Bot API", "status": "running"}


class PriceHistoryRequest(BaseModel):
    fund_code: str | None = None
    fund_codes: list[str] | None = None
    start_date: str
    end_date: str | None = None


# ── Currency pair helpers for pricehistory endpoint ──────────────────────────

def _is_currency_pair(code: str) -> bool:
    """Return True for 6-letter codes ending with TRY (e.g. USDTRY, EURTRY)."""
    return len(code) == 6 and code.endswith("TRY") and code[:3] != "TRY"


def _fetch_currency_as_fund_series(
    pair_code: str, start_date: str, end_date: str | None
) -> dict:
    """Call get_exchange_rate with a date range and reshape the result to
    match the FundSeries dict the chart frontend expects."""
    from tools.currency import get_exchange_rate

    currency_code = pair_code[:3]  # e.g. "USD" from "USDTRY"
    result = get_exchange_rate(currency_code, date_start=start_date, date_end=end_date)

    if result.get("status") != "success":
        return {
            "found": False,
            "fund_code": pair_code,
            "message": result.get("message", "Veri bulunamadı."),
        }

    data = result["data"]

    # Historical range result (has "history" list)
    if "history" not in data:
        return {
            "found": False,
            "fund_code": pair_code,
            "message": f"{pair_code} grafiği için tarih aralığı gerekli.",
        }

    prices = []
    for point in data["history"]:
        # Convert YYYY-MM-DD → DD.MM.YYYY to match TEFAS format
        parts = point["date"].split("-")
        tarih = f"{parts[2]}.{parts[1]}.{parts[0]}"
        prices.append({"tarih": tarih, "fiyat": point["buy_rate"]})

    if not prices:
        return {
            "found": False,
            "fund_code": pair_code,
            "message": f"{pair_code} için belirtilen aralıkta veri bulunamadı.",
        }

    fiyatlar = [p["fiyat"] for p in prices if p["fiyat"] is not None]
    first_price = fiyatlar[0] if fiyatlar else None
    last_price = fiyatlar[-1] if fiyatlar else None
    change_pct = (
        round((last_price - first_price) / first_price * 100, 2)
        if first_price and last_price and first_price != 0
        else None
    )

    # Reformat date strings to DD.MM.YYYY
    ds = data.get("date_start", start_date)
    de = data.get("date_end", end_date or "")
    for field, val in [("ds", ds), ("de", de)]:
        if "-" in val:
            p = val.split("-")
            if field == "ds":
                ds = f"{p[2]}.{p[1]}.{p[0]}"
            else:
                de = f"{p[2]}.{p[1]}.{p[0]}"

    return {
        "found": True,
        "fund_code": pair_code,
        "start_date": ds,
        "end_date": de,
        "total_days": data.get("total_days", 0),
        "record_count": len(prices),
        "summary": {
            "first_price": first_price,
            "last_price": last_price,
            "min_price": min(fiyatlar) if fiyatlar else None,
            "max_price": max(fiyatlar) if fiyatlar else None,
            "change_percent": change_pct,
        },
        "prices": prices,
    }


@app.post("/api/pricehistory")
async def price_history(request: PriceHistoryRequest):
    """
    Get historical fund prices from TEFAS or currency rates from TCMB.
    Accepts fund_code (single) or fund_codes (list, max 3) with start_date and optional end_date.
    Six-letter codes ending with TRY (e.g. USDTRY, EURTRY) are treated as currency pairs
    and fetched via the TCMB currency tool instead of TEFAS.
    """
    from tools.fund_price_history import get_fund_price_history

    # Resolve fund codes list (support both single and multi)
    codes: list[str] = []
    if request.fund_codes:
        codes = [c.strip().upper() for c in request.fund_codes if c.strip()]
    elif request.fund_code:
        codes = [c.strip().upper() for c in request.fund_code.split(",") if c.strip()]

    if not codes:
        raise HTTPException(status_code=400, detail="fund_code veya fund_codes gerekli.")
    if len(codes) > 3:
        raise HTTPException(status_code=400, detail="En fazla 3 fon/döviz karşılaştırılabilir.")

    results = []
    for code in codes:
        if _is_currency_pair(code):
            result = _fetch_currency_as_fund_series(code, request.start_date, request.end_date)
        else:
            raw = get_fund_price_history(
                fund_code=code,
                start_date=request.start_date,
                end_date=request.end_date,
            )
            result = raw.get("data", {})
        results.append(result)

    # If any fund has data, return success
    found_any = any(r.get("found", False) for r in results)
    if not found_any:
        raise HTTPException(status_code=404, detail="Seçilen fonlar/kurlar için veri bulunamadı.")

    # Single fund: return flat (backward compatible)
    if len(results) == 1:
        return results[0]

    # Multiple funds: return as list
    return {"funds": results}


class DistributionHistoryRequest(BaseModel):
    fund_code: str
    start_date: str
    end_date: str | None = None
    include_history: bool = False


@app.post("/api/distributionhistory")
async def distribution_history(request: DistributionHistoryRequest):
    """
    Get fund asset-allocation (distribution) data from TEFAS.
    By default returns only the latest date. Set include_history=true for all dates.
    """
    from tools.fund_distribution_history import get_distribution_history

    code = request.fund_code.strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="fund_code gerekli.")

    result = get_distribution_history(
        fund_code=code,
        start_date=request.start_date,
        end_date=request.end_date,
        include_history=request.include_history,
    )
    data = result.get("data", {})
    if not data.get("found", False):
        raise HTTPException(status_code=404, detail=data.get("message", "Veri bulunamadı."))

    return data


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
    import logging as _logging
    _log = _logging.getLogger("chat_stream")

    session_id = request.session_id
    user_message = request.message
    pii_masking_enabled = request.pii_masking_enabled
    requested_model = request.model or None  # None means use default
    language = request.language if request.language in ("tr", "en") else "tr"
    
    # Store PII masking preference for the session
    session_pii_enabled[session_id] = pii_masking_enabled
    
    # Get or create Workflow for this session
    # Recreate if the model changed since last request
    is_followup = False
    pending_request_id = None
    # Normalize model: treat None/empty as the default deployment
    # so that requests missing the model field don't trigger a false
    # workflow recreation (which would wipe conversation history).
    effective_model = requested_model or agent.deployment
    if session_id not in sessions:
        _log.info(f"📌 New session {session_id}, creating workflow (model={effective_model}, lang={language})")
        sessions[session_id] = {
            "workflow": agent.create_new_workflow(model=effective_model, language=language),
            "pending_request_id": None,
            "model": effective_model,
            "language": language,
        }
    else:
        prev_model = sessions[session_id].get("model") or agent.deployment
        prev_lang = sessions[session_id].get("language", "tr")
        if effective_model != prev_model or language != prev_lang:
            # Model or language changed — create a fresh workflow
            _log.info(f"🔄 Config changed (model={prev_model}→{effective_model}, lang={prev_lang}→{language}), recreating workflow for session {session_id}")
            sessions[session_id] = {
                "workflow": agent.create_new_workflow(model=effective_model, language=language),
                "pending_request_id": None,
                "model": effective_model,
                "language": language,
            }
        else:
            pending_request_id = sessions[session_id].get("pending_request_id")
            if pending_request_id:
                is_followup = True
    
    _log.info(
        f"📨 session={session_id} is_followup={is_followup} "
        f"pending_request_id={pending_request_id} model={effective_model}"
    )
    
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
                "timestamp_start": 0,
                "timestamp_end": pii_result["duration_ms"],
                "duration_ms": pii_result["duration_ms"],
                "timestamp": datetime.now().isoformat(),
                "request_input": pii_result["request_body"],
                "request_output": pii_result["response_body"],
            },
        }
    
    workflow = sessions[session_id]["workflow"]
    
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
            async for event in agent.stream_response(message_for_llm, workflow, is_followup, pending_request_id, model=requested_model, language=language):
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
                        # Shift all agent timeline timestamps by PII duration (agent timer starts after PII)
                        pii_ms = pii_debug_info.get("pii_duration_ms", 0)
                        for te in timeline:
                            if "timestamp_start" in te:
                                te["timestamp_start"] = round(te["timestamp_start"] + pii_ms, 2)
                            if "timestamp_end" in te:
                                te["timestamp_end"] = round(te["timestamp_end"] + pii_ms, 2)
                        timeline.insert(0, pii_debug_info["pii_timeline_event"])
                        event["debug"]["timeline_events"] = timeline
                    # Include PII duration in total request duration
                    pii_ms = pii_debug_info.get("pii_duration_ms", 0)
                    if "total_request_time_ms" in event["debug"]:
                        event["debug"]["total_request_time_ms"] = round(event["debug"]["total_request_time_ms"] + pii_ms, 2)
                
                # Track pending_request_id from the final message event
                if event.get("type") == "message" and "debug" in event:
                    new_pending = event["debug"].get("pending_request_id")
                    sessions[session_id]["pending_request_id"] = new_pending
                
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
            import logging as _logging
            _logging.getLogger(__name__).error(f"SSE event_generator error: {e}", exc_info=True)
            # Reset pending_request_id so the next request uses run_stream
            # instead of retrying with a stale/invalid request_id forever.
            if session_id in sessions:
                sessions[session_id]["pending_request_id"] = None
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
    
    # Get or create Workflow for this session
    is_followup = False
    pending_request_id = None
    if session_id not in sessions:
        sessions[session_id] = {"workflow": agent.create_new_workflow(), "pending_request_id": None}
    else:
        pending_request_id = sessions[session_id].get("pending_request_id")
        if pending_request_id:
            is_followup = True
    
    # Apply PII masking if enabled
    pii_replacements: list = []
    message_for_llm = user_message
    if pii_masking_enabled:
        pii_result = pii_analyze_detailed(user_message)
        message_for_llm = pii_result["masked_text"]
        pii_replacements = pii_result["replacements"]
    
    workflow = sessions[session_id]["workflow"]
    
    try:
        # Set PII replacements so tool functions can unmask their parameters
        set_pii_replacements(pii_replacements)
        response = await agent.get_response(message_for_llm, workflow, is_followup, pending_request_id)
        
        # Store pending_request_id for follow-up messages
        if "debug" in response:
            sessions[session_id]["pending_request_id"] = response["debug"].get("pending_request_id")
        
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
