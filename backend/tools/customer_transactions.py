from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from models.user import DUMMY_USER
import random

# Mock transaction database
def generate_mock_transactions(customer_id: str) -> List[Dict[str, Any]]:
    """Generate mock transaction history for a customer."""
    
    if customer_id != DUMMY_USER.customer_id:
        return []
    
    transactions = [
        {
            "transaction_id": "TXN_001",
            "date": "2023-01-20",
            "type": "BUY",
            "fund_code": "GTA",
            "fund_name": "Garanti Teknoloji A Tipi Fon",
            "units": 100.0,
            "price_per_unit": 11.50,
            "total_amount": 1150.00,
            "currency": "TRY",
            "status": "COMPLETED"
        },
        {
            "transaction_id": "TXN_002",
            "date": "2023-03-15",
            "type": "BUY",
            "fund_code": "GOL",
            "fund_name": "Garanti Ons Altın Fonu",
            "units": 50.0,
            "price_per_unit": 24.80,
            "total_amount": 1240.00,
            "currency": "TRY",
            "status": "COMPLETED"
        },
        {
            "transaction_id": "TXN_003",
            "date": "2023-06-10",
            "type": "BUY",
            "fund_code": "GTA",
            "fund_name": "Garanti Teknoloji A Tipi Fon",
            "units": 50.5,
            "price_per_unit": 14.20,
            "total_amount": 717.10,
            "currency": "TRY",
            "status": "COMPLETED"
        },
        {
            "transaction_id": "TXN_004",
            "date": "2023-09-22",
            "type": "BUY",
            "fund_code": "GOL",
            "fund_name": "Garanti Ons Altın Fonu",
            "units": 25.0,
            "price_per_unit": 26.00,
            "total_amount": 650.00,
            "currency": "TRY",
            "status": "COMPLETED"
        },
        {
            "transaction_id": "TXN_005",
            "date": "2024-01-15",
            "type": "SELL",
            "fund_code": "GTA",
            "fund_name": "Garanti Teknoloji A Tipi Fon",
            "units": 20.0,
            "price_per_unit": 15.80,
            "total_amount": 316.00,
            "currency": "TRY",
            "status": "COMPLETED",
            "profit_loss": 86.00,
            "profit_loss_percentage": 37.4
        },
        {
            "transaction_id": "TXN_006",
            "date": "2024-05-08",
            "type": "BUY",
            "fund_code": "GTL",
            "fund_name": "Garanti Likit Fon",
            "units": 200.0,
            "price_per_unit": 10.25,
            "total_amount": 2050.00,
            "currency": "TRY",
            "status": "COMPLETED"
        },
        {
            "transaction_id": "TXN_007",
            "date": "2024-08-12",
            "type": "SELL",
            "fund_code": "GTL",
            "fund_name": "Garanti Likit Fon",
            "units": 200.0,
            "price_per_unit": 11.10,
            "total_amount": 2220.00,
            "currency": "TRY",
            "status": "COMPLETED",
            "profit_loss": 170.00,
            "profit_loss_percentage": 8.3
        },
        {
            "transaction_id": "TXN_008",
            "date": "2025-11-20",
            "type": "BUY",
            "fund_code": "GTA",
            "fund_name": "Garanti Teknoloji A Tipi Fon",
            "units": 20.0,
            "price_per_unit": 11.90,
            "total_amount": 238.00,
            "currency": "TRY",
            "status": "COMPLETED"
        },
        {
            "transaction_id": "TXN_009",
            "date": "2026-01-10",
            "type": "DIVIDEND",
            "fund_code": "GOL",
            "fund_name": "Garanti Ons Altın Fonu",
            "units": 0.0,
            "price_per_unit": 0.0,
            "total_amount": 125.50,
            "currency": "TRY",
            "status": "COMPLETED",
            "description": "Fon temettü ödemesi"
        }
    ]
    
    return transactions

