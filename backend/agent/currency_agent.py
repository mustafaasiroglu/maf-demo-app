import json
import os
import logging
from typing import Annotated, Optional, List

from pydantic import Field
from agent_framework.azure import AzureOpenAIChatClient
from agent import ReducingChatMessageStore
from tools.pii import pii_unmask_args
from i18n import Language, get_currency_system_prompt

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# Tool wrappers (annotated for Microsoft Agent Framework)
# ────────────────────────────────────────────────────────────

@pii_unmask_args
def get_exchange_rate(
    currency_code: Annotated[str, Field(description="The currency code to look up (e.g., USD, EUR, GBP, XAU)")],
    date_start: Annotated[Optional[str], Field(description="Start date for historical range (DD.MM.YYYY or YYYY-MM-DD). Omit for current rate.")] = None,
    date_end: Annotated[Optional[str], Field(description="End date for historical range (DD.MM.YYYY or YYYY-MM-DD). Omit for current rate.")] = None,
) -> str:
    """Get exchange rate(s) for a currency against TRY. Without dates returns the current rate; with date_start/date_end returns a historical series (daily for ≤30 days, weekly for 31-120 days, monthly for 121+ days). Use for 'Dolar kaç?', 'Euro kuru', 'Son 3 ayda dolar', 'Altın fiyatı', 'Doların son 1 haftalık seyri', 'Euro grafiği'."""
    from tools.currency import get_exchange_rate as _get_exchange_rate
    result = _get_exchange_rate(currency_code, date_start=date_start, date_end=date_end)
    return json.dumps(result, ensure_ascii=False)


@pii_unmask_args
def list_exchange_rates(
    sort_by: Annotated[str, Field(description="Sort criteria: 'code', 'buy_rate', 'change_1d', 'change_1w', 'change_1m'")] = "code",
) -> str:
    """List all available exchange rates (currencies, gold, silver) with their buy/sell rates. Use for 'Tüm döviz kurları', 'Döviz listesi'."""
    from tools.currency import list_exchange_rates as _list_exchange_rates
    result = _list_exchange_rates(sort_by)
    return json.dumps(result, ensure_ascii=False)


@pii_unmask_args
def convert_currency(
    amount: Annotated[float, Field(description="The amount to convert")],
    from_currency: Annotated[str, Field(description="Source currency code (e.g., 'USD', 'EUR', 'TRY')")],
    to_currency: Annotated[str, Field(description="Target currency code (e.g., 'TRY', 'EUR', 'USD')")],
) -> str:
    """Convert an amount from one currency to another. Use for '100 dolar kaç TL?', '500 Euro kaç dolar?'."""
    from tools.currency import convert_currency as _convert_currency
    result = _convert_currency(amount, from_currency, to_currency)
    return json.dumps(result, ensure_ascii=False)


# ────────────────────────────────────────────────────────────
# Agent factory
# ────────────────────────────────────────────────────────────


def create_currency_agent(deployment: str | None = None, language: Language = "tr"):
    """Create and return a ChatAgent configured for currency/FX queries."""
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
        name="currency_agent",
        description="Döviz kurları, altın/gümüş fiyatları ve döviz çevirme işlemleri konusunda uzmanlaşmış asistan. Döviz soruları için bu agent'a yönlendirme yapın.",
        instructions=get_currency_system_prompt(language),
        tools=[
            get_exchange_rate,
            list_exchange_rates,
            convert_currency,
        ],
        max_tokens=2048,
        chat_message_store_factory=ReducingChatMessageStore,
    )

    return agent
