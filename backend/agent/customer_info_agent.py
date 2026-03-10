import json
import os
import time
import logging
from typing import Annotated, Optional

from pydantic import Field
from agent_framework.azure import AzureOpenAIChatClient
from agent import ReducingChatMessageStore
from tools.pii import pii_unmask_args
from i18n import Language, get_customer_info_system_prompt

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# Tool wrappers (annotated for Microsoft Agent Framework)
# ────────────────────────────────────────────────────────────

@pii_unmask_args
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


@pii_unmask_args
def get_customer_info(
    customer_id: Annotated[Optional[str], Field(description="Customer ID (optional, uses current customer if not provided)")] = None
) -> str:
    """Get customer's personal information, portfolio holdings, and account details. Use this to answer 'Who am I?' or identity questions."""
    from tools.customer_transactions import get_customer_info as _get_customer_info
    time.sleep(0.5)  # Simulate a slight delay for fetching customer info
    result = _get_customer_info(customer_id)
    return json.dumps(result, ensure_ascii=False)


# ────────────────────────────────────────────────────────────
# Agent factory
# ────────────────────────────────────────────────────────────


def create_customer_info_agent(deployment: str | None = None, language: Language = "tr"):
    """Create and return a ChatAgent configured for customer info queries."""
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    deployment = deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-chat")

    chat_client = AzureOpenAIChatClient(
        api_key=api_key,
        endpoint=azure_endpoint,
        deployment_name=deployment,
        api_version=api_version,
    )

    agent = chat_client.as_agent(
        name="customer_info_agent",
        description="Müşteri bilgileri, portföy durumu ve işlem geçmişi konusunda uzmanlaşmış asistan. Müşteri hesap bilgileri ve işlem sorguları için bu agent'a yönlendirme yapın.",
        instructions=get_customer_info_system_prompt(language),
        tools=[
            get_customer_transactions,
            get_customer_info,
        ],
        max_tokens=2048,
        chat_message_store_factory=ReducingChatMessageStore,
    )

    return agent
