from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json

# Dummy fund knowledge base
FUND_DATABASE = {
    "GTA": {
        "fund_code": "GTA",
        "fund_name": "Garanti Teknoloji A Tipi Fon",
        "fund_name_en": "Garanti Technology Type A Fund",
        "description": "Garanti Teknoloji A Tipi Fon, yerli ve yabancı teknoloji şirketlerinin hisse senetlerine yatırım yapan bir A tipi fonudur. Fon, yüksek büyüme potansiyeline sahip teknoloji şirketlerini portföyüne alarak yatırımcılara uzun vadede değer katmayı hedefler.",
        "risk_level": "Yüksek",
        "risk_score": 7,
        "category": "Hisse Senedi Fonu",
        "inception_date": "2020-03-15",
        "fund_manager": "Garanti Portföy Yönetimi A.Ş.",
        "management_fee": "2.5%",
        "total_value": "₺125,000,000",
        "returns": {
            "1_day": 0.35,
            "1_week": 2.8,
            "1_month": 5.2,
            "3_months": 12.5,
            "6_months": 18.3,
            "1_year": 35.7,
            "ytd": 4.8
        },
        "top_holdings": [
            {"name": "Microsoft", "weight": "12.5%"},
            {"name": "Apple", "weight": "11.2%"},
            {"name": "NVIDIA", "weight": "10.8%"},
            {"name": "Aselsan", "weight": "8.5%"},
            {"name": "Vestel", "weight": "6.3%"}
        ]
    },
    "GOL": {
        "fund_code": "GOL",
        "fund_name": "Garanti Ons Altın Fonu",
        "fund_name_en": "Garanti Ounce Gold Fund",
        "description": "Garanti Ons Altın Fonu, portföyünü ağırlıklı olarak altın ve değerli madenler üzerinden değerlendiren bir fondur. Enflasyona karşı koruma sağlamak ve değer koruma amaçlı yatırımcılara hitap eder.",
        "risk_level": "Orta",
        "risk_score": 5,
        "category": "Değerli Madenler Fonu",
        "inception_date": "2018-06-20",
        "fund_manager": "Garanti Portföy Yönetimi A.Ş.",
        "management_fee": "1.5%",
        "total_value": "₺250,000,000",
        "returns": {
            "1_day": 0.15,
            "1_week": 1.2,
            "1_month": 3.5,
            "3_months": 8.2,
            "6_months": 15.8,
            "1_year": 28.5,
            "ytd": 3.2
        },
        "top_holdings": [
            {"name": "Fiziki Altın", "weight": "85.0%"},
            {"name": "Altın Vadeli İşlemler", "weight": "10.0%"},
            {"name": "Gümüş", "weight": "3.0%"},
            {"name": "Nakit", "weight": "2.0%"}
        ]
    },
    "GTL": {
        "fund_code": "GTL",
        "fund_name": "Garanti Likit Fon",
        "fund_name_en": "Garanti Liquid Fund",
        "description": "Garanti Likit Fon, kısa vadeli para piyasası araçlarına yatırım yaparak yatırımcılara yüksek likidite ve düşük risk ile getiri sağlamayı hedefleyen bir fondur. Günlük nakit ihtiyaçları için ideal bir yatırım aracıdır.",
        "risk_level": "Düşük",
        "risk_score": 2,
        "category": "Likit Fon",
        "inception_date": "2015-01-10",
        "fund_manager": "Garanti Portföy Yönetimi A.Ş.",
        "management_fee": "0.5%",
        "total_value": "₺500,000,000",
        "returns": {
            "1_day": 0.08,
            "1_week": 0.5,
            "1_month": 2.1,
            "3_months": 6.5,
            "6_months": 13.2,
            "1_year": 26.8,
            "ytd": 2.0
        },
        "top_holdings": [
            {"name": "Devlet Tahvili", "weight": "45.0%"},
            {"name": "Hazine Bonosu", "weight": "35.0%"},
            {"name": "Banka Bonosu", "weight": "15.0%"},
            {"name": "Nakit", "weight": "5.0%"}
        ]
    }
}

