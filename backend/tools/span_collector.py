"""
In-memory OpenTelemetry span collector for Agent Framework.

Captures spans emitted by agent_framework (LLM calls, tool executions, agent invocations)
and converts them into timeline events for the debug panel.

Agent Framework emits spans following OTel GenAI semantic conventions:
  - "chat <model>"          → LLM call  (gen_ai.operation.name = "chat")
  - "execute_tool <name>"   → Tool call (gen_ai.operation.name = "execute_tool")
  - "invoke_agent <name>"   → Agent run (gen_ai.operation.name = "invoke_agent")
"""

import threading
import time
import json
import asyncio
import logging
from datetime import datetime
from typing import Sequence, List, Dict, Any, Optional, Callable

from opentelemetry import trace, context as otel_context
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan, Span, SpanProcessor
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

logger = logging.getLogger(__name__)

# ── Span start notifier (fires when framework BEGINS a tool/LLM span) ───────

class _SpanStartNotifier(SpanProcessor):
    """SpanProcessor that fires a callback when a span starts.
    
    Used to detect tool execution and LLM calls the moment the framework
    starts them, rather than waiting for buffered stream events.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._on_tool_start: Optional[Callable[[str], None]] = None
        self._on_llm_start: Optional[Callable[[], None]] = None

    def set_on_tool_start(self, callback: Optional[Callable[[str], None]]) -> None:
        """Register a callback for when a tool span starts.
        
        callback receives the tool name as argument.
        """
        with self._lock:
            self._on_tool_start = callback

    def set_on_llm_start(self, callback: Optional[Callable[[], None]]) -> None:
        """Register a callback for when an LLM (chat) span starts."""
        with self._lock:
            self._on_llm_start = callback

    def on_start(self, span: Span, parent_context: Optional[otel_context.Context] = None) -> None:
        attrs = span.attributes or {}
        op = attrs.get("gen_ai.operation.name", "")
        # Fallback: check span name when attributes aren't set at start time.
        # Agent Framework span names follow "<operation> <detail>" pattern:
        #   "chat <model>", "execute_tool <name>", "invoke_agent <name>"
        span_name = getattr(span, 'name', '') or ''

        is_tool = op == "execute_tool" or (not op and span_name.startswith("execute_tool"))
        is_chat = op == "chat" or (not op and span_name.startswith("chat"))

        if is_tool:
            tool_name = attrs.get("gen_ai.tool.name", "")
            if not tool_name and " " in span_name:
                tool_name = span_name.split(" ", 1)[1]
            tool_name = tool_name or "unknown"
            with self._lock:
                cb = self._on_tool_start
            if cb:
                try:
                    cb(tool_name)
                except Exception:
                    pass
        elif is_chat:
            with self._lock:
                cb = self._on_llm_start
            if cb:
                try:
                    cb()
                except Exception:
                    pass

    def on_end(self, span: ReadableSpan) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: Optional[int] = None) -> bool:
        return True


# ── In-memory exporter ──────────────────────────────────────────────────────

class _ListSpanExporter(SpanExporter):
    """Collects finished spans in a thread-safe list."""

    def __init__(self):
        self._lock = threading.Lock()
        self._spans: List[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with self._lock:
            self._spans.extend(spans)
        return SpanExportResult.SUCCESS

    def drain(self) -> List[ReadableSpan]:
        """Return all collected spans and clear the buffer."""
        with self._lock:
            result = list(self._spans)
            self._spans.clear()
        return result

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis: Optional[int] = None):
        pass


# Module-level singletons
_exporter: Optional[_ListSpanExporter] = None
_notifier: Optional[_SpanStartNotifier] = None


def setup_otel() -> None:
    """Initialize OTel with an in-memory exporter + Agent Framework instrumentation.
    
    Must be called once at app startup, BEFORE any agent is created.
    """
    global _exporter, _notifier
    if _exporter is not None:
        return  # already initialized

    _exporter = _ListSpanExporter()
    _notifier = _SpanStartNotifier()
    provider = TracerProvider()
    provider.add_span_processor(_notifier)           # fires on span start
    provider.add_span_processor(SimpleSpanProcessor(_exporter))  # collects finished spans
    trace.set_tracer_provider(provider)

    from agent_framework.observability import enable_instrumentation
    enable_instrumentation(enable_sensitive_data=True)
    logger.info("✅ OTel tracing initialized with in-memory span collector (sensitive_data=True)")


def drain_spans() -> List[ReadableSpan]:
    """Drain all collected spans since last call. Returns empty list if OTel not set up."""
    if _exporter is None:
        return []
    return _exporter.drain()


class ToolStartQueue:
    """Async queue that receives tool start notifications from OTel SpanProcessor.
    
    Usage in investment_agent.py:
        tool_queue = ToolStartQueue()
        with tool_queue:
            async for wf_event in event_stream:
                # Check for early tool notifications
                while (tool_name := tool_queue.try_get()) is not None:
                    yield thinking event for tool_name
                # ... process wf_event normally ...
    """

    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._llm_start_times_ns: List[int] = []

    def __enter__(self):
        self._loop = asyncio.get_event_loop()
        self._llm_start_times_ns = []
        if _notifier:
            _notifier.set_on_tool_start(self._on_tool_start)
            _notifier.set_on_llm_start(self._on_llm_start)
        return self

    def __exit__(self, *args):
        if _notifier:
            _notifier.set_on_tool_start(None)
            _notifier.set_on_llm_start(None)
        self._loop = None

    def _on_tool_start(self, tool_name: str) -> None:
        """Called from OTel SpanProcessor thread when a tool span starts."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._queue.put_nowait, tool_name)

    def _on_llm_start(self) -> None:
        """Called from OTel SpanProcessor thread when a chat LLM span starts."""
        self._llm_start_times_ns.append(time.time_ns())

    @property
    def llm_start_times_ns(self) -> List[int]:
        """Ordered list of nanosecond timestamps for each LLM span start."""
        return self._llm_start_times_ns

    def try_get(self) -> Optional[str]:
        """Non-blocking: return a tool name or None."""
        try:
            return self._queue.get_nowait()
        except asyncio.QueueEmpty:
            return None


