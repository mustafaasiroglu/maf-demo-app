"""
TEFAS fund price history provider.

Fetches historical fund prices from the TEFAS (Türkiye Elektronik Fon Alım Satım Platformu) API.
Automatically splits date ranges longer than 60 days into multiple requests and merges results.

API endpoint:
  https://www.tefas.gov.tr/api/DB/BindHistoryInfo
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
import requests
import threading

logger = logging.getLogger(__name__)

TEFAS_API_URL = "https://www.tefas.gov.tr/api/DB/BindHistoryInfo"
MAX_DAYS_PER_REQUEST = 60
MAX_RETRIES = 3
RETRY_DELAY = 3  # seconds

# ── In-memory cache (5 min TTL) ─────────────────────────────────
CACHE_TTL_SECONDS = 5 * 60
_cache: Dict[str, Dict[str, Any]] = {}   # key → {"data": ..., "ts": float}
_cache_lock = threading.Lock()

TEFAS_HEADERS = {
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def _parse_date(date_str: str) -> datetime:
    """Parse a date string in DD.MM.YYYY or YYYY-MM-DD format."""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Tarih formatı geçersiz: {date_str}. DD.MM.YYYY veya YYYY-MM-DD kullanın.")


def _fetch_tefas_chunk(
    fund_code: str,
    start_date: datetime,
    end_date: datetime,
) -> List[Dict[str, Any]]:
    """
    Fetch a single chunk (≤60 days) from TEFAS API with retries.

    Returns a list of cleaned price records.
    """
    params = {
        "fontip": "YAT",
        "sfontur": "",
        "fonkod": fund_code.upper(),
        "fongrup": "",
        "bastarih": start_date.strftime("%d.%m.%Y"),
        "bittarih": end_date.strftime("%d.%m.%Y"),
        "fonturkod": "",
        "fonunvantip": "",
        "kurucukod": "",
    }

    import time

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(TEFAS_API_URL, data=params, headers=TEFAS_HEADERS, timeout=30)

            if resp.status_code != 200:
                logger.warning(
                    "TEFAS HTTP %s for %s, attempt %d/%d",
                    resp.status_code, fund_code, attempt, MAX_RETRIES,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                return []

            result = resp.json()
            raw_data = result.get("data", [])

            if not raw_data:
                logger.warning(
                    "TEFAS returned empty data for %s (%s - %s), attempt %d/%d",
                    fund_code,
                    start_date.strftime("%d.%m.%Y"),
                    end_date.strftime("%d.%m.%Y"),
                    attempt,
                    MAX_RETRIES,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                return []

            cleaned: List[Dict[str, Any]] = []
            for item in raw_data:
                try:
                    ts = int(item["TARIH"]) / 1000
                    cleaned.append({
                        "tarih": datetime.fromtimestamp(ts).strftime("%d.%m.%Y"),
                        "fiyat": item.get("FIYAT"),
                        "tedavuldeki_pay": item.get("TEDPAYSAYISI"),
                        "yatirimci_sayisi": item.get("KISISAYISI"),
                        "portfoy_buyukluk": item.get("PORTFOYBUYUKLUK"),
                    })
                except (KeyError, TypeError, ValueError) as exc:
                    logger.debug("Skipping malformed TEFAS record: %s", exc)
                    continue

            return cleaned

        except requests.exceptions.JSONDecodeError:
            logger.warning("Invalid JSON from TEFAS for %s, attempt %d/%d", fund_code, attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
            return []

        except requests.exceptions.RequestException as exc:
            logger.warning("Request error for %s: %s, attempt %d/%d", fund_code, exc, attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
            return []

    return []


def _split_date_range(start: datetime, end: datetime) -> List[tuple]:
    """Split a date range into chunks of at most MAX_DAYS_PER_REQUEST days."""
    chunks = []
    current_start = start
    while current_start <= end:
        current_end = min(current_start + timedelta(days=MAX_DAYS_PER_REQUEST - 1), end)
        chunks.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    return chunks


def get_fund_price_history(
    fund_code: str,
    start_date: str,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Get historical price data for a fund from TEFAS.

    Results are cached in-memory for 5 minutes so that duplicate calls
    (e.g. LLM tool call followed by frontend chart request) hit the cache.

    If the date range exceeds 60 days, the request is automatically split into
    multiple chunks and the results are merged in chronological order.

    Args:
        fund_code: Fund code (e.g. "GTA", "GOL", "GTL").
        start_date: Start date in DD.MM.YYYY or YYYY-MM-DD format.
        end_date: End date in DD.MM.YYYY or YYYY-MM-DD format. Defaults to today.

    Returns:
        Dictionary with price history data and metadata.
    """
    # ── Cache lookup ──
    import time as _time
    cache_key = f"{fund_code.strip().upper()}|{start_date}|{end_date or ''}"
    with _cache_lock:
        entry = _cache.get(cache_key)
        if entry and (_time.time() - entry["ts"]) < CACHE_TTL_SECONDS:
            logger.info("Cache HIT for %s (key=%s)", fund_code.upper(), cache_key)
            return entry["data"]

    # ── Cache miss → fetch from TEFAS ──
    result = _get_fund_price_history_uncached(fund_code, start_date, end_date)

    # Only cache successful results (found or not-found, but not errors)
    with _cache_lock:
        _cache[cache_key] = {"data": result, "ts": _time.time()}

    return result


