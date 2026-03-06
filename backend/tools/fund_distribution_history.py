"""
TEFAS fund distribution (allocation) history provider.

Fetches historical asset-allocation breakdowns from the TEFAS API.
Automatically splits date ranges longer than 60 days into multiple requests and merges results.

API endpoint:
  https://www.tefas.gov.tr/api/DB/BindHistoryAllocation
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
import threading
import time as _time
import requests

logger = logging.getLogger(__name__)

TEFAS_ALLOC_URL = "https://www.tefas.gov.tr/api/DB/BindHistoryAllocation"
MAX_DAYS_PER_REQUEST = 60
MAX_RETRIES = 3
RETRY_DELAY = 3  # seconds

TEFAS_HEADERS = {
    "Origin": "https://www.tefas.gov.tr",
    "Referer": "https://www.tefas.gov.tr/TarihselVeriler.aspx",
    "X-Requested-With": "XMLHttpRequest",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# ── Field code → human-readable Turkish label mapping ────────────
FIELD_LABELS: Dict[str, str] = {
    "HS": "Hisse Senedi",
    "DT": "Devlet Tahvili",
    "HB": "Hazine Bonosu",
    "GYY": "Gayrimenkul Yatırımları",
    "GSYY": "Girişim Sermayesi Yatırımları",
    "KİBD": "Döviz Kamu İç Borçlanma Araçları",
    "DB": "Döviz Ödemeli Bono",
    "DÖT": "Dövize Ödemeli Tahvil",
    "FB": "Finansman Bonosu",
    "OST": "Özel Sektör Tahvili",
    "BB": "Banka Bonosu",
    "VDM": "Varlığa Dayalı Menkul Kıymetler",
    "GAS": "Gayrimenkul Sertifikası",
    "EUT": "Eurobonds",
    "KBA": "Kamu Dış Borçlanma Araçları",
    "ÖSDB": "Özel Sektör Dış Borç. Araçları",
    "TPP": "Takasbank Para Piyasası",
    "KKS": "Kamu Kira Sertifikaları",
    "KKSTL": "Kamu Kira Sertifikaları (TL)",
    "KKSD": "Kamu Kira Sertifikaları (Döviz)",
    "OSKS": "Özel Sektör Kira Sertifikaları",
    "KKSYD": "Kamu Yurt Dışı Kira Sertifikaları",
    "ÖKSYD": "Ö.S. Yurt Dışı Kira Sertifikaları",
    "VM": "Vadeli Mevduat",
    "VMTL": "Mevduat (TL)",
    "VMD": "Mevduat (Döviz)",
    "VMAU": "Mevduat (Altın)",
    "KH": "Katılım Hesabı",
    "KHTL": "Katılma Hesabı (TL)",
    "KHD": "Katılma Hesabı (Döviz)",
    "KHAU": "Katılma Hesabı (Altın)",
    "R": "Repo",
    "TR": "Ters-Repo",
    "BTAA": "BİST Taahhütlü İşlem Pazarı Alım",
    "BTAS": "BİST Taahhütlü İşlem Pazarı Satım",
    "KM": "Kıymetli Madenler",
    "KMBYF": "Kıymetli Madenler Cinsinden BYF",
    "KMKBA": "Kıymetli Madenler Kamu B.A.",
    "KMKKS": "Kıymetli Madenler Kamu Kira Sertifika.",
    "YMK": "Yabancı Menkul Kıymet",
    "YBA": "Yabancı Borçlanma Aracı",
    "YBKB": "Yabancı Kamu Borçlanma Araçları",
    "YBOSB": "Yabancı Özel Sektör B.A.",
    "YHS": "Yabancı Hisse Senedi",
    "YBYF": "Yabancı Borsa Yatırım Fonları",
    "FKB": "Fon Katılma Belgesi",
    "YYF": "Yatırım Fonları Katılma Payları",
    "BYF": "BYF Katılma Payları",
    "GYKB": "Gayrimenkul Yatırım Fon Katılma Payları",
    "GSYKB": "Girişim S. Yatırım Fon Katılma Payları",
    "T": "Türev Araçları",
    "VİNT": "Vadeli İşlemler Nakit Teminatları",
    "D": "Diğer",
    "BPP": "Borsa İstanbul Para Piyasası",
}

# All allocation field codes (used when cleaning raw data)
ALLOC_FIELDS = list(FIELD_LABELS.keys())

# ── In-memory cache (5 min TTL) ─────────────────────────────────
CACHE_TTL_SECONDS = 5 * 60
_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = threading.Lock()


def _parse_date(date_str: str) -> datetime:
    """Parse a date string in DD.MM.YYYY or YYYY-MM-DD format."""
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Tarih formatı geçersiz: {date_str}. DD.MM.YYYY veya YYYY-MM-DD kullanın.")


def _split_date_range(start: datetime, end: datetime) -> List[tuple]:
    """Split a date range into chunks of at most MAX_DAYS_PER_REQUEST days."""
    chunks = []
    current_start = start
    while current_start <= end:
        current_end = min(current_start + timedelta(days=MAX_DAYS_PER_REQUEST - 1), end)
        chunks.append((current_start, current_end))
        current_start = current_end + timedelta(days=1)
    return chunks


def _fetch_alloc_chunk(
    fund_code: str,
    start_date: datetime,
    end_date: datetime,
) -> List[Dict[str, Any]]:
    """Fetch a single chunk (≤60 days) from BindHistoryAllocation with retries."""
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
            resp = requests.post(TEFAS_ALLOC_URL, data=params, headers=TEFAS_HEADERS, timeout=30)

            if resp.status_code != 200:
                logger.warning(
                    "TEFAS alloc HTTP %s for %s, attempt %d/%d",
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
                    "TEFAS alloc returned empty data for %s (%s - %s), attempt %d/%d",
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
                    record: Dict[str, Any] = {
                        "tarih": datetime.fromtimestamp(ts).strftime("%d.%m.%Y"),
                    }
                    # Collect only non-null allocation fields
                    for field in ALLOC_FIELDS:
                        val = item.get(field)
                        if val is not None:
                            record[field] = val
                    cleaned.append(record)
                except (KeyError, TypeError, ValueError) as exc:
                    logger.debug("Skipping malformed TEFAS alloc record: %s", exc)
                    continue

            return cleaned

        except requests.exceptions.JSONDecodeError:
            logger.warning("Invalid JSON from TEFAS alloc for %s, attempt %d/%d", fund_code, attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
            return []

        except requests.exceptions.RequestException as exc:
            logger.warning("Request error for %s alloc: %s, attempt %d/%d", fund_code, exc, attempt, MAX_RETRIES)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
            return []

    return []


def get_distribution_history(
    fund_code: str,
    start_date: str,
    end_date: Optional[str] = None,
    include_history: bool = False,
) -> Dict[str, Any]:
    """
    Get asset-allocation data for a fund from TEFAS (cached for 5 min).

    By default returns only the latest date's allocation snapshot.
    Set include_history=True to get all dates in the range.

    Args:
        fund_code: Fund code (e.g. "GTZ", "GTA").
        start_date: Start date in DD.MM.YYYY or YYYY-MM-DD format.
        end_date: End date. Defaults to today.
        include_history: If True, return allocations for all dates in range.

    Returns:
        Dictionary with allocation data and metadata.
    """
    cache_key = f"dist|{fund_code.strip().upper()}|{start_date}|{end_date or ''}|{'h' if include_history else 'l'}"
    with _cache_lock:
        entry = _cache.get(cache_key)
        if entry and (_time.time() - entry["ts"]) < CACHE_TTL_SECONDS:
            logger.info("Cache HIT for distribution %s (key=%s)", fund_code.upper(), cache_key)
            return entry["data"]

    result = _get_distribution_history_uncached(fund_code, start_date, end_date, include_history)

    with _cache_lock:
        _cache[cache_key] = {"data": result, "ts": _time.time()}

    return result


def _get_distribution_history_uncached(
    fund_code: str,
    start_date: str,
    end_date: Optional[str] = None,
    include_history: bool = False,
) -> Dict[str, Any]:
    """Fetch allocation from TEFAS (no cache)."""
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
                    "tool_name": "get_distribution_history",
                },
            }

        total_days = (end_dt - start_dt).days
        chunks = _split_date_range(start_dt, end_dt)

        logger.info(
            "Fetching TEFAS allocation history for %s: %s → %s (%d days, %d chunk(s))",
            fund_code.upper(),
            start_dt.strftime("%d.%m.%Y"),
            end_dt.strftime("%d.%m.%Y"),
            total_days,
            len(chunks),
        )

        all_records: List[Dict[str, Any]] = []
        for chunk_start, chunk_end in chunks:
            records = _fetch_alloc_chunk(fund_code, chunk_start, chunk_end)
            all_records.extend(records)

        # Deduplicate by date and sort chronologically
        seen_dates: set = set()
        unique_records: List[Dict[str, Any]] = []
        for rec in all_records:
            if rec["tarih"] not in seen_dates:
                seen_dates.add(rec["tarih"])
                unique_records.append(rec)

        unique_records.sort(key=lambda r: datetime.strptime(r["tarih"], "%d.%m.%Y"))

        execution_time = (datetime.now() - exec_start).total_seconds() * 1000

        if not unique_records:
            return {
                "type": "tool_result",
                "data": {
                    "found": False,
                    "fund_code": fund_code.upper(),
                    "message": f"{fund_code.upper()} fonu için {start_dt.strftime('%d.%m.%Y')} - {end_dt.strftime('%d.%m.%Y')} tarih aralığında dağılım verisi bulunamadı.",
                },
                "debug": {
                    "tool_name": "get_distribution_history",
                },
            }

        # Compute the latest allocation snapshot with labels
        latest = unique_records[-1]
        latest_allocation: List[Dict[str, Any]] = []
        for field in ALLOC_FIELDS:
            val = latest.get(field)
            if val is not None and val > 0:
                latest_allocation.append({
                    "code": field,
                    "label": FIELD_LABELS.get(field, field),
                    "percent": val,
                })
        latest_allocation.sort(key=lambda x: x["percent"], reverse=True)

        # Build response data
        data: Dict[str, Any] = {
            "found": True,
            "fund_code": fund_code.upper(),
            "start_date": start_dt.strftime("%d.%m.%Y"),
            "end_date": end_dt.strftime("%d.%m.%Y"),
            "total_days": total_days,
            "record_count": len(unique_records),
            "latest_date": latest["tarih"],
            "latest_allocation": latest_allocation,
        }

        # Only include full history when requested
        if include_history:
            data["allocations"] = unique_records

        return {
            "type": "tool_result",
            "data": data,
            "debug": {
                "tool_name": "get_distribution_history",
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
                "tool_name": "get_distribution_history",
                "fund_code": fund_code,
                "execution_time_ms": execution_time,
                "result": "error",
                "error": str(exc),
            },
        }

    except Exception as exc:
        execution_time = (datetime.now() - exec_start).total_seconds() * 1000
        logger.exception("Unexpected error fetching TEFAS allocation for %s", fund_code)
        return {
            "type": "tool_result",
            "data": {
                "found": False,
                "message": f"Dağılım verisi alınırken hata oluştu: {str(exc)}",
            },
            "debug": {
                "tool_name": "get_distribution_history",
                "fund_code": fund_code,
                "execution_time_ms": execution_time,
                "result": "error",
                "error": str(exc),
            },
        }
