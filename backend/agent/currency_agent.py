import json
import os
import logging
from typing import Annotated, Optional, List

from pydantic import Field
from agent_framework.azure import AzureOpenAIChatClient
from tools.pii import pii_unmask_args

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
# Tool wrappers (annotated for Microsoft Agent Framework)
# ────────────────────────────────────────────────────────────

@pii_unmask_args
def get_exchange_rate(
    currency_code: Annotated[str, Field(description="The currency code to look up (e.g., USD, EUR, GBP, XAU)")],
) -> str:
    """Get the current exchange rate for a specific currency against Turkish Lira (TRY). Use this for questions like 'Dolar kaç?', 'Euro kuru nedir?', 'Altın fiyatı'."""
    from tools.currency import get_exchange_rate as _get_exchange_rate
    result = _get_exchange_rate(currency_code)
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


@pii_unmask_args
def get_currency_history(
    currency_code: Annotated[str, Field(description="The currency code to get history for (e.g., USD, EUR)")],
) -> str:
    """Get 7-day price history for a currency. Use for 'Doların son 1 haftalık seyri', 'Euro grafiği'."""
    from tools.currency import get_currency_history as _get_currency_history
    result = _get_currency_history(currency_code)
    return json.dumps(result, ensure_ascii=False)


# ────────────────────────────────────────────────────────────
# Agent factory
# ────────────────────────────────────────────────────────────

CURRENCY_SYSTEM_PROMPT = """You are a specialized currency and foreign exchange assistant for Garanti Bank.
Your expertise is in exchange rates, currency conversions, gold/silver prices, and FX market information.

Key Responsibilities:
- Provide current exchange rates for major currencies (USD, EUR, GBP, etc.)
- Convert amounts between currencies
- Show currency price history and trends
- Explain gold and silver prices
- Always respond in Turkish

Guidelines:
1. Always use the provided tools to fetch accurate exchange rate data
2. Present rates clearly with buy/sell spreads
3. When showing multiple currencies, use organized tables or lists
4. Mention that rates are indicative ("gösterge niteliğinde")
5. For gold prices, clarify whether it's gram or ounce
6. Be helpful and professional
7. If asked about investment funds or portfolio questions, suggest that those topics can be handled by the investment specialist

Remember: You must respond in Turkish to all user queries."""


def create_currency_agent():
    """Create and return a ChatAgent configured for currency/FX queries."""
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_key = os.getenv("AZURE_OPENAI_KEY")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5.1-chat")

    chat_client = AzureOpenAIChatClient(
        api_key=api_key,
        endpoint=azure_endpoint,
        deployment_name=deployment,
        api_version=api_version,
    )

    agent = chat_client.as_agent(
        name="currency_agent",
        description="Döviz kurları, altın/gümüş fiyatları ve döviz çevirme işlemleri konusunda uzmanlaşmış asistan. Döviz soruları için bu agent'a yönlendirme yapın.",
        instructions=CURRENCY_SYSTEM_PROMPT,
        tools=[
            get_exchange_rate,
            list_exchange_rates,
            convert_currency,
            get_currency_history,
        ],
    )

    return agent
