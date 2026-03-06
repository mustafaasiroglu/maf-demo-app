"""
TCMB (Turkish Central Bank) live exchange rate provider.

Fetches current and historical rates from:
  https://www.tcmb.gov.tr/kurlar/today.xml
  https://www.tcmb.gov.tr/kurlar/YYYYMM/DDMMYYYY.xml
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
import threading
import time
import logging
import requests

logger = logging.getLogger(__name__)

TCMB_TODAY_URL = "https://www.tcmb.gov.tr/kurlar/today.xml"
TCMB_HISTORY_URL = "https://www.tcmb.gov.tr/kurlar/{ym}/{dmy}.xml"

# In-memory cache: { url: (parsed_dict, fetch_timestamp) }
_cache: Dict[str, tuple] = {}
_cache_lock = threading.Lock()
_CACHE_TTL_SECONDS = 300  # 5 minutes


# ── XML Parsing ──────────────────────────────────────────────────────────────

def _parse_float(text: Optional[str]) -> Optional[float]:
    """Safely parse a float from XML text, returning None for empty/missing."""
    if not text or not text.strip():
        return None
    try:
        return float(text.strip())
    except ValueError:
        return None


def _parse_tcmb_xml(xml_text: str) -> Dict[str, Any]:
    """Parse TCMB XML into a dict keyed by currency code.

    Returns:
        {
            "_meta": {"date": "13.02.2026", "bulletin": "2026/31"},
            "USD": { "code": "USD", "name": "ABD DOLARI", ... },
            ...
        }
    """
    root = ET.fromstring(xml_text)
    result: Dict[str, Any] = {}

    # Meta
    result["_meta"] = {
        "date": root.attrib.get("Tarih", ""),
        "date_iso": root.attrib.get("Date", ""),
        "bulletin": root.attrib.get("Bulten_No", ""),
    }

    for currency_el in root.findall("Currency"):
        code = currency_el.attrib.get("CurrencyCode", "").strip()
        if not code:
            continue

        unit = _parse_float(currency_el.findtext("Unit")) or 1
        forex_buy = _parse_float(currency_el.findtext("ForexBuying"))
        forex_sell = _parse_float(currency_el.findtext("ForexSelling"))
        banknote_buy = _parse_float(currency_el.findtext("BanknoteBuying"))
        banknote_sell = _parse_float(currency_el.findtext("BanknoteSelling"))

        # Normalize to 1 unit
        entry: Dict[str, Any] = {
            "code": code,
            "name": currency_el.findtext("Isim", "").strip(),
            "name_en": currency_el.findtext("CurrencyName", "").strip(),
            "unit": int(unit),
            "forex_buy": round(forex_buy / unit, 6) if forex_buy else None,
            "forex_sell": round(forex_sell / unit, 6) if forex_sell else None,
            "banknote_buy": round(banknote_buy / unit, 6) if banknote_buy else None,
            "banknote_sell": round(banknote_sell / unit, 6) if banknote_sell else None,
        }
        result[code] = entry

    return result


# ── HTTP Fetch with cache ────────────────────────────────────────────────────

def _fetch_tcmb(url: str, use_cache: bool = True) -> Dict[str, Any]:
    """Fetch and parse TCMB XML, with optional caching."""
    now = time.time()

    if use_cache:
        with _cache_lock:
            cached = _cache.get(url)
            if cached and (now - cached[1]) < _CACHE_TTL_SECONDS:
                return cached[0]

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "GarantiBankBot/1.0"})
        resp.raise_for_status()
        resp.encoding = "utf-8"
        parsed = _parse_tcmb_xml(resp.text)

        with _cache_lock:
            _cache[url] = (parsed, now)

        return parsed
    except Exception as e:
        logger.error(f"TCMB fetch failed ({url}): {e}")
        # Return stale cache if available
        with _cache_lock:
            cached = _cache.get(url)
            if cached:
                logger.warning("Returning stale cache for TCMB data")
                return cached[0]
        raise


def _get_today_rates() -> Dict[str, Any]:
    """Fetch today's rates from TCMB."""
    return _fetch_tcmb(TCMB_TODAY_URL)


def _get_historical_rates(dt: datetime) -> Optional[Dict[str, Any]]:
    """Fetch rates for a specific date. Returns None if unavailable (weekend/holiday)."""
    ym = dt.strftime("%Y%m")
    dmy = dt.strftime("%d%m%Y")
    url = TCMB_HISTORY_URL.format(ym=ym, dmy=dmy)
    try:
        return _fetch_tcmb(url, use_cache=True)
    except Exception:
        return None


# ── Date helpers ─────────────────────────────────────────────────────────────