def _get_fund_price_history_uncached(
    fund_code: str,
    start_date: str,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Fetch from TEFAS (no cache). Called by get_fund_price_history."""
    exec_start = datetime.now()

    try:
        start_dt = _parse_date(start_date)
        end_dt = _parse_date(end_date) if end_date else datetime.now()

        if start_dt > end_dt:
            return {
                "type": "tool_result",
                "data": {
                    "found": False,
                    "message": "Başlangıç tarihi bitiş tarihinden sonra olamaz.",
                },
                "debug": {
                    "tool_name": "get_fund_price_history",
                    "fund_code": fund_code,
                    "result": "error",
                },
            }

        total_days = (end_dt - start_dt).days
        chunks = _split_date_range(start_dt, end_dt)

        logger.info(
            "Fetching TEFAS price history for %s: %s → %s (%d days, %d chunk(s))",
            fund_code.upper(),
            start_dt.strftime("%d.%m.%Y"),
            end_dt.strftime("%d.%m.%Y"),
            total_days,
            len(chunks),
        )

        all_records: List[Dict[str, Any]] = []
        for chunk_start, chunk_end in chunks:
            records = _fetch_tefas_chunk(fund_code, chunk_start, chunk_end)
            all_records.extend(records)

        # Deduplicate by date (in case chunks overlap) and sort chronologically
        seen_dates: set = set()
        unique_records: List[Dict[str, Any]] = []
        for rec in all_records:
            if rec["tarih"] not in seen_dates:
                seen_dates.add(rec["tarih"])
                unique_records.append(rec)

        # Sort by date ascending
        unique_records.sort(
            key=lambda r: datetime.strptime(r["tarih"], "%d.%m.%Y")
        )

        execution_time = (datetime.now() - exec_start).total_seconds() * 1000

        if not unique_records:
            return {
                "type": "tool_result",
                "data": {
                    "found": False,
                    "fund_code": fund_code.upper(),
                    "message": f"{fund_code.upper()} fonu için {start_dt.strftime('%d.%m.%Y')} - {end_dt.strftime('%d.%m.%Y')} tarih aralığında veri bulunamadı.",
                },
                "debug": {
                    "tool_name": "get_fund_price_history",
                    "fund_code": fund_code.upper(),
                    "start_date": start_dt.strftime("%d.%m.%Y"),
                    "end_date": end_dt.strftime("%d.%m.%Y"),
                    "total_days": total_days,
                    "chunks": len(chunks),
                    "execution_time_ms": execution_time,
                    "result": "not_found",
                },
            }

        # Compute summary statistics
        prices = [r["fiyat"] for r in unique_records if r.get("fiyat") is not None]
        first_price = prices[0] if prices else None
        last_price = prices[-1] if prices else None
        change_pct = (
            round((last_price - first_price) / first_price * 100, 2)
            if first_price and last_price and first_price != 0
            else None
        )

        return {
            "type": "tool_result",
            "data": {
                "found": True,
                "fund_code": fund_code.upper(),
                "start_date": start_dt.strftime("%d.%m.%Y"),
                "end_date": end_dt.strftime("%d.%m.%Y"),
                "total_days": total_days,
                "record_count": len(unique_records),
                "summary": {
                    "first_price": first_price,
                    "last_price": last_price,
                    "min_price": min(prices) if prices else None,
                    "max_price": max(prices) if prices else None,
                    "change_percent": change_pct,
                },
                "prices": unique_records,
            },
            "debug": {
                "tool_name": "get_fund_price_history",
                "fund_code": fund_code.upper(),
                "start_date": start_dt.strftime("%d.%m.%Y"),
                "end_date": end_dt.strftime("%d.%m.%Y"),
                "total_days": total_days,
                "chunks": len(chunks),
                "execution_time_ms": execution_time,
                "result": "success",
            },
        }

    except ValueError as exc:
        execution_time = (datetime.now() - exec_start).total_seconds() * 1000
        return {
            "type": "tool_result",
            "data": {
                "found": False,
                "message": str(exc),
            },
            "debug": {
                "tool_name": "get_fund_price_history",
                "fund_code": fund_code,
                "execution_time_ms": execution_time,
                "result": "error",
                "error": str(exc),
            },
        }

    except Exception as exc:
        execution_time = (datetime.now() - exec_start).total_seconds() * 1000
        logger.exception("Unexpected error fetching TEFAS price history for %s", fund_code)
        return {
            "type": "tool_result",
            "data": {
                "found": False,
                "message": f"Fiyat geçmişi alınırken hata oluştu: {str(exc)}",
            },
            "debug": {
                "tool_name": "get_fund_price_history",
                "fund_code": fund_code,
                "execution_time_ms": execution_time,
                "result": "error",
                "error": str(exc),
            },
        }