# ── Span → Timeline conversion ──────────────────────────────────────────────

def _ns_to_ms(ns: int) -> float:
    """Convert nanoseconds to milliseconds."""
    return ns / 1_000_000


def spans_to_timeline(
    spans: List[ReadableSpan],
    workflow_start_ns: int,
) -> Dict[str, Any]:
    """Convert collected OTel spans into structured timeline data.
    
    Uses a unified approach: all LLM and tool spans are sorted by start_time
    and interleaved into a single timeline. This avoids timing-comparison bugs
    where tool spans might overlap with or be children of LLM spans.
    
    Args:
        spans: List of finished OTel spans from drain_spans().
        workflow_start_ns: time.time_ns() captured right before workflow.run_stream().
    
    Returns:
        Dict with:
          - timeline_events: ordered list of timeline entries, each with
            timestamp_start, timestamp_end, duration_ms, ttft_ms (null for tools)
          - total_llm_time_ms, total_tool_time_ms, total_input_tokens, total_output_tokens
    """
    # Categorize spans
    llm_spans: List[ReadableSpan] = []
    tool_spans: List[ReadableSpan] = []
    agent_spans: List[ReadableSpan] = []

    for span in spans:
        attrs = dict(span.attributes) if span.attributes else {}
        op = attrs.get("gen_ai.operation.name", "")
        if op == "chat":
            llm_spans.append(span)
        elif op == "execute_tool":
            tool_spans.append(span)
        elif op == "invoke_agent":
            agent_spans.append(span)

    # Build a unified list of (start_time, type, span) sorted by start_time
    tagged_spans: List[tuple] = []
    for s in llm_spans:
        tagged_spans.append((s.start_time, "llm", s))
    for s in tool_spans:
        tagged_spans.append((s.start_time, "tool", s))
    tagged_spans.sort(key=lambda x: x[0])

    # Walk through in order to build the timeline
    timeline_events: List[Dict[str, Any]] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_llm_time_ms = 0.0
    total_tool_time_ms = 0.0
    event_order = 0
    llm_index = 0  # sequential LLM counter

    # Pre-compute: set of tool span ids for quick lookup
    tool_span_ids = {id(s) for s in tool_spans}

    for idx, (_, span_type, span) in enumerate(tagged_spans):
        attrs = dict(span.attributes) if span.attributes else {}
        duration_ns = span.end_time - span.start_time
        duration_ms = round(_ns_to_ms(duration_ns), 2)
        start_offset_ms = round(_ns_to_ms(span.start_time - workflow_start_ns), 2)
        end_offset_ms = round(_ns_to_ms(span.end_time - workflow_start_ns), 2)

        if span_type == "llm":
            llm_index += 1
            input_tokens = attrs.get("gen_ai.usage.input_tokens", 0) or 0
            output_tokens = attrs.get("gen_ai.usage.output_tokens", 0) or 0
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            total_llm_time_ms += duration_ms
            model = attrs.get("gen_ai.request.model", "unknown")

            # Determine type: check output messages for handoff tool calls first,
            # then check if any tool span appears next (before the next LLM).
            has_handoff = False
            output_raw = attrs.get("gen_ai.output.messages", "")
            if output_raw:
                try:
                    out_msgs = json.loads(output_raw) if isinstance(output_raw, str) else output_raw
                    if isinstance(out_msgs, list):
                        for msg in out_msgs:
                            for p in msg.get("parts", []):
                                if isinstance(p, dict) and p.get("type") == "tool_call":
                                    if str(p.get("name", "")).startswith("handoff_to_"):
                                        has_handoff = True
                                        break
                            if has_handoff:
                                break
                except Exception:
                    pass

            has_tool_after = False
            for future_idx in range(idx + 1, len(tagged_spans)):
                future_type = tagged_spans[future_idx][1]
                if future_type == "tool":
                    has_tool_after = True
                    break
                if future_type == "llm":
                    break  # next LLM found before any tool

            if has_handoff:
                llm_type = "handoff"
            elif has_tool_after:
                llm_type = "tool_decision"
            else:
                llm_type = "final_response"

            # Build request_output
            request_output: Dict[str, Any] = {
                "decision": llm_type,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }

            # Extract LLM response content from output messages
            response_content = _extract_messages_text(attrs, "gen_ai.output.messages")
            if response_content:
                request_output["response"] = response_content

            # Add finish_reasons if available
            finish_reasons = _parse_json_attr(attrs, "gen_ai.response.finish_reasons")
            if finish_reasons:
                request_output["finish_reasons"] = finish_reasons

            # For tool_decision, gather detail about which tools were called
            if llm_type == "tool_decision":
                tool_calls_detail = []
                for future_idx in range(idx + 1, len(tagged_spans)):
                    future_type = tagged_spans[future_idx][1]
                    if future_type == "llm":
                        break
                    if future_type == "tool":
                        t_span = tagged_spans[future_idx][2]
                        t_attrs = dict(t_span.attributes) if t_span.attributes else {}
                        tool_name = t_attrs.get("gen_ai.tool.name", "unknown")
                        tool_args = _parse_json_attr(t_attrs, "gen_ai.tool.call.arguments")
                        tool_calls_detail.append({"name": tool_name, "arguments": tool_args})
                if tool_calls_detail:
                    request_output["tool_calls"] = tool_calls_detail

            event_order += 1
            # Build request_input with model + input messages
            request_input: Dict[str, Any] = {"model": model}
            input_content = _extract_messages_text(attrs, "gen_ai.input.messages")
            if input_content:
                # Truncate very long input (system prompt + history can be huge)
                if len(input_content) > 2000:
                    request_input["messages"] = input_content[:2000] + "\n... [truncated]"
                else:
                    request_input["messages"] = input_content

            timeline_events.append({
                "order": event_order,
                "request_number": llm_index,
                "agent_id": _get_agent_id(span, agent_spans),
                "event_type": "llm_request",
                "label": f"LLM ({llm_type})",
                "timestamp_start": start_offset_ms,
                "timestamp_end": end_offset_ms,
                "duration_ms": duration_ms,
                "ttft_ms": None,
                "request_input": request_input,
                "request_output": request_output,
            })

        elif span_type == "tool":
            tool_name = attrs.get("gen_ai.tool.name", "unknown")
            total_tool_time_ms += duration_ms

            tool_args = _parse_json_attr(attrs, "gen_ai.tool.call.arguments")
            tool_result = _parse_json_attr(attrs, "gen_ai.tool.call.result")
            if isinstance(tool_result, dict) and 'data' in tool_result:
                tool_result = tool_result['data']

            event_order += 1
            timeline_events.append({
                "order": event_order,
                "agent_id": _get_agent_id(span, agent_spans),
                "event_type": "tool_call",
                "label": f"Tool ({tool_name})",
                "timestamp_start": start_offset_ms,
                "timestamp_end": end_offset_ms,
                "duration_ms": duration_ms,
                "ttft_ms": None,
                "request_input": {
                    "tool_name": tool_name,
                    "arguments": tool_args,
                },
                "request_output": tool_result,
            })

    return {
        "timeline_events": timeline_events,
        "total_llm_requests": len(llm_spans),
        "total_llm_time_ms": round(total_llm_time_ms, 2),
        "total_tool_time_ms": round(total_tool_time_ms, 2),
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
    }