def _parse_date(s: str) -> datetime:
    """Accept DD.MM.YYYY or YYYY-MM-DD."""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(f"Geçersiz tarih formatı: '{s}'. DD.MM.YYYY veya YYYY-MM-DD kullanın.")


def _sample_dates(start: datetime, end: datetime) -> List[datetime]:
    """Return the list of dates to query based on the range length.

    0-30  days  → every calendar day
    31-120 days → Fridays only  (weekday == 4)
    121+  days  → last day of each month
    """
    total_days = (end - start).days
    dates: List[datetime] = []

    if total_days <= 30:
        d = start
        while d <= end:
            dates.append(d)
            d += timedelta(days=1)

    elif total_days <= 120:
        # Weekly – Fridays
        d = start
        days_until_friday = (4 - d.weekday()) % 7
        d += timedelta(days=days_until_friday)
        while d <= end:
            dates.append(d)
            d += timedelta(days=7)
        # Ensure start/end boundaries are included
        if not dates or dates[0] != start:
            dates.insert(0, start)
        if dates[-1] != end:
            dates.append(end)

    else:
        # Monthly – last day of each month
        dates.append(start)
        # Walk through months, adding last day of each
        cursor_year = start.year
        cursor_month = start.month
        while True:
            # Last day of cursor_month
            if cursor_month == 12:
                last_day = datetime(cursor_year + 1, 1, 1) - timedelta(days=1)
            else:
                last_day = datetime(cursor_year, cursor_month + 1, 1) - timedelta(days=1)
            if last_day > end:
                break
            if last_day > start:
                dates.append(last_day)
            # Advance to next month
            if cursor_month == 12:
                cursor_year += 1
                cursor_month = 1
            else:
                cursor_month += 1
        if dates[-1] != end:
            dates.append(end)

    return dates


def _fetch_rate_for_date(
    code: str, dt: datetime, *, max_lookback: int = 5
) -> Optional[Dict[str, Any]]:
    """Try to fetch a rate for *dt*; walk backwards up to *max_lookback*
    calendar days if the target date has no data (weekend/holiday)."""
    for offset in range(max_lookback + 1):
        candidate = dt - timedelta(days=offset)
        rates = _get_historical_rates(candidate)
        if rates and code in rates and code != "_meta":
            c = rates[code]
            buy = c["forex_buy"] or c["banknote_buy"]
            sell = c["forex_sell"] or c["banknote_sell"]
            if buy:
                return {
                    "date": candidate.strftime("%Y-%m-%d"),
                    "requested_date": dt.strftime("%Y-%m-%d"),
                    "buy_rate": buy,
                    "sell_rate": sell,
                }
    return None


# ── Public API ───────────────────────────────────────────────────────────────

