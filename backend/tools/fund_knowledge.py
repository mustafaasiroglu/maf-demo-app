"""
Fund knowledge tool backed by Azure AI Search (funds_index).

Environment variables required:
  AZURE_SEARCH_ENDPOINT  – e.g. https://<service>.search.windows.net
  AZURE_SEARCH_API_KEY   – Admin or Query API key
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import os
import json
import requests

# ── Azure AI Search configuration ────────────────────────────────────────────
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")
INDEX_NAME = "funds_index"
API_VERSION = "2024-07-01"

HEADERS = {
    "Content-Type": "application/json",
    "api-key": SEARCH_API_KEY or "",
}

DEFAULT_FIELDS = [
    "code",
    "title_tr",
    "title_en",
    "category_tr",
    "category_en",
    "alias_tr",
    "alias_en",
    "first_offering_date",
    "annual_management_fee",
    "risk_level",
    "compare_measure",
    "taxation",
    "trading_terms",
    "investment_strategy",
    "investor_profile",
    "pdf_url",
    "is_recommended",
    "latest_price_close",
    "latest_price_date",
    "net_asset_value",
    "distribution_json",
    "return_weekly",
    "return_one_month",
    "return_three_month",
    "return_six_month",
    "return_from_begin_of_year",
    "return_one_year",
    "return_three_year",
    "return_first_offering_date",
    "documents_json",
]


def _query_search_index(
    query: str,
    *,
    search_fields: Optional[List[str]] = None,
    top: int = 5,
    filters: Optional[str] = None,
    fields: Optional[List[str]] = None,
) -> List[dict]:
    """
    Low-level helper that posts a search request to Azure AI Search.

    Returns the list of matching documents (value array).
    Raises on HTTP errors.
    """
    if not SEARCH_ENDPOINT or not SEARCH_API_KEY:
        raise ValueError(
            "Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY environment variables."
        )

    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version={API_VERSION}"

    body: Dict[str, Any] = {
        "search": query,
        "top": top,
        "count": True,
    }
    if filters:
        body["filter"] = filters
    if fields:
        body["select"] = ",".join(fields)
    if search_fields:
        body["searchFields"] = ",".join(search_fields)

    resp = requests.post(url, headers=HEADERS, json=body)
    resp.raise_for_status()

    data = resp.json()
    return data.get("value", [])


# Fields returned for search results (basic overview)
SEARCH_RESULT_FIELDS = [
    "code",
    "title_tr",
    "category_tr",
    "latest_price_close",
    "latest_price_date",
    "risk_level",
    "distribution_json",
    "return_weekly",
    "return_one_month",
    "return_three_month",
    "return_six_month",
    "return_from_begin_of_year",
    "return_one_year",
    "return_three_year",
    "return_first_offering_date",
    "is_recommended",
    "investment_strategy",
    "investor_profile",
    "documents_json",
]

# ── Public tool functions ────────────────────────────────────────────────────


def search_funds(search_query: str) -> Dict[str, Any]:
    """
    Search for investment funds in Azure AI Search and return basic details.

    Args:
        search_query: Free-text query to search (e.g., "altın", "teknoloji", "likit")

    Returns:
        Dictionary containing a list of matching funds with basic details.
    """
    start_time = datetime.now()

    try:
        # Try exact code filter first
        query_upper = search_query.strip().upper()
        results = _query_search_index(
            "*",
            filters=f"code eq '{query_upper}'",
            top=1,
            fields=SEARCH_RESULT_FIELDS,
        )

        # If no exact match, do a full-text search
        if not results:
            results = _query_search_index(
                search_query,
                search_fields=["title_tr", "title_en", "category_tr", "category_en", "investment_strategy", "investor_profile"],
                top=5,
                fields=SEARCH_RESULT_FIELDS,
            )

        # Strip search metadata
        for doc in results:
            doc.pop("@search.score", None)

        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        if not results:
            all_funds = _query_search_index("*", top=50, fields=["code", "title_tr"])
            available = [{"code": f.get("code", ""), "title_tr": f.get("title_tr", "")} for f in all_funds if f.get("code")]
            return {
                "type": "tool_result",
                "data": {
                    "found": False,
                    "message": f"Fon bulunamadı: {search_query}",
                    "available_funds": available[:20],
                    "suggestion": "Lütfen geçerli bir fon kodu veya anahtar kelime deneyin.",
                },
                "debug": {
                    "tool_name": "search_funds",
                    "query": search_query,
                    "execution_time_ms": execution_time,
                    "result": "not_found",
                },
            }

        return {
            "type": "tool_result",
            "data": {
                "found": True,
                "funds": results,
                "total_results": len(results),
            },
            "debug": {
                "tool_name": "search_funds",
                "query": search_query,
                "execution_time_ms": execution_time,
                "result": "success",
            },
        }

    except Exception as exc:
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        return {
            "type": "tool_result",
            "data": {
                "found": False,
                "message": f"Arama sırasında hata oluştu: {str(exc)}",
            },
            "debug": {
                "tool_name": "search_funds",
                "query": search_query,
                "execution_time_ms": execution_time,
                "result": "error",
                "error": str(exc),
            },
        }


def get_fund_details(fund_code: str) -> Dict[str, Any]:
    """
    Get full details for a specific fund by its fund code.

    Args:
        fund_code: The fund code (e.g., "GTA", "GOL", "GTL")

    Returns:
        Dictionary containing all available fund details.
    """
    start_time = datetime.now()

    try:
        fund_code_upper = fund_code.strip().upper()
        results = _query_search_index(
            "*",
            filters=f"code eq '{fund_code_upper}'",
            top=1,
            fields=DEFAULT_FIELDS,
        )

        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        if not results:
            all_funds = _query_search_index("*", top=50, fields=["code"])
            available_codes = [f.get("code", "") for f in all_funds if f.get("code")]
            return {
                "type": "tool_result",
                "data": {
                    "found": False,
                    "message": f"Fon bulunamadı: {fund_code}",
                    "available_funds": available_codes[:20],
                    "suggestion": "Lütfen geçerli bir fon kodu deneyin.",
                },
                "debug": {
                    "tool_name": "get_fund_details",
                    "fund_code": fund_code,
                    "execution_time_ms": execution_time,
                    "result": "not_found",
                },
            }

        fund_data = results[0]
        fund_data.pop("@search.score", None)

        return {
            "type": "tool_result",
            "data": {
                "found": True,
                "fund": fund_data,
            },
            "debug": {
                "tool_name": "get_fund_details",
                "fund_code": fund_code,
                "matched_fund_code": fund_data.get("code", ""),
                "execution_time_ms": execution_time,
                "result": "success",
            },
        }

    except Exception as exc:
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        return {
            "type": "tool_result",
            "data": {
                "found": False,
                "message": f"Fon detayları alınırken hata oluştu: {str(exc)}",
            },
            "debug": {
                "tool_name": "get_fund_details",
                "fund_code": fund_code,
                "execution_time_ms": execution_time,
                "result": "error",
                "error": str(exc),
            },
        }


def compare_funds(fund_codes: List[str], metric: str = "returns") -> Dict[str, Any]:
    """
    Compare multiple funds based on a specific metric.

    Args:
        fund_codes: List of fund codes to compare
        metric: Metric to compare (e.g., "returns", "risk", "fees")

    Returns:
        Dictionary containing comparison data and debug metadata
    """
    start_time = datetime.now()

    # Build an OData filter for all requested fund codes
    filter_clauses = " or ".join(
        f"code eq '{code.strip().upper()}'" for code in fund_codes
    )

    try:
        results = _query_search_index(
            "*",
            filters=filter_clauses,
            top=len(fund_codes),
            fields=DEFAULT_FIELDS,
        )

        # Strip search metadata
        for doc in results:
            doc.pop("@search.score", None)

        execution_time = (datetime.now() - start_time).total_seconds() * 1000

        if not results:
            return {
                "type": "tool_result",
                "data": {
                    "found": False,
                    "message": "Karşılaştırmak için geçerli fon bulunamadı.",
                },
                "debug": {
                    "tool_name": "compare_funds",
                    "fund_codes": fund_codes,
                    "metric": metric,
                    "execution_time_ms": execution_time,
                    "result": "not_found",
                },
            }

        return {
            "type": "tool_result",
            "data": {
                "found": True,
                "comparison": results,
                "metric": metric,
                "funds_compared": len(results),
            },
            "debug": {
                "tool_name": "compare_funds",
                "fund_codes": fund_codes,
                "metric": metric,
                "execution_time_ms": execution_time,
                "result": "success",
            },
        }

    except Exception as exc:
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        return {
            "type": "tool_result",
            "data": {
                "found": False,
                "message": f"Karşılaştırma sırasında hata oluştu: {str(exc)}",
            },
            "debug": {
                "tool_name": "compare_funds",
                "fund_codes": fund_codes,
                "metric": metric,
                "execution_time_ms": execution_time,
                "result": "error",
                "error": str(exc),
            },
        }