def search_fund_info(fund_name: str, query_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for fund information in the knowledge base.
    
    Args:
        fund_name: Fund code or name to search (e.g., "GTA", "GOL", "GTL")
        query_type: Optional specific query type (e.g., "risk", "returns", "description")
    
    Returns:
        Dictionary containing fund information and debug metadata
    """
    start_time = datetime.now()
    
    # Normalize fund name to uppercase for matching
    fund_code = fund_name.upper().strip()
    
    # Try to find exact match or partial match
    fund_data = None
    for code, data in FUND_DATABASE.items():
        if code == fund_code or code in fund_code or fund_code in data["fund_name"].upper():
            fund_data = data
            fund_code = code
            break
    
    if not fund_data:
        # Return all fund codes if no match found
        return {
            "type": "tool_result",
            "data": {
                "found": False,
                "message": f"Fon bulunamadı: {fund_name}",
                "available_funds": list(FUND_DATABASE.keys()),
                "suggestion": "Lütfen GTA, GOL veya GTL fon kodlarından birini deneyin."
            },
            "debug": {
                "tool_name": "search_fund_info",
                "query": fund_name,
                "query_type": query_type,
                "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "result": "not_found"
            }
        }
    
    # Filter response based on query type if specified
    if query_type:
        query_type_lower = query_type.lower()
        if "risk" in query_type_lower:
            filtered_data = {
                "fund_code": fund_data["fund_code"],
                "fund_name": fund_data["fund_name"],
                "risk_level": fund_data["risk_level"],
                "risk_score": fund_data["risk_score"],
                "description": fund_data["description"]
            }
        elif "return" in query_type_lower or "getiri" in query_type_lower or "performan" in query_type_lower:
            filtered_data = {
                "fund_code": fund_data["fund_code"],
                "fund_name": fund_data["fund_name"],
                "returns": fund_data["returns"]
            }
        elif "holding" in query_type_lower or "portföy" in query_type_lower:
            filtered_data = {
                "fund_code": fund_data["fund_code"],
                "fund_name": fund_data["fund_name"],
                "top_holdings": fund_data["top_holdings"]
            }
        else:
            filtered_data = fund_data
    else:
        filtered_data = fund_data
    
    execution_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return {
        "type": "tool_result",
        "data": {
            "found": True,
            "fund": filtered_data
        },
        "debug": {
            "tool_name": "search_fund_info",
            "query": fund_name,
            "query_type": query_type,
            "matched_fund_code": fund_code,
            "execution_time_ms": execution_time,
            "result": "success"
        }
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
    
    comparison_data = []
    for code in fund_codes:
        result = search_fund_info(code)
        if result["data"]["found"]:
            comparison_data.append(result["data"]["fund"])
    
    if not comparison_data:
        return {
            "type": "tool_result",
            "data": {
                "found": False,
                "message": "Karşılaştırmak için geçerli fon bulunamadı."
            },
            "debug": {
                "tool_name": "compare_funds",
                "fund_codes": fund_codes,
                "metric": metric,
                "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "result": "not_found"
            }
        }
    
    execution_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return {
        "type": "tool_result",
        "data": {
            "found": True,
            "comparison": comparison_data,
            "metric": metric,
            "funds_compared": len(comparison_data)
        },
        "debug": {
            "tool_name": "compare_funds",
            "fund_codes": fund_codes,
            "metric": metric,
            "execution_time_ms": execution_time,
            "result": "success"
        }
    }

def list_all_funds(sort_by: str = "returns_1_week") -> Dict[str, Any]:
    """
    List all available funds, optionally sorted by a metric.
    
    Args:
        sort_by: Metric to sort by (e.g., "returns_1_week", "risk_score", "total_value")
    
    Returns:
        Dictionary containing all funds and debug metadata
    """
    start_time = datetime.now()
    
    funds = list(FUND_DATABASE.values())
    
    # Sort if requested
    if "return" in sort_by.lower() and "1_week" in sort_by:
        funds.sort(key=lambda x: x["returns"]["1_week"], reverse=True)
    elif "risk" in sort_by.lower():
        funds.sort(key=lambda x: x["risk_score"])
    
    execution_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return {
        "type": "tool_result",
        "data": {
            "funds": funds,
            "total_funds": len(funds),
            "sorted_by": sort_by
        },
        "debug": {
            "tool_name": "list_all_funds",
            "sort_by": sort_by,
            "execution_time_ms": execution_time,
            "result": "success"
        }
    }
