from typing import Dict, List, Any
from datetime import datetime

class DummyUser:
    """Dummy user model for testing without authentication."""
    
    def __init__(self):
        self.customer_id = "123456789"
        self.name = "Mustafa Aşıroğlu"
        self.email = "mustafa.asiroglu@example.com"
        self.phone = "+90 555 123 4567"
        self.registration_date = "2023-01-15"
        self.portfolio = [
            {
                "fund_code": "GTA",
                "fund_name": "Garanti Teknoloji A Tipi Fon",
                "units": 150.5,
                "average_purchase_price": 12.45,
                "current_value": 1875.00,
                "last_updated": "2026-02-05"
            },
            {
                "fund_code": "GOL",
                "fund_name": "Garanti Ons Altın Fonu",
                "units": 75.0,
                "average_purchase_price": 25.30,
                "current_value": 1897.50,
                "last_updated": "2026-02-05"
            }
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user object to dictionary."""
        return {
            "customer_id": self.customer_id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "registration_date": self.registration_date,
            "portfolio": self.portfolio
        }
    
    def get_customer_info(self) -> str:
        """Get formatted customer information."""
        return f"""
Customer Information:
- Name: {self.name}
- Customer ID: {self.customer_id}
- Email: {self.email}
- Phone: {self.phone}
- Member Since: {self.registration_date}

Current Portfolio:
{self._format_portfolio()}
"""
    
    def _format_portfolio(self) -> str:
        """Format portfolio for display."""
        if not self.portfolio:
            return "No holdings"
        
        lines = []
        total_value = 0
        for holding in self.portfolio:
            lines.append(
                f"- {holding['fund_name']} ({holding['fund_code']}): "
                f"{holding['units']} units, Value: ₺{holding['current_value']:.2f}"
            )
            total_value += holding['current_value']
        
        lines.append(f"\nTotal Portfolio Value: ₺{total_value:.2f}")
        return "\n".join(lines)

# Global dummy user instance
DUMMY_USER = DummyUser()
