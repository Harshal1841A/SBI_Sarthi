from typing import Any
from state import SarthiState
from security.audit import create_audit_artifact
from utils.cache import cached_llm_call

# ────────────────────────────────────────────────────────────────
# Adoption Agent — Cross-Sell & Digital Product Adoption
# Analyzes transactions, detects patterns, delivers personalized nudges
# Consent-gated: requires P003 (Personalized Product Recommendations)
# ────────────────────────────────────────────────────────────────

# SBI product catalog with targeting rules
SBI_PRODUCTS = {
    "recurring_deposit": {
        "name": "SBI Recurring Deposit",
        "rate": 6.80,
        "min_amount": 100,
        "max_amount": 100000,
        "tenure_months": [6, 12, 24, 36, 60, 84, 96, 120],
        "target_signals": ["regular_savings", "education_expense", "salary_credit"]
    },
    "fixed_deposit": {
        "name": "SBI Fixed Deposit",
        "rate": 6.80,
        "min_amount": 1000,
        "target_signals": ["lump_sum", "bonus", "inheritance"]
    },
    "education_loan": {
        "name": "SBI Education Loan",
        "rate": 8.50,
        "max_amount": 2000000,
        "target_signals": ["education_expense", "tuition_payment", "child_age_7_15"]
    },
    "home_loan": {
        "name": "SBI Home Loan",
        "rate": 8.40,
        "max_amount": 50000000,
        "target_signals": ["rent_payment", "property_search", "marriage"]
    },
    "personal_loan": {
        "name": "SBI Personal Loan",
        "rate": 11.15,
        "max_amount": 2000000,
        "target_signals": ["medical_expense", "wedding", "travel"]
    },
    "sukanya_samriddhi": {
        "name": "Sukanya Samriddhi Yojana",
        "rate": 8.00,
        "min_amount": 250,
        "max_amount": 150000,
        "target_signals": ["girl_child", "long_term_savings"]
    },
    "sbi_life_insurance": {
        "name": "SBI Life Insurance",
        "target_signals": ["family", "income_protection", "retirement_planning"]
    },
    "digital_savings": {
        "name": "SBI Digital Savings Account",
        "rate": 2.70,
        "target_signals": ["new_customer", "digital_native", "young_professional"]
    }
}


async def adoption_agent(state: SarthiState) -> dict:
    """Adoption Agent: deliver personalized product recommendations and cross-sell nudges.
    
    Requires P003 consent. If not granted, returns silent (no recommendation).
    """
    intent = state.get("current_intent", "")
    entities = state.get("extracted_entities", {})
    lang = state.get("language", "en")
    
    # Check P003 consent
    consent_artifacts = state.get("consent_artifacts", [])
    p003_granted = any(
        a["purpose_id"] == "P003" and a.get("granted", False) 
        for a in consent_artifacts
    )
    
    if not p003_granted:
        create_audit_artifact(
            event_type="shield_flag",
            session_id=state["session_id"],
            agent_name="adoption",
            decision={"action": "recommendation_blocked", "reason": "P003_not_granted"},
            state_snapshot=dict(state)
        )
        return {
            "response_text": "",
            "shield_flags": ["P003_missing:recommendations_blocked"],
            "status": "IDLE"
        }
    
    # Route based on intent
    if intent == "product_recommendation":
        return _handle_product_inquiry(state)
    elif intent == "savings_inquiry":
        return _handle_savings_recommendation(state)
    elif "transaction" in state.get("metadata", {}):
        return _handle_transaction_nudge(state)
    else:
        return _default_adoption_response(state)


def _handle_product_inquiry(state: SarthiState) -> dict:
    """Handle explicit product inquiry from user."""
    lang = state.get("language", "en")
    entities = state.get("extracted_entities", {})
    product = entities.get("product", "recurring_deposit")
    
    product_info = SBI_PRODUCTS.get(product, SBI_PRODUCTS["recurring_deposit"])
    
    responses = {
        "en": f"{product_info['name']}: Interest rate {product_info['rate']}% per annum. Would you like to apply?",
        "hi": f"{product_info['name']}: Byaj dar {product_info['rate']}% prati varsh. Kya aap apply karna chahenge?",
        "mr": f"{product_info['name']}: Vyaj dar {product_info['rate']}% prati varsh. Tumhi apply karu ichchita ka?"
    }
    
    create_audit_artifact(
        event_type="agent_decision",
        session_id=state["session_id"],
        agent_name="adoption",
        decision={"action": "product_inquiry", "product": product},
        state_snapshot=dict(state)
    )
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }


