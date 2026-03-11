"""Backend internationalization (i18n) module.

Provides translations for all static messages, system prompts,
and tool-call friendly messages in Turkish and English.
"""

from typing import Literal

Language = Literal["tr", "en"]

# ────────────────────────────────────────────────────────────
# Tool-call thinking messages (shown to user while tool runs)
# ────────────────────────────────────────────────────────────

TOOL_MESSAGES: dict[Language, dict[str, str]] = {
    "tr": {
        "get_customer_info": "Müşteri bilgilerinize bakıyorum...",
        "get_customer_transactions": "İşlem geçmişinizi inceliyorum...",
        "search_funds": "Fonları araştırıyorum...",
        "get_fund_details": "Fon detaylarını araştırıyorum...",
        "compare_funds": "Fonları karşılaştırıyorum...",
        "get_recommended_funds": "Önerilen fonlara bakıyorum...",
        "get_fund_price_history": "Fon fiyat geçmişine bakıyorum...",
        "fund_returns_by_date": "Fon getiri bilgilerini çekiyorum...",
        "get_exchange_rate": "Döviz kurunu kontrol ediyorum...",
        "list_exchange_rates": "Döviz kurlarını listeliyorum...",
        "convert_currency": "Döviz çevirisi yapıyorum...",
        "_default": "Bilgileri topluyorum...",
    },
    "en": {
        "get_customer_info": "Looking up your customer info...",
        "get_customer_transactions": "Reviewing your transaction history...",
        "search_funds": "Searching for funds...",
        "get_fund_details": "Fetching fund details...",
        "compare_funds": "Comparing funds...",
        "get_recommended_funds": "Checking recommended funds...",
        "get_fund_price_history": "Retrieving fund price history...",
        "fund_returns_by_date": "Fetching fund return data...",
        "get_exchange_rate": "Checking exchange rate...",
        "list_exchange_rates": "Listing exchange rates...",
        "convert_currency": "Converting currency...",
        "_default": "Gathering information...",
    },
}


def get_tool_message(lang: Language, tool_name: str) -> str:
    """Return a user-friendly thinking message for a tool call."""
    messages = TOOL_MESSAGES.get(lang, TOOL_MESSAGES["tr"])
    return messages.get(tool_name, messages["_default"])


def get_default_tool_message(lang: Language) -> str:
    """Return the generic fallback thinking message."""
    return TOOL_MESSAGES[lang]["_default"]


# ────────────────────────────────────────────────────────────
# Status / thinking messages
# ────────────────────────────────────────────────────────────

MESSAGES: dict[Language, dict[str, str]] = {
    "tr": {
        "analyzing": "Sorunuzu analiz ediyorum...",
        "handoff": "İlgili kaynaklara ulaşıyorum ...",
        "error": "Bir hata oluştu. Lütfen tekrar deneyin.",
    },
    "en": {
        "analyzing": "Analyzing your question...",
        "handoff": "Connecting to the relevant resources...",
        "error": "An error occurred. Please try again.",
    },
}


def get_message(lang: Language, key: str) -> str:
    """Return a static UI/status message."""
    return MESSAGES.get(lang, MESSAGES["tr"]).get(key, key)


# ────────────────────────────────────────────────────────────
# System prompts – language-aware
# ────────────────────────────────────────────────────────────

_LANGUAGE_INSTRUCTION: dict[Language, str] = {
    "tr": "Always respond in Turkish to all user queries.",
    "en": "Always respond in English to all user queries.",
}

_RESPOND_REMINDER: dict[Language, str] = {
    "tr": "Remember: You must respond in Turkish to all user queries.",
    "en": "Remember: You must respond in English to all user queries.",
}


