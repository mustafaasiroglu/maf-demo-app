import traceback
from typing import Dict, List, Any, AsyncGenerator, Annotated, Optional
from datetime import datetime
import time
import os
import json
import logging
import asyncio
from pydantic import Field
from agent_framework import ChatAgent
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Configure logging (use INFO level in production for better performance)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Tool functions with proper annotations for Microsoft Agent Framework
def search_fund_info(
    fund_name: Annotated[str, Field(description="The fund code or name to search for (e.g., GTA, GOL, GTL)")],
    query_type: Annotated[Optional[str], Field(description="Optional: Specific aspect to query (e.g., 'risk', 'returns', 'holdings')")] = None
) -> str:
    """Search for information about investment funds. Use this to get fund details, risk levels, returns, and descriptions. Supports GTA (Technology Fund), GOL (Gold Fund), and GTL (Liquid Fund)."""
    from tools.fund_knowledge import search_fund_info as _search_fund_info
    result = _search_fund_info(fund_name, query_type)
    return json.dumps(result, ensure_ascii=False)


def compare_funds(
    fund_codes: Annotated[List[str], Field(description="List of fund codes to compare (e.g., ['GTA', 'GOL', 'GTL'])")],
    metric: Annotated[str, Field(description="Metric to compare (e.g., 'returns', 'risk', 'fees')")] = "returns"
) -> str:
    """Compare multiple investment funds based on specific metrics like returns, risk levels, or fees."""
    from tools.fund_knowledge import compare_funds as _compare_funds
    result = _compare_funds(fund_codes, metric)
    return json.dumps(result, ensure_ascii=False)


def list_all_funds(
    sort_by: Annotated[str, Field(description="Metric to sort funds by")] = "returns_1_week"
) -> str:
    """List all available investment funds, optionally sorted by a specific metric like returns or risk level."""
    from tools.fund_knowledge import list_all_funds as _list_all_funds
    result = _list_all_funds(sort_by)
    return json.dumps(result, ensure_ascii=False)


def get_customer_transactions(
    customer_id: Annotated[Optional[str], Field(description="Customer ID (optional, uses current customer if not provided)")] = None,
    fund_code: Annotated[Optional[str], Field(description="Filter by specific fund code (e.g., 'GTA', 'GOL')")] = None,
    transaction_type: Annotated[Optional[str], Field(description="Filter by transaction type (BUY, SELL, DIVIDEND)")] = None,
    limit: Annotated[int, Field(description="Maximum number of transactions to return")] = 50
) -> str:
    """Get customer's transaction history with investment funds. Can filter by fund code, transaction type, or date range."""
    from tools.customer_transactions import get_customer_transactions as _get_customer_transactions
    result = _get_customer_transactions(customer_id, fund_code, transaction_type, None, None, limit)
    return json.dumps(result, ensure_ascii=False)


def get_customer_info(
    customer_id: Annotated[Optional[str], Field(description="Customer ID (optional, uses current customer if not provided)")] = None
) -> str:
    """Get customer's personal information, portfolio holdings, and account details. Use this to answer 'Who am I?' or identity questions."""
    from tools.customer_transactions import get_customer_info as _get_customer_info
    result = _get_customer_info(customer_id)
    return json.dumps(result, ensure_ascii=False)