def _handle_savings_recommendation(state: SarthiState) -> dict:
    """Deliver savings/Recurring Deposit recommendation."""
    lang = state.get("language", "en")
    entities = state.get("extracted_entities", {})
    
    # Calculate RD maturity example
    monthly = entities.get("monthly_amount", 3000)
    months = entities.get("tenure_months", 96)  # 8 years
    rate = 6.80
    
    # Simple maturity calculation: M = P * n + P * n(n+1) * r / (2 * 12 * 100)
    maturity = int(monthly * months + monthly * months * (months + 1) * rate / (2 * 12 * 100))
    
    responses = {
        "en": f"SBI Recurring Deposit: Rs. {monthly:,}/month for {months//12} years at {rate}% = Rs. {maturity:,} maturity. Perfect for education fund! Apply now?",
        "hi": f"SBI Recurring Deposit: Rs. {monthly:,}/mahina, {months//12} saal, {rate}% byaj = Rs. {maturity:,} maturity. Shikshan fund ke liye behtarin! Abhi apply karein?",
        "mr": f"SBI Recurring Deposit: Rs. {monthly:,}/mahina, {months//12} varsh, {rate}% vyaj = Rs. {maturity:,} maturity. Shikshan fund sathi uttam! Atta apply kara?"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }


def _handle_transaction_nudge(state: SarthiState) -> dict:
    """Handle proactive nudge based on transaction analysis.
    Triggered by YONO transaction webhook.
    """
    lang = state.get("language", "en")
    metadata = state.get("metadata", {})
    transaction = metadata.get("transaction", {})
    
    category = transaction.get("category", "")
    amount = transaction.get("amount", 0)
    
    # Match transaction to product
    matched_product = None
    if category in ["EDUCATION_TUITION", "EDUCATION", "SCHOOL", "COLLEGE"]:
        matched_product = "recurring_deposit"
    elif category in ["RENT", "HOUSING"]:
        matched_product = "home_loan"
    elif category in ["MEDICAL", "HEALTHCARE"]:
        matched_product = "personal_loan"
    elif category in ["WEDDING", "JEWELRY"]:
        matched_product = "personal_loan"
    elif category in ["SALARY", "PAYROLL"]:
        matched_product = "digital_savings"
    
    if matched_product:
        product_info = SBI_PRODUCTS[matched_product]
        
        responses = {
            "en": f"Hi! I noticed a {category} payment. Based on your pattern, {product_info['name']} could help. Rate: {product_info.get('rate', 'N/A')}%. Want details?",
            "hi": f"Namaste! Maine {category} payment dekha. Aapke pattern ke hisaab se, {product_info['name']} madad kar sakta hai. Dar: {product_info.get('rate', 'N/A')}%. Jankari chahiye?",
            "mr": f"Namaskar! Mi {category} payment lakshat ghetli. Tumchya pattern nusar, {product_info['name']} madat karu shakto. Dar: {product_info.get('rate', 'N/A')}%. Mahiti haviahe ka?"
        }
        
        create_audit_artifact(
            event_type="agent_decision",
            session_id=state["session_id"],
            agent_name="adoption",
            decision={"action": "proactive_nudge", "product": matched_product, "trigger": category},
            state_snapshot=dict(state)
        )
        
        return {
            "response_text": responses.get(lang, responses["en"]),
            "status": "IDLE"
        }
    
    return _default_adoption_response(state)


def _default_adoption_response(state: SarthiState) -> dict:
    """Default adoption response when no specific trigger matches."""
    lang = state.get("language", "en")
    
    responses = {
        "en": "I can help you discover SBI products that match your needs. Are you looking for savings, loans, or insurance?",
        "hi": "Main aapko SBI ke products ke baare mein bata sakta hoon jo aapki zarooraton se match karte hain. Bachat, loan, ya insurance?",
        "mr": "Mi tumhala SBI che utpadane sanghu shakto je tumchya garajana saman ahet. Bachat, loan, kiva insurance?"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }
