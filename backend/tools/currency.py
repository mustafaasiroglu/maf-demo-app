from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

# Dummy exchange rate database (base currency: TRY)
CURRENCY_DATABASE = {
    "USD": {
        "code": "USD",
        "name": "Amerikan Doları",
        "name_en": "US Dollar",
        "symbol": "$",
        "buy_rate": 36.45,
        "sell_rate": 36.62,
        "change_1d": 0.18,
        "change_1w": 0.85,
        "change_1m": 1.42,
        "last_updated": "2026-02-10T10:30:00",
        "history_7d": [36.10, 36.18, 36.25, 36.30, 36.28, 36.40, 36.45],
    },
    "EUR": {
        "code": "EUR",
        "name": "Euro",
        "name_en": "Euro",
        "symbol": "€",
        "buy_rate": 38.12,
        "sell_rate": 38.35,
        "change_1d": -0.10,
        "change_1w": 0.55,
        "change_1m": 1.20,
        "last_updated": "2026-02-10T10:30:00",
        "history_7d": [37.80, 37.85, 37.95, 38.05, 38.10, 38.18, 38.12],
    },
    "GBP": {
        "code": "GBP",
        "name": "İngiliz Sterlini",
        "name_en": "British Pound",
        "symbol": "£",
        "buy_rate": 45.80,
        "sell_rate": 46.10,
        "change_1d": 0.25,
        "change_1w": 1.10,
        "change_1m": 2.05,
        "last_updated": "2026-02-10T10:30:00",
        "history_7d": [45.20, 45.35, 45.42, 45.55, 45.60, 45.72, 45.80],
    },
    "CHF": {
        "code": "CHF",
        "name": "İsviçre Frangı",
        "name_en": "Swiss Franc",
        "symbol": "CHF",
        "buy_rate": 40.25,
        "sell_rate": 40.50,
        "change_1d": 0.08,
        "change_1w": 0.42,
        "change_1m": 0.95,
        "last_updated": "2026-02-10T10:30:00",
        "history_7d": [39.95, 40.00, 40.05, 40.10, 40.15, 40.20, 40.25],
    },
    "JPY": {
        "code": "JPY",
        "name": "Japon Yeni",
        "name_en": "Japanese Yen",
        "symbol": "¥",
        "buy_rate": 0.2380,
        "sell_rate": 0.2410,
        "change_1d": -0.0005,
        "change_1w": 0.0020,
        "change_1m": 0.0045,
        "last_updated": "2026-02-10T10:30:00",
        "history_7d": [0.2365, 0.2368, 0.2370, 0.2375, 0.2378, 0.2382, 0.2380],
    },
    "SAR": {
        "code": "SAR",
        "name": "Suudi Arabistan Riyali",
        "name_en": "Saudi Riyal",
        "symbol": "﷼",
        "buy_rate": 9.72,
        "sell_rate": 9.78,
        "change_1d": 0.04,
        "change_1w": 0.22,
        "change_1m": 0.38,
        "last_updated": "2026-02-10T10:30:00",
        "history_7d": [9.58, 9.60, 9.63, 9.65, 9.68, 9.70, 9.72],
    },
    "AUD": {
        "code": "AUD",
        "name": "Avustralya Doları",
        "name_en": "Australian Dollar",
        "symbol": "A$",
        "buy_rate": 23.15,
        "sell_rate": 23.40,
        "change_1d": 0.12,
        "change_1w": 0.65,
        "change_1m": 1.10,
        "last_updated": "2026-02-10T10:30:00",
        "history_7d": [22.75, 22.82, 22.90, 22.95, 23.00, 23.10, 23.15],
    },
    "CAD": {
        "code": "CAD",
        "name": "Kanada Doları",
        "name_en": "Canadian Dollar",
        "symbol": "C$",
        "buy_rate": 25.30,
        "sell_rate": 25.55,
        "change_1d": 0.10,
        "change_1w": 0.48,
        "change_1m": 0.92,
        "last_updated": "2026-02-10T10:30:00",
        "history_7d": [25.00, 25.05, 25.10, 25.15, 25.18, 25.25, 25.30],
    },
    "XAU": {
        "code": "XAU",
        "name": "Gram Altın",
        "name_en": "Gold (gram)",
        "symbol": "XAU",
        "buy_rate": 3125.00,
        "sell_rate": 3140.00,
        "change_1d": 15.00,
        "change_1w": 45.00,
        "change_1m": 120.00,
        "last_updated": "2026-02-10T10:30:00",
        "history_7d": [3080.00, 3085.00, 3095.00, 3100.00, 3110.00, 3118.00, 3125.00],
    },
    "XAG": {
        "code": "XAG",
        "name": "Gram Gümüş",
        "name_en": "Silver (gram)",
        "symbol": "XAG",
        "buy_rate": 36.50,
        "sell_rate": 37.00,
        "change_1d": 0.30,
        "change_1w": 1.20,
        "change_1m": 2.80,
        "last_updated": "2026-02-10T10:30:00",
        "history_7d": [35.50, 35.65, 35.80, 35.95, 36.10, 36.35, 36.50],
    },
}


