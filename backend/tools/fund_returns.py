"""
Fund returns provider via Garanti BBVA Portföy API.

Fetches fund return percentages (daily, weekly, monthly, yearly, YTD)
from the Garanti BBVA Portföy web service.

API endpoint:
  https://www.garantibbvaportfoy.com.tr/webservice/fundsreturns
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, date
import logging
import json
import time
import threading
import requests

logger = logging.getLogger(__name__)

API_URL = "https://www.garantibbvaportfoy.com.tr/webservice/fundsreturns"
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# ── In-memory cache (5 min TTL) ─────────────────────────────────
CACHE_TTL_SECONDS = 5 * 60
_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()


def _parse_date(date_str: str) -> str:
    """Parse a date string and return it in YYYY-MM-DD format."""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError(f"Tarih formatı geçersiz: {date_str}. DD.MM.YYYY veya YYYY-MM-DD kullanın.")


def _cache_key(funds: str, start_date: str, end_date: str) -> str:
    return f"{funds}|{start_date}|{end_date}"


def _get_cached(key: str) -> Optional[Any]:
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.time() - entry["ts"]) < CACHE_TTL_SECONDS:
            logger.info("Cache hit for fund_returns key: %s", key)
            return entry["data"]
        if entry:
            del _cache[key]
    return None


def _set_cached(key: str, data: Any) -> None:
    with _cache_lock:
        _cache[key] = {"data": data, "ts": time.time()}


def get_fund_returns(
    start_date: str,
    end_date: Optional[str] = None,
    funds: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fetch fund return data from Garanti BBVA Portföy API.

    Args:
        start_date: Start date in DD.MM.YYYY or YYYY-MM-DD format.
        end_date:   End date (defaults to today).
        funds:      Comma-separated fund codes (e.g. 'GOL' or 'GOL,GTA').
                    Empty string or None returns all funds.

    Returns:
        dict with fund names, codes, return percentages, and details.
    """
    start_iso = _parse_date(start_date)
    if end_date:
        end_iso = _parse_date(end_date)
    else:
        end_iso = date.today().strftime("%Y-%m-%d")

    funds_param = funds.strip().upper() if funds else ""

    # Check cache
    key = _cache_key(funds_param, start_iso, end_iso)
    cached = _get_cached(key)
    if cached is not None:
        return cached

    payload = {
        "lang": "tr",
        "fundType": "",
        "funds": funds_param,
        "startDate": start_iso,
        "endDate": end_iso,
    }

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)

            if resp.status_code != 200:
                logger.warning(
                    "Garanti API HTTP %s, attempt %d/%d",
                    resp.status_code, attempt, MAX_RETRIES,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                    continue
                return {"error": f"API HTTP {resp.status_code} hatası", "status": resp.status_code}

            # Response is a JSON string wrapped in quotes; parse twice if needed
            raw = resp.json()
            if isinstance(raw, str):
                raw = json.loads(raw)

            data = raw.get("data", raw)

            fund_codes = data.get("FundCodes", [])
            fund_names = data.get("FundNames", [])
            timelines = data.get("Timelines", {})
            fund_details = data.get("FundDetails", [])

            # Build a per-fund result list for easier consumption
            results: List[Dict[str, Any]] = []
            for i, code in enumerate(fund_codes):
                entry: Dict[str, Any] = {
                    "code": code,
                    "name": fund_names[i] if i < len(fund_names) else "",
                    "returns": {},
                }

                # Map timeline fields
                timeline_map = {
                    "daily": "Daily",
                    "weekly": "Weekly",
                    "monthly": "Monthly",
                    "yearly": "Yearly",
                    "ytd": "FromBeginOfYear",
                    "period": "D1D2Values",
                }
                for key_name, api_key in timeline_map.items():
                    values = timelines.get(api_key, [])
                    if i < len(values):
                        try:
                            entry["returns"][key_name] = round(float(values[i]), 4)
                        except (ValueError, TypeError):
                            entry["returns"][key_name] = values[i]

                # Attach fund detail info if available
                detail = next((d for d in fund_details if d.get("Code") == code), None)
                if detail:
                    entry["title"] = detail.get("Title", "")
                    entry["currency"] = detail.get("Currency", "TRY")

                results.append(entry)

            result = {
                "funds": results,
                "period": {"start": start_iso, "end": end_iso},
                "total_funds": len(results),
            }

            _set_cached(key, result)
            return result

        except requests.exceptions.Timeout:
            logger.warning("Garanti API timeout, attempt %d/%d", attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
        except requests.exceptions.RequestException as exc:
            logger.error("Garanti API request error: %s", exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                return {"error": f"API bağlantı hatası: {str(exc)}"}
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Garanti API parse error: %s", exc)
            return {"error": f"API yanıt ayrıştırma hatası: {str(exc)}"}

    return {"error": "API isteği başarısız oldu, lütfen tekrar deneyin."}