def get_customer_transactions(
    customer_id: Optional[str] = None,
    fund_code: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50
) -> Dict[str, Any]:
    """
    Get customer transaction history with optional filters.
    
    Args:
        customer_id: Customer ID (defaults to DUMMY_USER)
        fund_code: Filter by fund code (e.g., "GTA", "GOL")
        transaction_type: Filter by type (e.g., "BUY", "SELL", "DIVIDEND")
        start_date: Filter transactions after this date (YYYY-MM-DD)
        end_date: Filter transactions before this date (YYYY-MM-DD)
        limit: Maximum number of transactions to return
    
    Returns:
        Dictionary containing transaction history and debug metadata
    """
    start_time = datetime.now()
    
    # Use dummy user if no customer_id provided
    if not customer_id:
        customer_id = DUMMY_USER.customer_id
    
    # Get all transactions for customer
    all_transactions = generate_mock_transactions(customer_id)
    
    if not all_transactions:
        return {
            "type": "tool_result",
            "data": {
                "found": False,
                "message": f"Bu müşteri için işlem kaydı bulunamadı: {customer_id}",
                "customer_id": customer_id
            },
            "debug": {
                "tool_name": "get_customer_transactions",
                "customer_id": customer_id,
                "filters_applied": [],
                "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "result": "not_found"
            }
        }
    
    # Apply filters
    filtered_transactions = all_transactions
    filters_applied = []
    
    if fund_code:
        fund_code_upper = fund_code.upper()
        filtered_transactions = [t for t in filtered_transactions if t["fund_code"] == fund_code_upper]
        filters_applied.append(f"fund_code={fund_code_upper}")
    
    if transaction_type:
        transaction_type_upper = transaction_type.upper()
        filtered_transactions = [t for t in filtered_transactions if t["type"] == transaction_type_upper]
        filters_applied.append(f"type={transaction_type_upper}")
    
    if start_date:
        filtered_transactions = [t for t in filtered_transactions if t["date"] >= start_date]
        filters_applied.append(f"start_date={start_date}")
    
    if end_date:
        filtered_transactions = [t for t in filtered_transactions if t["date"] <= end_date]
        filters_applied.append(f"end_date={end_date}")
    
    # Apply limit
    filtered_transactions = filtered_transactions[:limit]
    
    # Calculate summary statistics
    total_buy_amount = sum(t["total_amount"] for t in filtered_transactions if t["type"] == "BUY")
    total_sell_amount = sum(t["total_amount"] for t in filtered_transactions if t["type"] == "SELL")
    total_profit_loss = sum(t.get("profit_loss", 0) for t in filtered_transactions if "profit_loss" in t)
    
    execution_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return {
        "type": "tool_result",
        "data": {
            "found": True,
            "customer_id": customer_id,
            "customer_name": DUMMY_USER.name,
            "transactions": filtered_transactions,
            "total_transactions": len(filtered_transactions),
            "summary": {
                "total_buy_amount": total_buy_amount,
                "total_sell_amount": total_sell_amount,
                "total_profit_loss": total_profit_loss,
                "total_dividend": sum(t["total_amount"] for t in filtered_transactions if t["type"] == "DIVIDEND")
            }
        },
        "debug": {
            "tool_name": "get_customer_transactions",
            "customer_id": customer_id,
            "filters_applied": filters_applied,
            "total_records_before_filter": len(all_transactions),
            "total_records_after_filter": len(filtered_transactions),
            "execution_time_ms": execution_time,
            "result": "success"
        }
    }

def get_customer_info(customer_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get customer information and current portfolio.
    
    Args:
        customer_id: Customer ID (defaults to DUMMY_USER)
    
    Returns:
        Dictionary containing customer information and debug metadata
    """
    start_time = datetime.now()
    
    # Use dummy user if no customer_id provided
    if not customer_id:
        customer_id = DUMMY_USER.customer_id
    
    if customer_id != DUMMY_USER.customer_id:
        return {
            "type": "tool_result",
            "data": {
                "found": False,
                "message": f"Müşteri bulunamadı: {customer_id}"
            },
            "debug": {
                "tool_name": "get_customer_info",
                "customer_id": customer_id,
                "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000,
                "result": "not_found"
            }
        }
    
    execution_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return {
        "type": "tool_result",
        "data": {
            "found": True,
            "customer": DUMMY_USER.to_dict()
        },
        "debug": {
            "tool_name": "get_customer_info",
            "customer_id": customer_id,
            "execution_time_ms": execution_time,
            "result": "success"
        }
    }