def get_exchange_rate(currency_code: str) -> Dict[str, Any]:
    """
    Get the current exchange rate for a specific currency against TRY.

    Args:
        currency_code: Currency code (e.g., "USD", "EUR", "GBP")

    Returns:
        Dictionary with exchange rate information
    """
    code = currency_code.upper().strip()

    if code in CURRENCY_DATABASE:
        currency = CURRENCY_DATABASE[code]
        return {
            "status": "success",
            "data": {
                "code": currency["code"],
                "name": currency["name"],
                "symbol": currency["symbol"],
                "buy_rate": currency["buy_rate"],
                "sell_rate": currency["sell_rate"],
                "spread": round(currency["sell_rate"] - currency["buy_rate"], 4),
                "change_1d": currency["change_1d"],
                "change_1d_pct": round((currency["change_1d"] / (currency["buy_rate"] - currency["change_1d"])) * 100, 2),
                "change_1w": currency["change_1w"],
                "change_1m": currency["change_1m"],
                "last_updated": currency["last_updated"],
                "base_currency": "TRY",
            },
        }

    # Try partial match
    matches = []
    for key, val in CURRENCY_DATABASE.items():
        if code in val["name"].upper() or code in val["name_en"].upper() or code in key:
            matches.append(key)

    if matches:
        return {
            "status": "partial_match",
            "message": f"'{currency_code}' bulunamadı. Şunu mu demek istediniz?",
            "suggestions": matches,
        }

    return {
        "status": "not_found",
        "message": f"'{currency_code}' kodlu döviz bulunamadı.",
        "available_currencies": list(CURRENCY_DATABASE.keys()),
    }


def list_exchange_rates(sort_by: str = "code") -> Dict[str, Any]:
    """
    List all available exchange rates.

    Args:
        sort_by: Sort criteria - "code", "buy_rate", "change_1d", "change_1w"

    Returns:
        Dictionary with all exchange rates
    """
    rates = []
    for code, currency in CURRENCY_DATABASE.items():
        rates.append({
            "code": currency["code"],
            "name": currency["name"],
            "symbol": currency["symbol"],
            "buy_rate": currency["buy_rate"],
            "sell_rate": currency["sell_rate"],
            "change_1d": currency["change_1d"],
            "change_1w": currency["change_1w"],
            "change_1m": currency["change_1m"],
        })

    # Sort
    sort_key_map = {
        "code": lambda x: x["code"],
        "buy_rate": lambda x: x["buy_rate"],
        "change_1d": lambda x: x["change_1d"],
        "change_1w": lambda x: x["change_1w"],
        "change_1m": lambda x: x["change_1m"],
    }
    sort_fn = sort_key_map.get(sort_by, sort_key_map["code"])
    reverse = sort_by != "code"
    rates.sort(key=sort_fn, reverse=reverse)

    return {
        "status": "success",
        "data": rates,
        "count": len(rates),
        "base_currency": "TRY",
        "last_updated": "2026-02-10T10:30:00",
    }


def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
) -> Dict[str, Any]:
    """
    Convert an amount between two currencies.

    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., "USD", "TRY")
        to_currency: Target currency code (e.g., "TRY", "EUR")

    Returns:
        Dictionary with conversion result
    """
    from_code = from_currency.upper().strip()
    to_code = to_currency.upper().strip()

    # Get rates (everything is relative to TRY)
    if from_code == "TRY":
        from_rate = 1.0
    elif from_code in CURRENCY_DATABASE:
        from_rate = CURRENCY_DATABASE[from_code]["sell_rate"]  # When customer sells foreign, bank buys
    else:
        return {"status": "error", "message": f"'{from_currency}' kodlu döviz bulunamadı."}

    if to_code == "TRY":
        to_rate = 1.0
    elif to_code in CURRENCY_DATABASE:
        to_rate = CURRENCY_DATABASE[to_code]["buy_rate"]  # When customer buys foreign, bank sells
    else:
        return {"status": "error", "message": f"'{to_currency}' kodlu döviz bulunamadı."}

    # Convert: from -> TRY -> to
    try_amount = amount * from_rate
    result_amount = try_amount / to_rate

    return {
        "status": "success",
        "data": {
            "from": {
                "currency": from_code,
                "amount": amount,
            },
            "to": {
                "currency": to_code,
                "amount": round(result_amount, 4),
            },
            "rate": round(from_rate / to_rate, 6),
            "try_equivalent": round(try_amount, 2),
            "note": "Kurlar gösterge niteliğindedir. Gerçek işlem kurları farklılık gösterebilir.",
        },
    }


def get_currency_history(currency_code: str) -> Dict[str, Any]:
    """
    Get 7-day price history for a currency.

    Args:
        currency_code: Currency code (e.g., "USD", "EUR")

    Returns:
        Dictionary with price history
    """
    code = currency_code.upper().strip()

    if code not in CURRENCY_DATABASE:
        return {"status": "error", "message": f"'{currency_code}' kodlu döviz bulunamadı."}

    currency = CURRENCY_DATABASE[code]
    history = currency["history_7d"]

    # Generate date labels for last 7 days
    today = datetime(2026, 2, 10)
    dates = [(today - timedelta(days=6 - i)).strftime("%Y-%m-%d") for i in range(7)]

    return {
        "status": "success",
        "data": {
            "code": code,
            "name": currency["name"],
            "base_currency": "TRY",
            "history": [
                {"date": date, "rate": rate}
                for date, rate in zip(dates, history)
            ],
            "min_rate": min(history),
            "max_rate": max(history),
            "avg_rate": round(sum(history) / len(history), 4),
            "current_rate": currency["buy_rate"],
        },
    }