def _parse_json_attr(attrs: Dict[str, Any], key: str) -> Any:
    """Safely parse a JSON string attribute, returning {} on failure."""
    raw = attrs.get(key, "")
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return {"raw": str(raw)[:3000]}


def _extract_messages_text(attrs: Dict[str, Any], attr_key: str) -> Optional[str]:
    """Extract text content from gen_ai.input.messages / gen_ai.output.messages.
    
    OTel message format: [{"role": "...", "parts": [{"type": "text", "content": "..."}]}]
    Returns a compact text summary or None if not available.
    """
    raw = attrs.get(attr_key, "")
    if not raw:
        return None
    try:
        messages = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(messages, list):
            return None
        parts_text = []
        for msg in messages:
            role = msg.get("role", "unknown")
            parts = msg.get("parts", [])
            texts = []
            for p in parts:
                if isinstance(p, dict):
                    if p.get("type") == "text" and p.get("content"):
                        texts.append(p["content"])
                    elif p.get("type") == "tool_call":
                        name = p.get("name", "?")
                        texts.append(f"[tool_call: {name}]")
                    elif p.get("type") == "tool_result":
                        texts.append("[tool_result]")
                    elif p.get("type") == "reasoning" and p.get("content"):
                        texts.append(f"[reasoning: {p['content'][:200]}]")
            if texts:
                parts_text.append(f"{role}: {' | '.join(texts)}")
        return "\n".join(parts_text) if parts_text else None
    except Exception:
        return None


def _get_agent_id(span: ReadableSpan, agent_spans: List[ReadableSpan]) -> str:
    """Find which agent a span belongs to based on parent/time overlap with agent spans."""
    # Try to find enclosing agent span by time overlap
    for a_span in agent_spans:
        if a_span.start_time <= span.start_time and span.end_time <= a_span.end_time:
            attrs = dict(a_span.attributes) if a_span.attributes else {}
            return attrs.get("gen_ai.agent.name", "unknown")
    return "unknown"