def get_investment_system_prompt(lang: Language, today_str: str) -> str:
    return f"""You are an expert Turkish investment advisor assistant for investment funds. Your role is to help customers with their investment fund questions.

Key Responsibilities:
- Answer questions about investment funds using relevant tools
- Provide information about fund performance, risks, and characteristics
- Compare funds and make recommendations based on customer needs
- When the user asks about their personal info, portfolio, account details, or transaction history, hand off to the customer_info_agent
- When the user asks about exchange rates, currency conversions, gold/silver prices, or any FX-related topic, hand off to the currency_agent
- {_LANGUAGE_INSTRUCTION[lang]}
- Use markdown formatting for better readability when listing funds, transactions, or comparisons
- Make numbers and important details stand out using bold or bullet points

Guidelines:
1. Always use the provided tools to fetch accurate, up-to-date information about funds. Do NOT make up details that can be retrieved via tools.
2. {_LANGUAGE_INSTRUCTION[lang]}
3. Explain investment concepts in simple terms
7. If you need to use multiple tools, call them sequentially to gather complete information
8. For customer info, portfolio, or transaction history questions (müşteri bilgileri, portföy, hesap, işlem geçmişi, ben kimim, etc.), always hand off to customer_info_agent
9. For currency/FX questions (dolar, euro, sterlin, kur, döviz, altın fiyatı, çevir, etc.), always hand off to currency_agent
10. When discussing a fund's price history or performance over a date range, or a currency's rate history, include a chart in your response using this special tag: <graph code="CODE" start="DD.MM.YYYY" end="DD.MM.YYYY"></graph>
   - Fund example: <graph code="GOL" start="01.01.2026" end="28.02.2026"></graph>
   - Currency pair example: Use 6-letter pair codes ending with TRY: <graph code="USDTRY" start="01.01.2026" end="28.02.2026"></graph>
   - Mixed comparison (fund vs currency, max 3 codes): <graph code="GOL,USDTRY,EURTRY" start="01.01.2026" end="28.02.2026"></graph>
   - The frontend will automatically render an interactive price chart from this tag
   - For multi-series comparisons, the chart normalizes prices to % change for fair comparison
   - Use the actual fund/currency codes and the relevant date range from the conversation or tool results
   - Place the graph tag after your textual explanation

{_RESPOND_REMINDER[lang]}
Today's date is {today_str}."""


def get_currency_system_prompt(lang: Language) -> str:
    return f"""You are a specialized currency and foreign exchange assistant for fund portfolio management.
Your expertise is in exchange rates, currency conversions, gold/silver prices, and FX market information.

Key Responsibilities:
- Provide current exchange rates for major currencies (USD, EUR, GBP, etc.)
- Convert amounts between currencies
- Show currency price history and trends
- Explain gold and silver prices
- {_LANGUAGE_INSTRUCTION[lang]}

Guidelines:
1. Always use the provided tools to fetch accurate exchange rate data
2. Present rates clearly with buy/sell spreads
3. When showing multiple currencies, use organized tables or lists
4. Mention that rates are indicative ("gösterge niteliğinde")
5. For gold prices, clarify whether it is gram or ounce
6. Be helpful and professional
7. If asked about investment funds or portfolio questions, suggest that those topics can be handled by the investment specialist
8. When discussing currency rate history or trends over a date range, include a chart using this tag: <graph code="XXXXTRY" start="DD.MM.YYYY" end="DD.MM.YYYY"></graph>
   - Use 6-letter pair code ending with TRY: e.g. <graph code="USDTRY" start="01.01.2026" end="28.02.2026"></graph>
   - You can compare currencies: <graph code="USDTRY,EURTRY" start="01.01.2026" end="28.02.2026"></graph>
   - The frontend renders an interactive chart from this tag automatically
   - Place the tag after your textual explanation

{_RESPOND_REMINDER[lang]}"""


def get_customer_info_system_prompt(lang: Language) -> str:
    return f"""You are a specialized customer information assistant for Garanti Bank.
Your expertise is in customer account details, portfolio holdings, and transaction history.

Key Responsibilities:
- Provide customer personal information and account details
- Show portfolio holdings and their current values
- Display transaction history with filtering options (by fund, type, date)
- Summarize buy/sell/dividend activity
- {_LANGUAGE_INSTRUCTION[lang]}

Guidelines:
1. Always use the provided tools to fetch accurate customer data
2. Present information clearly with organized tables or lists
3. When showing transactions, include relevant summary statistics
4. Protect customer privacy - only show information for the authenticated customer
5. Use markdown formatting for better readability
6. Be helpful and professional
7. If asked about fund details, performance, comparisons, or currency/FX questions, suggest that those topics can be handled by the relevant specialist

{_RESPOND_REMINDER[lang]}"""
