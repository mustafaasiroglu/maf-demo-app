import traceback
from typing import Dict, List, Any, AsyncGenerator, Annotated, Optional, Sequence
from datetime import datetime
import time
import os
import json
import logging
import asyncio
from pydantic import Field
from agent_framework import (
    ChatAgent, ChatMessage, ChatMessageStore, AgentThread,
    HandoffBuilder, HandoffSentEvent, HandoffAgentUserRequest,
    AgentRunUpdateEvent, AgentRunEvent, RequestInfoEvent,
    WorkflowStatusEvent, WorkflowRunState, WorkflowEvent, Workflow,
)
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from tools.pii import pii_unmask_args
from tools.span_collector import drain_spans, spans_to_timeline, ToolStartQueue
from agent import ReducingChatMessageStore
from agent.currency_agent import create_currency_agent
from agent.customer_info_agent import create_customer_info_agent
from i18n import (
    Language, get_tool_message, get_default_tool_message, get_message,
    get_investment_system_prompt,
)

# Configure logging (use INFO level in production for better performance)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Tool functions with proper annotations for Microsoft Agent Framework
@pii_unmask_args
def search_funds(
    search_query: Annotated[str, Field(description="Free-text query to search for funds (e.g., 'altın', 'teknoloji', 'likit', 'GTA')")],
) -> str:
    """Search for investment funds by keyword or fund code. Returns basic details (name, code, price, strategy) for each matching fund. Use this to discover funds before getting full details."""
    time.sleep(1)
    from tools.fund_knowledge import search_funds as _search_funds
    result = _search_funds(search_query)
    return json.dumps(result, ensure_ascii=False)


@pii_unmask_args
def get_fund_details(
    fund_code: Annotated[str, Field(description="The fund code to get full details for (e.g., 'GTA', 'GOL', 'GTL')")],
) -> str:
    """Get all details for a specific investment fund by its fund code, including risk level, returns, holdings, fees, and trading rules. Use this after identifying the fund via search_funds or when the user asks about a specific fund code."""
    time.sleep(1)
    from tools.fund_knowledge import get_fund_details as _get_fund_details
    result = _get_fund_details(fund_code)
    return json.dumps(result, ensure_ascii=False)


@pii_unmask_args
def compare_funds(
    fund_codes: Annotated[List[str], Field(description="List of fund codes to compare (e.g., ['GTA', 'GOL', 'GTL'])")],
    metric: Annotated[str, Field(description="Metric to compare (e.g., 'returns', 'risk', 'fees')")] = "returns"
) -> str:
    """Compare multiple investment funds based on specific metrics like returns, risk levels, or fees."""
    from tools.fund_knowledge import compare_funds as _compare_funds
    result = _compare_funds(fund_codes, metric)
    return json.dumps(result, ensure_ascii=False)


def get_recommended_funds() -> str:
    """Get the list of recommended (önerilen) investment funds. Use this when the user asks for recommended funds, suggested funds, or 'önerilen fonlar'."""
    from tools.fund_knowledge import get_recommended_funds as _get_recommended_funds
    result = _get_recommended_funds()
    return json.dumps(result, ensure_ascii=False)


@pii_unmask_args
def get_fund_price_history(
    fund_code: Annotated[str, Field(description="The fund code to get price history for (e.g., 'GTA', 'GOL', 'GTL')")],
    start_date: Annotated[str, Field(description="Start date in DD.MM.YYYY or YYYY-MM-DD format (e.g., '01.01.2026')")],
    end_date: Annotated[Optional[str], Field(description="End date in DD.MM.YYYY or YYYY-MM-DD format. Defaults to today if not provided.")] = None,
) -> str:
    """Get historical price data for a fund from TEFAS (Türkiye Elektronik Fon Alım Satım Platformu). Returns daily prices, portfolio size, and investor count. Automatically handles date ranges longer than 60 days by splitting into multiple queries."""
    from tools.fund_price_history import get_fund_price_history as _get_fund_price_history
    result = _get_fund_price_history(fund_code, start_date, end_date)
    return json.dumps(result, ensure_ascii=False)


