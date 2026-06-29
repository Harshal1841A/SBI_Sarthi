
# ────────────────────────────────────────────────────────────────
# Mock SBI Middleware Integration
# Simulates SBI's existing API contracts for:
# - Account creation
# - KYC verification (via SBI middleware, NOT direct UIDAI)
# - Balance inquiry
# - Transaction posting
# - Loan origination
# ────────────────────────────────────────────────────────────────

# Mock "database" of accounts
_mock_accounts: dict = {}
_mock_loans: dict = {}
_mock_transactions: dict = {}


class SBIError(Exception):
    """SBI API error."""
    pass


class SBIAPI:
    """Mock SBI Middleware API adapter."""
    
    @staticmethod
    def create_account(profile_id: str, kyc_token: str, initial_deposit: float = 500.0) -> dict:
        """Create a new savings account.
        
        Returns:
            {"account_id": str, "status": "ACTIVE", "ifsc": "SBIN0001234", "branch": "MUMBAI_MAIN"}
        """
        account_id = f"SBIN{hash(profile_id + kyc_token) & 0xFFFFFFFF:010d}"
        
        account = {
            "account_id": account_id,
            "profile_id": profile_id,
            "kyc_token": kyc_token,
            "status": "ACTIVE",
            "ifsc": "SBIN0001234",
            "branch": "MUMBAI_MAIN",
            "balance": initial_deposit,
            "account_type": "SAVINGS",
            "opening_date": "2026-06-18",
            "min_balance": 500.0
        }
        
        _mock_accounts[account_id] = account
        return account
    
    @staticmethod
    def get_account_balance(account_id: str) -> dict:
        """Get account balance."""
        account = _mock_accounts.get(account_id)
        if not account:
            raise SBIError(f"Account {account_id} not found")
        return {"account_id": account_id, "balance": account["balance"]}
    
    @staticmethod
    def post_transaction(account_id: str, amount: float, description: str, txn_type: str = "debit") -> dict:
        """Post a transaction to an account."""
        account = _mock_accounts.get(account_id)
        if not account:
            raise SBIError(f"Account {account_id} not found")
        
        if txn_type == "debit" and account["balance"] < amount:
            raise SBIError(f"Insufficient balance: {account['balance']} < {amount}")
        
        txn_id = f"TXN{hash(account_id + str(amount) + description) & 0xFFFFFFFF:010d}"
        
        if txn_type == "debit":
            account["balance"] -= amount
        else:
            account["balance"] += amount
        
        txn = {
            "txn_id": txn_id,
            "account_id": account_id,
            "amount": amount,
            "type": txn_type,
            "description": description,
            "balance_after": account["balance"],
            "timestamp": "2026-06-18T10:00:00Z"
        }
        
        _mock_transactions[txn_id] = txn
        return txn
    
    @staticmethod
    def get_transaction_history(account_id: str, limit: int = 10) -> list:
        """Get transaction history for an account."""
        txns = [
            t for t in _mock_transactions.values()
            if t["account_id"] == account_id
        ]
        return sorted(txns, key=lambda x: x["timestamp"], reverse=True)[:limit]
    
    @staticmethod
    def create_loan(
        user_id: str,
        amount: float,
        purpose: str,
        tenure_months: int = 60,
        interest_rate: float = 8.5
    ) -> dict:
        """Create a loan application."""
        loan_id = f"LN_SBI_2026_{hash(user_id + str(amount)) & 0xFFFFFF:06x}"
        
        # EMI calculation: M = P * r * (1+r)^n / ((1+r)^n - 1)
        r = interest_rate / (12 * 100)
        n = tenure_months
        emi = amount * r * (1 + r) ** n / ((1 + r) ** n - 1)
        
        loan = {
            "loan_id": loan_id,
            "user_id": user_id,
            "amount": amount,
            "purpose": purpose,
            "tenure_months": tenure_months,
            "interest_rate": interest_rate,
            "emi": round(emi, 2),
            "total_interest": round(emi * n - amount, 2),
            "status": "PENDING_SANCTION",
            "applied_date": "2026-06-18"
        }
        
        _mock_loans[loan_id] = loan
        return loan
    
    @staticmethod
    def sanction_loan(loan_id: str, officer_id: str) -> dict:
        """Sanction a loan (HITL action)."""
        loan = _mock_loans.get(loan_id)
        if not loan:
            raise SBIError(f"Loan {loan_id} not found")
        
        loan["status"] = "SANCTIONED"
        loan["sanctioned_by"] = officer_id
        loan["sanctioned_date"] = "2026-06-18"
        
        return loan
    
    @staticmethod
    def block_card(account_id: str, reason: str) -> dict:
        """Block a debit/credit card."""
        return {
            "account_id": account_id,
            "card_status": "BLOCKED",
            "reason": reason,
            "replacement_card_dispatched": True,
            "delivery_days": 3
        }
    
    @staticmethod
    def get_account_summary(user_id: str) -> dict:
        """Get full account summary for a user."""
        accounts = [a for a in _mock_accounts.values() if a.get("profile_id", "").startswith(user_id[:8])]
        loans = [l for l in _mock_loans.values() if l["user_id"] == user_id]
        
        total_balance = sum(a["balance"] for a in accounts)
        
        return {
            "user_id": user_id,
            "total_accounts": len(accounts),
            "total_balance": total_balance,
            "accounts": accounts,
            "loans": loans,
            "credit_score": 750  # Mock CIBIL
        }


# Convenience functions
sbi_api = SBIAPI()