def get_exchange_rate(
    currency_code: str,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Get exchange rate(s) for a currency against TRY from TCMB.

    • No dates  → current rate from today.xml
    • With dates → historical series with automatic sampling:
        0-30 days   → daily
        31-120 days → weekly (Fridays)
        121+ days   → monthly
    """
    code = currency_code.upper().strip()

    # ── Current rate (no date range) ─────────────────────────────────────
    if not date_start and not date_end:
        try:
            rates = _get_today_rates()
        except Exception as e:
            return {"status": "error", "message": f"TCMB verilerine erişilemedi: {str(e)}"}

        meta = rates.get("_meta", {})

        if code in rates and code != "_meta":
            c = rates[code]
            buy = c["forex_buy"] or c["banknote_buy"]
            sell = c["forex_sell"] or c["banknote_sell"]

            data: Dict[str, Any] = {
                "code": c["code"],
                "name": c["name"],
                "name_en": c["name_en"],
                "buy_rate": buy,
                "sell_rate": sell,
                "spread": round(sell - buy, 6) if (buy and sell) else None,
                "banknote_buy": c["banknote_buy"],
                "banknote_sell": c["banknote_sell"],
                "base_currency": "TRY",
                "source": "TCMB",
                "date": meta.get("date", ""),
                "bulletin": meta.get("bulletin", ""),
            }
            return {"status": "success", "data": data}

        # Try partial match
        matches = []
        for key, val in rates.items():
            if key == "_meta":
                continue
            if (code in val.get("name", "").upper()
                    or code in val.get("name_en", "").upper()
                    or code in key):
                matches.append(key)

        if matches:
            return {
                "status": "partial_match",
                "message": f"'{currency_code}' bulunamadı. Şunu mu demek istediniz?",
                "suggestions": matches,
            }

        available = [k for k in rates if k != "_meta"]
        return {
            "status": "not_found",
            "message": f"'{currency_code}' kodlu döviz TCMB verilerinde bulunamadı.",
            "available_currencies": available,
        }

    # ── Historical range ─────────────────────────────────────────────────
    try:
        start_dt = _parse_date(date_start) if date_start else None
        end_dt = _parse_date(date_end) if date_end else None
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if not start_dt:
        start_dt = today
    if not end_dt:
        end_dt = today
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    sample_points = _sample_dates(start_dt, end_dt)
    total_days = (end_dt - start_dt).days
    if total_days <= 30:
        sampling = "daily"
    elif total_days <= 120:
        sampling = "weekly"
    else:
        sampling = "monthly"

    history: List[Dict[str, Any]] = []
    for dt in sample_points:
        point = _fetch_rate_for_date(code, dt)
        if point:
            history.append(point)

    if not history:
        return {"status": "error", "message": f"'{currency_code}' için belirtilen tarih aralığında veri bulunamadı."}

    buy_rates = [h["buy_rate"] for h in history]

    return {
        "status": "success",
        "data": {
            "code": code,
            "base_currency": "TRY",
            "source": "TCMB",
            "date_start": start_dt.strftime("%Y-%m-%d"),
            "date_end": end_dt.strftime("%Y-%m-%d"),
            "total_days": total_days,
            "sampling": sampling,
            "history": history,
            "points": len(history),
            "min_rate": min(buy_rates),
            "max_rate": max(buy_rates),
            "avg_rate": round(sum(buy_rates) / len(buy_rates), 4),
        },
    }


def list_exchange_rates(sort_by: str = "code") -> Dict[str, Any]:
    """List all available TCMB exchange rates."""
    try:
        rates = _get_today_rates()
    except Exception as e:
        return {"status": "error", "message": f"TCMB verilerine erişilemedi: {str(e)}"}

    meta = rates.get("_meta", {})
    items = []
    for key, val in rates.items():
        if key == "_meta":
            continue
        buy = val["forex_buy"] or val["banknote_buy"]
        sell = val["forex_sell"] or val["banknote_sell"]
        if not buy and not sell:
            continue
        items.append({
            "code": val["code"],
            "name": val["name"],
            "buy_rate": buy,
            "sell_rate": sell,
        })

    sort_key_map = {
        "code": lambda x: x["code"],
        "buy_rate": lambda x: x.get("buy_rate") or 0,
        "name": lambda x: x["name"],
    }
    sort_fn = sort_key_map.get(sort_by, sort_key_map["code"])
    reverse = sort_by == "buy_rate"
    items.sort(key=sort_fn, reverse=reverse)

    return {
        "status": "success",
        "data": items,
        "count": len(items),
        "base_currency": "TRY",
        "source": "TCMB",
        "date": meta.get("date", ""),
    }


def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
) -> Dict[str, Any]:
    """Convert an amount between two currencies using TCMB rates."""
    from_code = from_currency.upper().strip()
    to_code = to_currency.upper().strip()

    try:
        rates = _get_today_rates()
    except Exception as e:
        return {"status": "error", "message": f"TCMB verilerine erişilemedi: {str(e)}"}

    # Get sell rate for source (customer sells foreign -> bank buys)
    if from_code == "TRY":
        from_rate = 1.0
    elif from_code in rates and from_code != "_meta":
        from_rate = rates[from_code]["forex_sell"] or rates[from_code]["banknote_sell"]
        if not from_rate:
            return {"status": "error", "message": f"'{from_currency}' için satış kuru bulunamadı."}
    else:
        return {"status": "error", "message": f"'{from_currency}' kodlu döviz bulunamadı."}

    # Get buy rate for target (customer buys foreign -> bank sells)
    if to_code == "TRY":
        to_rate = 1.0
    elif to_code in rates and to_code != "_meta":
        to_rate = rates[to_code]["forex_buy"] or rates[to_code]["banknote_buy"]
        if not to_rate:
            return {"status": "error", "message": f"'{to_currency}' için alış kuru bulunamadı."}
    else:
        return {"status": "error", "message": f"'{to_currency}' kodlu döviz bulunamadı."}

    # from -> TRY -> to
    try_amount = amount * from_rate
    result_amount = try_amount / to_rate

    return {
        "status": "success",
        "data": {
            "from": {"currency": from_code, "amount": amount},
            "to": {"currency": to_code, "amount": round(result_amount, 4)},
            "rate": round(from_rate / to_rate, 6),
            "try_equivalent": round(try_amount, 2),
            "source": "TCMB",
            "note": "Kurlar TCMB gösterge niteliğindedir. Gerçek işlem kurları farklılık gösterebilir.",
        },
    }