# @pii_unmask_args
# def get_distribution_history(
#     fund_code: Annotated[str, Field(description="The fund code to get distribution/allocation for (e.g., 'GTZ', 'GTA', 'GOL')")],
#     start_date: Annotated[str, Field(description="Start date in DD.MM.YYYY or YYYY-MM-DD format (e.g., '01.01.2026')")],
#     end_date: Annotated[Optional[str], Field(description="End date in DD.MM.YYYY or YYYY-MM-DD format. Defaults to today if not provided.")] = None,
#     include_history: Annotated[bool, Field(description="If true, return allocation data for all dates in the range. If false (default), return only the latest date's snapshot.")] = False,
# ) -> str:
#     """Get asset-allocation (distribution) history for a fund from TEFAS. Shows the percentage breakdown of the fund's portfolio across asset classes (stocks, bonds, gold, FX, etc.). By default returns only the latest snapshot. Set include_history=true for the full time series. Use only when the user asks about fund composition, allocation, distribution history."""
#     from tools.fund_distribution_history import get_distribution_history as _get_distribution_history
#     result = _get_distribution_history(fund_code, start_date, end_date, include_history)
#     return json.dumps(result, ensure_ascii=False)


@pii_unmask_args
def fund_returns_by_date(
    start_date: Annotated[str, Field(description="Start date in DD.MM.YYYY or YYYY-MM-DD format (e.g., '01.01.2026')")],
    end_date: Annotated[Optional[str], Field(description="End date in DD.MM.YYYY or YYYY-MM-DD format. Defaults to today if not provided.")] = None,
    funds: Annotated[Optional[str], Field(description="Comma-separated fund codes to query (e.g., 'GOL' or 'GOL,GTA'). Leave empty to get all funds.")] = None,
) -> str:
    """Get fund return percentages (daily, weekly, monthly, yearly, YTD, and custom period). Use this when the user asks about fund performance, returns, or yield over a specific date range."""
    from tools.fund_returns import get_fund_returns as _get_fund_returns
    result = _get_fund_returns(start_date, end_date, funds)
    return json.dumps(result, ensure_ascii=False)





