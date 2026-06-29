from typing import Dict, List
import asyncio

# ────────────────────────────────────────────────────────────────
# Mock YONO 2.0 API Integration
# Simulates YONO 2.0 read-only APIs for transaction analysis.
# Uses asyncio Queue per customer (prevents race conditions).
# ────────────────────────────────────────────────────────────────

customer_queues: Dict[str, asyncio.Queue] = {}

# Mock YONO transaction database
_mock_yono_transactions: List[dict] = []

# Transaction categories for analysis
TRANSACTION_CATEGORIES = {
    "8299": "EDUCATION_TUITION",
    "8011": "MEDICAL",
    "5411": "GROCERY",
    "5812": "DINING",
    "5912": "PHARMACY",
    "5541": "FUEL",
    "7011": "RENT",
    "7832": "ENTERTAINMENT",
    "5999": "SHOPPING",
    "9311": "TAX",
    "9399": "GOVERNMENT",
}


class YONOError(Exception):
    """YONO API error."""
    pass


class YONOAPI:
    """Mock YONO 2.0 API adapter."""
    
    @staticmethod
    async def get_transactions(user_id: str, days: int = 30) -> List[dict]:
        """Get recent transactions for a user."""
        async with _customer_queue(user_id):
            # Return mock transactions
            return [
                {
                    "txn_id": f"YONO_{user_id[:4]}_{i:04d}",
                    "user_id": user_id,
                    "amount": 2500 + i * 100,
                    "category": "GROCERY" if i % 3 == 0 else "DINING" if i % 3 == 1 else "FUEL",
                    "mcc": "5411" if i % 3 == 0 else "5812" if i % 3 == 1 else "5541",
                    "timestamp": f"2026-06-{15-i:02d}T10:00:00Z",
                    "type": "debit"
                }
                for i in range(min(days, 30))
            ]
    
    @staticmethod
    async def analyze_spending_patterns(user_id: str) -> dict:
        """Analyze spending patterns for product recommendations."""
        async with _customer_queue(user_id):
            transactions = await YONOAPI.get_transactions(user_id, 90)
            
            # Calculate category totals
            category_totals = {}
            for t in transactions:
                cat = t["category"]
                category_totals[cat] = category_totals.get(cat, 0) + t["amount"]
            
            # Detect patterns
            patterns = []
            if category_totals.get("EDUCATION_TUITION", 0) > 10000:
                patterns.append("education_expense")
            if category_totals.get("RENT", 0) > 15000:
                patterns.append("rent_payment")
            if category_totals.get("MEDICAL", 0) > 5000:
                patterns.append("medical_expense")
            
            # Monthly average
            total_spend = sum(category_totals.values())
            monthly_avg = total_spend / 3
            
            return {
                "user_id": user_id,
                "total_90_day_spend": total_spend,
                "monthly_average": monthly_avg,
                "category_breakdown": category_totals,
                "detected_patterns": patterns,
                "recommendation_ready": len(patterns) > 0
            }
    
    @staticmethod
    async def get_product_holdings(user_id: str) -> dict:
        """Get current product holdings for cross-sell analysis."""
        async with _customer_queue(user_id):
            return {
                "user_id": user_id,
                "has_savings": True,
                "has_fd": False,
                "has_rd": False,
                "has_loan": False,
                "has_insurance": False,
                "has_credit_card": True,
                "digital_products": ["upi", "net_banking"]
            }
    
    @staticmethod
    async def get_salary_info(user_id: str) -> dict:
        """Get salary/income information."""
        async with _customer_queue(user_id):
            return {
                "user_id": user_id,
                "monthly_salary": 85000,
                "employer": "SBI_TECH_SOLUTIONS",
                "salary_credit_day": 1,
                "last_salary_date": "2026-06-01"
            }
    
    @staticmethod
    async def process_webhook(payload: dict) -> dict:
        """Process a YONO transaction webhook."""
        _mock_yono_transactions.append(payload)
        
        # Trigger analysis
        user_id = payload.get("user_id", "")
        if user_id:
            analysis = await YONOAPI.analyze_spending_patterns(user_id)
            return {
                "status": "processed",
                "transaction_id": payload.get("txn_id"),
                "analysis": analysis
            }
        
        return {"status": "processed", "transaction_id": payload.get("txn_id")}


async def _customer_queue(user_id: str):
    """Context manager for per-customer asyncio Queue serialization.
    Prevents race conditions when multiple requests hit the same customer.
    """
    if user_id not in customer_queues:
        customer_queues[user_id] = asyncio.Queue(maxsize=1)
    
    q = customer_queues[user_id]
    await q.put(True)
    try:
        yield
    finally:
        await q.get()


yono_api = YONOAPI()