class InvestmentAgent:
    """
    Investment Bot Agent using Microsoft Agent Framework with Azure OpenAI GPT-5.1.
    Handles Turkish investment queries with streaming responses.
    """
    
    def __init__(self):
        """Initialize the agent with Microsoft Agent Framework."""
        # System prompt in English for GPT-5.1
        self.system_prompt = """You are an expert Turkish investment advisor assistant for Garanti Bank. Your role is to help customers with their investment fund questions.

Key Responsibilities:
- Answer questions about investment funds (GTA, GOL, GTL) in Turkish
- Provide information about fund performance, risks, and characteristics
- Help customers understand their portfolio and transaction history
- Compare funds and make recommendations based on customer needs
- Always respond in Turkish, even though this prompt is in English

Available Funds:
- GTA (Garanti Teknoloji A Tipi Fon): Technology-focused equity fund with high risk and high returns
- GOL (Garanti Ons Altın Fonu): Gold/precious metals fund with medium risk
- GTL (Garanti Likit Fon): Liquid fund with low risk and high liquidity

Guidelines:
1. Always use the provided tools to fetch accurate, up-to-date information
2. Respond in clear, professional Turkish
3. Explain investment concepts in simple terms
4. When comparing funds, present data in an organized, easy-to-understand format
5. Always mention risk levels when discussing funds
6. Be helpful and friendly while maintaining professionalism
7. If you need to use multiple tools, call them sequentially to gather complete information

Remember: You must respond in Turkish to all user queries."""
        
        # Create Azure OpenAI client with explicit parameters
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-chat")
        
        # Create Azure OpenAI chat client with explicit configuration
        self.chat_client = AzureOpenAIChatClient(
            api_key=api_key,
            endpoint=azure_endpoint,
            deployment_name=deployment,
            api_version=api_version
        )
        
        # Create agent with tools
        self.agent = self.chat_client.as_agent(
            instructions=self.system_prompt,
            tools=[
                search_fund_info,
                compare_funds,
                list_all_funds,
                get_customer_transactions,
                get_customer_info
            ]
        )
        
        self.deployment = deployment
    
    async def stream_response(
        self, 
        user_message: str, 
        conversation_history: List[Dict[str, str]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream agent response with tool calls and debug information using Microsoft Agent Framework.
        Uses run_stream for real-time streaming of tool calls and responses.
        
        Yields events in format:
        {
            "type": "message" | "tool_call" | "tool_result" | "error" | "thinking",
            "data": {...},
            "debug": {...}
        }
        """
        # Tool name to Turkish message mapping
        tool_messages = {
            "get_customer_info": "Müşteri bilgilerinize bakıyorum...",
            "get_customer_transactions": "İşlem geçmişinizi inceliyorum...",
            "search_fund_info": "Fon detaylarını araştırıyorum...",
            "compare_funds": "Fonları karşılaştırıyorum...",
            "list_all_funds": "Fonları listeliyorum..."
        }
        
        try:
            logger.info("=" * 60)
            logger.info("🚀 Starting Agent Response Stream (using run_stream)")
            logger.info(f"User Message: {user_message}")
            logger.info(f"History Length: {len(conversation_history)}")
            logger.info("=" * 60)
            
            # Track LLM request timings and timeline events
            llm_requests = []
            timeline_events = []  # Unified timeline of all events
            total_start_time = time.time()
            current_llm_start = time.time()
            llm_request_count = 0
            event_order = 0
            total_tool_time_ms = 0
            
            # Yield initial thinking event
            yield {
                "type": "thinking",
                "data": {"message": "Sorunuzu analiz ediyorum..."},
                "debug": {
                    "timestamp": datetime.now().isoformat(),
                    "context_size": len(conversation_history)
                }
            }
            
            # State tracking for streaming
            current_tool_call = {}  # Accumulate function_call chunks
            response_text = ""
            tool_calls_processed = set()  # Track which tool calls we've already emitted events for
            
            # Build context from conversation history (max last 4 messages, excluding current)
            history_without_current = conversation_history[:-1]  # Exclude current user message
            recent_history = history_without_current[-4:] if len(history_without_current) > 4 else history_without_current
            
            context_messages = []
            for msg in recent_history:
                role = "Kullanıcı" if msg["role"] == "user" else "Asistan"
                context_messages.append(f"{role}: {msg['content']}")
            
            # Create the full prompt with history context
            if context_messages:
                history_context = "\n".join(context_messages)
                full_prompt = f"""Önceki konuşma geçmişi:
{history_context}

Şu anki kullanıcı mesajı: {user_message}"""
                logger.info(f"📝 Sending message with {len(context_messages)} previous messages as context (max 4)")
            else:
                full_prompt = user_message
                logger.info("📝 Sending message without history context")
            
            # Stream using run_stream for real-time events with conversation context
            async for update in self.agent.run_stream(full_prompt):
                update_dict = update.to_dict() if hasattr(update, 'to_dict') else {}
                contents = update_dict.get('contents', [])
                role = update_dict.get('role', {}).get('value', '') if isinstance(update_dict.get('role'), dict) else ''
                
                for content in contents:
                    content_type = content.get('type', '')
                    
                    # Handle function_call chunks (tool is about to be called)
                    if content_type == 'function_call':
                        call_id = content.get('call_id', '')
                        name = content.get('name', '')
                        arguments = content.get('arguments', '')
                        
                        # First chunk has call_id and name
                        if call_id:
                            current_tool_call['call_id'] = call_id
                        if name:
                            current_tool_call['name'] = name
                            
                            # Emit thinking and tool_call events when we get the tool name
                            if current_tool_call.get('call_id') not in tool_calls_processed:
                                tool_calls_processed.add(current_tool_call.get('call_id'))
                                friendly_message = tool_messages.get(name, "Bilgileri topluyorum...")
                                
                                # Track LLM request timing (tool call means LLM finished deciding)
                                llm_request_count += 1
                                llm_end_time = time.time()
                                llm_duration_ms = (llm_end_time - current_llm_start) * 1000
                                event_order += 1
                                llm_requests.append({
                                    "request_number": llm_request_count,
                                    "type": "tool_decision",
                                    "duration_ms": round(llm_duration_ms, 2),
                                    "timestamp": datetime.now().isoformat()
                                })
                                timeline_events.append({
                                    "order": event_order,
                                    "event_type": "llm_request",
                                    "label": f"LLM Request (tool_decision, {self.deployment})",
                                    "duration_ms": round(llm_duration_ms, 2),
                                    "timestamp": datetime.now().isoformat()
                                })
                                logger.info(f"⏱️ LLM Request #{llm_request_count}: {llm_duration_ms:.2f}ms (tool decision)")
                                
                                logger.info(f"🔧 Tool call starting: {name}")
                                
                                # Emit thinking event
                                yield {
                                    "type": "thinking",
                                    "data": {"message": friendly_message},
                                    "debug": {
                                        "tool_name": name,
                                        "timestamp": datetime.now().isoformat()
                                    }
                                }
                                
                                # Emit tool_call event with status "executing"
                                yield {
                                    "type": "tool_call",
                                    "data": {
                                        "tool_name": name,
                                        "arguments": {},  # Arguments will come in chunks
                                        "status": "executing"
                                    },
                                    "debug": {
                                        "call_id": call_id,
                                        "llm_request_number": llm_request_count,
                                        "llm_duration_ms": round(llm_duration_ms, 2),
                                        "timestamp": datetime.now().isoformat()
                                    }
                                }
                                
                                # Record tool execution start time
                                current_tool_call['start_time'] = time.time()
                        
                        # Accumulate arguments
                        if arguments:
                            current_tool_call['arguments'] = current_tool_call.get('arguments', '') + arguments
                    
                    # Handle function_result (tool has completed)
                    elif content_type == 'function_result':
                        call_id = content.get('call_id', '')
                        result = content.get('result', '')
                        tool_name = current_tool_call.get('name', 'unknown')
                        
                        # Calculate tool execution time
                        tool_start = current_tool_call.get('start_time', time.time())
                        tool_execution_ms = (time.time() - tool_start) * 1000
                        
                        logger.info(f"✅ Tool result received: {tool_name} ({tool_execution_ms:.2f}ms)")
                        
                        # Parse arguments if available
                        tool_args = {}
                        if current_tool_call.get('arguments'):
                            try:
                                tool_args = json.loads(current_tool_call['arguments'])
                            except:
                                tool_args = {}
                        
                        # Parse result
                        parsed_result = result
                        try:
                            parsed_result = json.loads(result) if isinstance(result, str) else result
                            if isinstance(parsed_result, dict) and 'data' in parsed_result:
                                parsed_result = parsed_result['data']
                        except:
                            pass
                        
                        # Emit tool_result event
                        yield {
                            "type": "tool_result",
                            "data": {
                                "tool_name": tool_name,
                                "result": parsed_result,
                                "status": "completed"
                            },
                            "debug": {
                                "call_id": call_id,
                                "tool_parameters": tool_args,
                                "tool_execution_ms": round(tool_execution_ms, 2),
                                "timestamp": datetime.now().isoformat()
                            }
                        }
                        
                        # Add tool call to timeline
                        event_order += 1
                        total_tool_time_ms += tool_execution_ms
                        args_str = json.dumps(tool_args, ensure_ascii=False) if tool_args else "{}"
                        timeline_events.append({
                            "order": event_order,
                            "event_type": "tool_call",
                            "label": f"Tool Call ({tool_name} {args_str})",
                            "duration_ms": round(tool_execution_ms, 2),
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        # Reset for next potential tool call and start new LLM timer
                        current_tool_call = {}
                        current_llm_start = time.time()  # New LLM request starts after tool result
                    
                    # Handle text content (final response)
                    elif content_type == 'text':
                        text_chunk = content.get('text', '')
                        if text_chunk:
                            response_text += text_chunk
                            # Stream text chunks as they arrive
                            yield {
                                "type": "message_chunk",
                                "data": {
                                    "content": text_chunk,
                                    "role": "assistant"
                                },
                                "debug": {
                                    "timestamp": datetime.now().isoformat()
                                }
                            }
            
            # Track final LLM response time
            llm_request_count += 1
            llm_end_time = time.time()
            llm_duration_ms = (llm_end_time - current_llm_start) * 1000
            event_order += 1
            llm_requests.append({
                "request_number": llm_request_count,
                "type": "final_response",
                "duration_ms": round(llm_duration_ms, 2),
                "timestamp": datetime.now().isoformat()
            })
            timeline_events.append({
                "order": event_order,
                "event_type": "llm_request",
                "label": f"LLM Request (final_response, {self.deployment})",
                "duration_ms": round(llm_duration_ms, 2),
                "timestamp": datetime.now().isoformat()
            })
            logger.info(f"⏱️ LLM Request #{llm_request_count}: {llm_duration_ms:.2f}ms (final response)")
            
            total_time_ms = (time.time() - total_start_time) * 1000
            total_llm_time_ms = sum(r["duration_ms"] for r in llm_requests)
            
            logger.info("=" * 60)
            logger.info("✅ Agent Response Complete")
            logger.info(f"Response Length: {len(response_text)}")
            logger.info(f"Total LLM Requests: {llm_request_count}")
            logger.info(f"Total LLM Time: {total_llm_time_ms:.2f}ms")
            logger.info(f"Total Request Time: {total_time_ms:.2f}ms")
            logger.info("=" * 60)
            
            # Add assistant response to conversation history
            if response_text:
                conversation_history.append({
                    "role": "assistant",
                    "content": response_text
                })
            
            # Yield final complete message event with LLM timing details
            yield {
                "type": "message",
                "data": {
                    "content": response_text,
                    "role": "assistant"
                },
                "debug": {
                    "model": self.deployment,
                    "timestamp": datetime.now().isoformat(),
                    "timeline_events": timeline_events,
                    "llm_requests": llm_requests,
                    "total_llm_requests": llm_request_count,
                    "total_llm_time_ms": round(total_llm_time_ms, 2),
                    "total_tool_time_ms": round(total_tool_time_ms, 2),
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
                    "message": "Bir hata oluştu. Lütfen tekrar deneyin."
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
        conversation_history: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Get a single, non-streaming response from the agent.
        Used for testing and non-streaming endpoint.
        """
        final_response = None
        async for event in self.stream_response(user_message, conversation_history):
            if event["type"] == "message":
                final_response = event
        
        return final_response if final_response else {
            "type": "error",
            "data": {"error": "No response generated"},
            "debug": {}
        }