class InvestmentAgent:
    """
    Investment Bot Agent using Microsoft Agent Framework with Azure OpenAI GPT-5.1.
    Uses HandoffBuilder to support multi-agent handoffs (investment + currency).
    Handles Turkish investment queries with streaming responses.
    """
    
    def __init__(self):
        """Initialize the agent with Microsoft Agent Framework and Azure OpenAI."""
        # Azure OpenAI base config
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.getenv("AZURE_OPENAI_KEY")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        self.default_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-chat")
        
        # Cache: (deployment_name, language) -> (investment_agent, currency_agent, customer_info_agent)
        self._agents_cache: dict[tuple[str, str], tuple] = {}
        
        # Build default agents eagerly so the first request is fast
        self._get_or_create_agents(self.default_deployment, "tr")
        
        self.deployment = self.default_deployment
    
    def _get_or_create_agents(self, deployment: str, language: Language = "tr") -> tuple:
        """Return (investment_agent, currency_agent, customer_info_agent) for *deployment* and *language*, creating & caching if needed."""
        cache_key = (deployment, language)
        if cache_key in self._agents_cache:
            return self._agents_cache[cache_key]
        
        system_prompt = get_investment_system_prompt(language, datetime.now().strftime('%d.%m.%Y'))
        
        chat_client = AzureOpenAIChatClient(
            api_key=self.api_key,
            endpoint=self.azure_endpoint,
            deployment_name=deployment,
            api_version=self.api_version,
        )
        
        investment_agent = chat_client.as_agent(
            name="investment_agent",
            description="Yatırım fonları ve fon performansı konusunda uzmanlaşmış asistan. Genel yatırım soruları için bu agent başlangıç noktasıdır.",
            instructions=system_prompt,
            tools=[
                search_funds,
                get_fund_details,
                compare_funds,
                get_recommended_funds,
                get_fund_price_history,
                fund_returns_by_date,
            ],
            max_tokens=2048,
            chat_message_store_factory=ReducingChatMessageStore,
        )
        
        currency_agent = create_currency_agent(deployment=deployment, language=language)
        customer_info_agent = create_customer_info_agent(deployment=deployment, language=language)
        
        self._agents_cache[cache_key] = (investment_agent, currency_agent, customer_info_agent)
        logger.info(f"🔧 Created agents for deployment: {deployment}, language: {language}")
        return investment_agent, currency_agent, customer_info_agent
    
    def create_new_workflow(self, model: str | None = None, language: Language = "tr") -> Workflow:
        """Create a new Workflow instance for a session using HandoffBuilder.
        
        Args:
            model: Optional deployment/model name. If None, uses the default.
        
        Note: Do NOT use with_autonomous_mode() for conversational chatbots.
        Autonomous mode injects fake user prompts and loops up to 50 times per turn.
        Without it, the workflow uses human-in-loop mode: after each non-handoff 
        response it emits a RequestInfoEvent and waits for real user input.
        """
        deployment = model or self.default_deployment
        investment_agent, currency_agent, customer_info_agent = self._get_or_create_agents(deployment, language)
        
        workflow = (
            HandoffBuilder(
                name="investment_handoff",
                participants=[investment_agent, currency_agent, customer_info_agent],
            )
            .with_start_agent(investment_agent)
            .add_handoff(investment_agent, [currency_agent],
                         description="Döviz kurları, altın/gümüş fiyatları ve döviz çevirme işlemleri için döviz uzmanına yönlendir.")
            .add_handoff(investment_agent, [customer_info_agent],
                         description="Müşteri bilgileri, portföy durumu ve işlem geçmişi sorguları için müşteri bilgi uzmanına yönlendir.")
            .add_handoff(customer_info_agent, [investment_agent],
                         description="Yatırım fonları, fon performansı ve fon karşılaştırmaları için yatırım uzmanına yönlendir.")
            .add_handoff(customer_info_agent, [currency_agent],
                         description="Döviz kurları ve döviz çevirme işlemleri için döviz uzmanına yönlendir.")
            .add_handoff(currency_agent, [investment_agent],
                         description="Yatırım fonları ve fon performansı için yatırım uzmanına yönlendir.")
            .add_handoff(currency_agent, [customer_info_agent],
                         description="Müşteri bilgileri ve işlem geçmişi için müşteri bilgi uzmanına yönlendir.")
            .build()
        )
        return workflow

    async def stream_response(
        self, 
        user_message: str, 
        workflow: Workflow,
        is_followup: bool = False,
        pending_request_id: str | None = None,
        model: str | None = None,
        language: Language = "tr",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream agent response with tool calls and debug information using HandoffBuilder workflow.
        
        Args:
            user_message: The user's message (possibly PII-masked).
            workflow: The Workflow instance for this session.
            is_followup: Whether this is a follow-up message (send_responses_streaming).
            pending_request_id: The request ID if this is a follow-up response.
        
        Yields events in format:
        {
            "type": "message" | "tool_call" | "tool_result" | "error" | "thinking" | "handoff",
            "data": {...},
            "debug": {...}
        }
        """
        # Tool name to user-friendly message mapping (language-aware)
        tool_messages = {
            tool: get_tool_message(language, tool)
            for tool in [
                "get_customer_info", "get_customer_transactions",
                "search_funds", "get_fund_details", "compare_funds",
                "get_recommended_funds", "get_fund_price_history",
                "fund_returns_by_date", "get_exchange_rate",
                "list_exchange_rates", "convert_currency",
            ]
        }
        
        try:
            logger.info("=" * 60)
            logger.info("🚀 Starting Handoff Workflow Response Stream")
            logger.info(f"User Message: {user_message}")
            logger.info(f"Is Followup: {is_followup}")
            logger.info("=" * 60)
            
            total_start_time = time.time()
            
            # Yield initial thinking event
            yield {
                "type": "thinking",
                "data": {"message": get_message(language, "analyzing")},
                "debug": {
                    "timestamp": datetime.now().isoformat(),
                }
            }
            
            # State tracking for UI events only (no timing)
            active_tool_calls = {}
            current_call_id = None
            response_text = ""
            first_stream_chunk_time = None
            tool_calls_processed = set()
            current_agent_id = "investment_agent"
            new_pending_request_id = None
            
            # Drain any stale spans before starting, then record workflow start in nanoseconds
            # so we can correlate OTel span timestamps with our wall-clock reference.
            drain_spans()
            workflow_start_ns = time.time_ns()
            
            # Track tools already notified via OTel (to avoid duplicate thinking events)
            otel_notified_tools = set()
            
            with ToolStartQueue() as tool_queue:
              # Start the workflow AFTER ToolStartQueue registers OTel callbacks,
              # so _on_llm_start fires for the very first LLM span.
              if is_followup and pending_request_id:
                  try:
                      responses = {
                          pending_request_id: HandoffAgentUserRequest.create_response(user_message)
                      }
                      event_stream = workflow.send_responses_streaming(responses)
                      logger.info(f"📨 Using send_responses_streaming (followup, request_id={pending_request_id})")
                  except (ValueError, RuntimeError) as e:
                      # Stale pending_request_id — the workflow no longer has this
                      # request (e.g., SSE connection dropped before client got the
                      # new request_id).  Fall back to run_stream so the user's
                      # message is not lost.  The thread store still has history.
                      logger.warning(
                          f"⚠️ send_responses_streaming failed (stale request_id={pending_request_id}): {e}. "
                          f"Falling back to workflow.run_stream."
                      )
                      event_stream = workflow.run_stream(user_message)
              else:
                  logger.info(f"📨 Using workflow.run_stream (new run, is_followup={is_followup})")
                  event_stream = workflow.run_stream(user_message)
              # Helper to flush early OTel tool-start signals to the client
              # without waiting for the next workflow event.
              async def _flush_tool_queue():
                  while (early_tool := tool_queue.try_get()) is not None:
                      if early_tool not in otel_notified_tools and not early_tool.startswith('handoff_to_'):
                          otel_notified_tools.add(early_tool)
                          friendly = tool_messages.get(early_tool, get_default_tool_message(language))
                          yield {
                              "type": "thinking",
                              "data": {"message": friendly},
                              "debug": {
                                  "tool_name": early_tool,
                                  "agent_id": current_agent_id,
                                  "source": "otel_early",
                                  "timestamp": datetime.now().isoformat()
                              }
                          }

              # Poll-based loop: drains OTel queue every 100ms even when no
              # workflow event has arrived yet, eliminating the latency where
              # tool-start signals sat unseen until the next stream chunk.
              event_iter = event_stream.__aiter__()
              stream_done = False
              anext_task: asyncio.Task | None = None

              try:
                while not stream_done:
                  # Flush any OTel early signals immediately
                  async for early_event in _flush_tool_queue():
                      yield early_event

                  # Create the __anext__ task only if one is not already pending.
                  # IMPORTANT: we must NOT cancel this task on timeout — cancelling
                  # __anext__() corrupts the async generator's internal state and
                  # causes subsequent calls to raise StopAsyncIteration immediately.
                  if anext_task is None:
                      anext_task = asyncio.ensure_future(event_iter.__anext__())

                  # Wait up to 100ms for the next event; if it doesn't arrive,
                  # loop back to flush the OTel queue and try again.
                  done, _ = await asyncio.wait({anext_task}, timeout=0.1)

                  if not done:
                      # Timeout — task is still pending; loop back to drain queue
                      continue

                  # Task completed — retrieve the result
                  try:
                      wf_event = anext_task.result()
                  except StopAsyncIteration:
                      stream_done = True
                      async for early_event in _flush_tool_queue():
                          yield early_event
                      break
                  finally:
                      anext_task = None  # reset so next iteration creates a fresh task

            # logger.info(f"📨 Workflow event: {type(wf_event).__name__}")
                  # ── AgentRunUpdateEvent: streaming chunks from an agent ──
                  if isinstance(wf_event, AgentRunUpdateEvent):
                      agent_id = wf_event.executor_id
                      if agent_id != current_agent_id:
                          current_agent_id = agent_id
                          logger.info(f"🔄 Active agent: {agent_id}")
                    
                      update = wf_event.data
                      update_dict = update.to_dict() if hasattr(update, 'to_dict') else {}
                      contents = update_dict.get('contents', [])
                      logger.debug(f"  AgentRunUpdateEvent contents: {[c.get('type') for c in contents]}")
                    
                      for content in contents:
                          content_type = content.get('type', '')
                        
                          # Handle function_call chunks
                          if content_type == 'function_call':
                              call_id = content.get('call_id', '')
                              name = content.get('name', '')
                              arguments = content.get('arguments', '')
                            
                              if call_id:
                                  current_call_id = call_id
                                  if call_id not in active_tool_calls:
                                      active_tool_calls[call_id] = {'call_id': call_id, 'arguments': arguments}
                              if name and current_call_id:
                                  active_tool_calls[current_call_id]['name'] = name
                                
                                  if current_call_id not in tool_calls_processed:
                                      # Skip handoff tool calls from UI display
                                      if name.startswith('handoff_to_'):
                                          tool_calls_processed.add(current_call_id)
                                          continue
                                    
                                      tool_calls_processed.add(current_call_id)
                                    
                                      logger.info(f"🔧 Tool call (stream event): {name} (agent: {current_agent_id})")
                                    
                                      if name not in otel_notified_tools:
                                          friendly_message = tool_messages.get(name, get_default_tool_message(language))
                                          yield {
                                              "type": "thinking",
                                              "data": {"message": friendly_message},
                                              "debug": {
                                                  "tool_name": name,
                                                  "agent_id": current_agent_id,
                                                  "timestamp": datetime.now().isoformat()
                                              }
                                          }
                                    
                                      yield {
                                          "type": "tool_call",
                                          "data": {
                                              "tool_name": name,
                                              "arguments": {},
                                              "status": "executing"
                                          },
                                          "debug": {
                                              "call_id": current_call_id,
                                              "agent_id": current_agent_id,
                                              "timestamp": datetime.now().isoformat()
                                          }
                                      }
                            
                              if arguments and current_call_id:
                                  active_tool_calls[current_call_id]['arguments'] = active_tool_calls[current_call_id].get('arguments', '') + arguments
                        
                          # Handle function_result
                          elif content_type == 'function_result':
                              call_id = content.get('call_id', '')
                              result = content.get('result', '')
                            
                              matched_call = active_tool_calls.get(call_id, {})
                              tool_name = matched_call.get('name', 'unknown')
                            
                              # Skip handoff tool results
                              if tool_name.startswith('handoff_to_'):
                                  active_tool_calls.pop(call_id, None)
                                  current_call_id = None
                                  continue
                            
                              logger.info(f"✅ Tool result: {tool_name}")
                            
                              tool_args = {}
                              if matched_call.get('arguments'):
                                  try:
                                      tool_args = json.loads(matched_call['arguments'])
                                  except:
                                      tool_args = {}
                            
                              parsed_result = result
                              try:
                                  parsed_result = json.loads(result) if isinstance(result, str) else result
                                  if isinstance(parsed_result, dict) and 'data' in parsed_result:
                                      parsed_result = parsed_result['data']
                              except:
                                  pass
                            
                              yield {
                                  "type": "tool_result",
                                  "data": {
                                      "tool_name": tool_name,
                                      "result": parsed_result,
                                      "status": "completed"
                                  },
                                  "debug": {
                                      "call_id": call_id,
                                      "agent_id": current_agent_id,
                                      "tool_parameters": tool_args,
                                      "timestamp": datetime.now().isoformat()
                                  }
                              }
                            
                              active_tool_calls.pop(call_id, None)
                              current_call_id = None
                              # After a tool result, the next output is from a new LLM call
                              _awaiting_new_llm = True
                        
                          # Handle text content
                          elif content_type == 'text':
                              text_chunk = content.get('text', '')
                              if text_chunk:
                                  if first_stream_chunk_time is None:
                                      first_stream_chunk_time = time.time()
                                  response_text += text_chunk
                                  yield {
                                      "type": "message_chunk",
                                      "data": {
                                          "content": text_chunk,
                                          "role": "assistant"
                                      },
                                      "debug": {
                                          "agent_id": current_agent_id,
                                          "timestamp": datetime.now().isoformat()
                                      }
                                  }
                        
                          # Handle usage content (accumulated for debug, actual timing from OTel)
                          elif content_type == 'usage':
                              pass  # Token counts will be extracted from OTel spans
                
                  # ── HandoffSentEvent: agent is handing off to another ──
                  elif isinstance(wf_event, HandoffSentEvent):
                      logger.info(f"🤝 Handoff: {wf_event.source} → {wf_event.target}")
                                        
                      yield {
                          "type": "thinking",
                          "data": {"message": get_message(language, "handoff")},
                          "debug": {
                              "source": wf_event.source,
                              "target": wf_event.target,
                              "timestamp": datetime.now().isoformat()
                          }
                      }
                    
                      current_agent_id = wf_event.target
                
                  # ── RequestInfoEvent: workflow needs user input (follow-up) ──
                  elif isinstance(wf_event, RequestInfoEvent):
                      new_pending_request_id = wf_event.request_id
                      logger.info(f"📋 Workflow requesting user input (request_id: {wf_event.request_id})")
                
                  # ── WorkflowStatusEvent: lifecycle ──
                  elif isinstance(wf_event, WorkflowStatusEvent):
                      logger.info(f"📊 Workflow status: {wf_event.state}")

              finally:
                  # Clean up: cancel any pending task and properly close the
                  # async iterator so the framework's workflow generator exits
                  # cleanly without OTel context-detach errors.
                  if anext_task is not None and not anext_task.done():
                      anext_task.cancel()
                      try:
                          await anext_task
                      except (asyncio.CancelledError, StopAsyncIteration):
                          pass
                  if hasattr(event_iter, 'aclose'):
                      try:
                          await event_iter.aclose()
                      except Exception:
                          pass
            
            # ── Build timeline from OTel spans (accurate timing from framework internals) ──
            total_time_ms = (time.time() - total_start_time) * 1000
            
            collected_spans = drain_spans()
            otel_data = spans_to_timeline(collected_spans, workflow_start_ns)
            
            timeline_events = otel_data["timeline_events"]
            
            logger.info("=" * 60)
            logger.info("✅ Handoff Workflow Response Complete")
            logger.info(f"Total Request Time: {total_time_ms:.2f}ms")
            logger.info(f"Final Agent: {current_agent_id}")
            logger.info(f"OTel spans collected: {len(collected_spans)} (LLM: {otel_data['total_llm_requests']}, Tool: {len([e for e in timeline_events if e['event_type'] == 'tool_call'])})")
            logger.info("=" * 60)
            
            # Yield final complete message
            active_deployment = model or self.default_deployment
            yield {
                "type": "message",
                "data": {
                    "content": response_text,
                    "role": "assistant"
                },
                "debug": {
                    "model": active_deployment,
                    "active_agent": current_agent_id,
                    "pending_request_id": new_pending_request_id,
                    "timestamp": datetime.now().isoformat(),
                    "timeline_events": timeline_events,
                    "total_llm_requests": otel_data["total_llm_requests"],
                    "total_llm_time_ms": otel_data["total_llm_time_ms"],
                    "total_tool_time_ms": otel_data["total_tool_time_ms"],
                    "total_input_tokens": otel_data["total_input_tokens"],
                    "total_output_tokens": otel_data["total_output_tokens"],
                    "total_request_time_ms": round(total_time_ms, 2)
                }
            }
            
        except Exception as e:
            error_traceback = traceback.format_exc()
            logger.error(f"Error in stream_response: {e}")
            logger.error(f"Traceback:\n{error_traceback}")
            yield {
                "type": "error",
                "data": {
                    "error": str(e),
                    "message": get_message(language, "error")
                },
                "debug": {
                    "error_type": type(e).__name__,
                    "traceback": error_traceback,
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    async def get_response(
        self, 
        user_message: str, 
        workflow: Workflow,
        is_followup: bool = False,
        pending_request_id: str | None = None,
    ) -> Dict[str, Any]:
        """
        Get a single, non-streaming response from the agent.
        Used for testing and non-streaming endpoint.
        """
        final_response = None
        async for event in self.stream_response(user_message, workflow, is_followup, pending_request_id):
            if event["type"] == "message":
                final_response = event
        
        return final_response if final_response else {
            "type": "error",
            "data": {"error": "No response generated"},
            "debug": {}
        }
