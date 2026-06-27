from typing import Any
from state import SarthiState
from security.audit import create_audit_artifact

# ────────────────────────────────────────────────────────────────
# Engagement Agent — Financial Wellness, Churn Prevention, Dormant Reactivation
# Monitors: spending velocity, overdraft risk, life events, churn signals
# Interventions: voice (high urgency), WhatsApp (medium), in-app (low)
# ────────────────────────────────────────────────────────────────


def engagement_agent(state: SarthiState) -> dict:
    """Engagement Agent: financial wellness coaching, churn prevention, dormant reactivation.
    
    Detects:
    - Overdraft risk (balance < scheduled EMI)
    - Churn signals (account closure inquiries, reduced activity)
    - Dormant accounts (90+ days no transaction)
    - Life events (education, marriage, medical)
    """
    intent = state.get("current_intent", "")
    lang = state.get("language", "en")
    
    if intent == "spending_alert":
        return _handle_spending_alert(state)
    elif intent == "churn_risk":
        return _handle_churn_intervention(state)
    elif intent == "dormant_reactivation":
        return _handle_dormant_reactivation(state)
    elif intent == "overdraft_prevention":
        return _handle_overdraft_prevention(state)
    else:
        return _default_engagement_response(state)


def _handle_spending_alert(state: SarthiState) -> dict:
    """Handle spending pattern anomaly detection."""
    lang = state.get("language", "en")
    metadata = state.get("metadata", {})
    
    # Mock spending analysis
    overspend_category = metadata.get("overspend_category", "dining")
    overspend_amount = metadata.get("overspend_amount", 5000)
    
    responses = {
        "en": f"I noticed you're spending Rs. {overspend_amount:,} more than usual on {overspend_category}. Would you like me to suggest a budget adjustment?",
        "hi": f"Maine dekha aap {overspend_category} par Rs. {overspend_amount:,} zyada kharch kar rahe hain. Kya main budget adjustment suggest karu?",
        "mr": f"Mi lakshat ghetli ki tumhi {overspend_category} var Rs. {overspend_amount:,} jast kharch karat ahat. Mi budget adjustment suggest karu ka?"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }


def _handle_churn_intervention(state: SarthiState) -> dict:
    """Handle churn risk — proactive retention offer."""
    lang = state.get("language", "en")
    
    create_audit_artifact(
        event_type="agent_decision",
        session_id=state["session_id"],
        agent_name="engagement",
        decision={"action": "churn_intervention", "risk_score": state.get("risk_score", 0.5)},
        state_snapshot=dict(state)
    )
    
    responses = {
        "en": "I noticed you're considering leaving SBI. We value your relationship. Can I offer you a personalized retention plan? Perhaps a better FD rate or fee waiver?",
        "hi": "Maine dekha aap SBI chhodne ka soch rahe hain. Hum aapke rishte ko kadar karte hain. Kya main aapke liye personalized retention plan la sakta hoon? Behtar FD rate ya fee waiver?",
        "mr": "Mi lakshat ghetli ki tumhi SBI sodnyacha vichar karat ahat. Aamhi tumchya nateyala mahatva deto. Mi tumchya sathi personalized retention plan anu shakto ka? Changali FD rate kiva fee waiver?"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }


def _handle_dormant_reactivation(state: SarthiState) -> dict:
    """Handle dormant account reactivation — outbound IVR style."""
    lang = state.get("language", "en")
    
    create_audit_artifact(
        event_type="agent_decision",
        session_id=state["session_id"],
        agent_name="engagement",
        decision={"action": "dormant_reactivation", "channel": "ivr"},
        state_snapshot=dict(state)
    )
    
    responses = {
        "en": "Hello! This is Sarthi from SBI. Your account has been inactive for a while. I can help you reactivate it in 2 minutes. Would you like to proceed?",
        "hi": "Namaste! Main SBI se Sarthi bol raha hoon. Aapka khata kuch samay se inactive hai. Main 2 minute mein ise activate kar sakta hoon. Kya aap aage badhna chahenge?",
        "mr": "Namaskar! Mi SBI kadun Sarthi bolat ahe. Tumche khata kahi kalapasun active nahi. Mi 2 minitata te activate karu shakto. Tumhi pudhe jayla ichchita ka?"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }


def _handle_overdraft_prevention(state: SarthiState) -> dict:
    """Handle overdraft risk — urgent intervention."""
    lang = state.get("language", "en")
    metadata = state.get("metadata", {})
    
    balance = metadata.get("balance", 2400)
    scheduled_emi = metadata.get("scheduled_emi", 3500)
    days_until_salary = metadata.get("days_until_salary", 5)
    
    gap = scheduled_emi - balance
    
    create_audit_artifact(
        event_type="agent_decision",
        session_id=state["session_id"],
        agent_name="engagement",
        decision={
            "action": "overdraft_prevention",
            "balance": balance,
            "scheduled_emi": scheduled_emi,
            "gap": gap
        },
        state_snapshot=dict(state)
    )
    
    responses = {
        "en": f"Urgent: Your balance is Rs. {balance:,} but EMI of Rs. {scheduled_emi:,} is due tomorrow. You need Rs. {gap:,} more. Options: 1) Overdraft facility 2) EMI deferral 3) Emergency fund transfer. Which one?",
        "hi": f"Tatkal: Aapka balance Rs. {balance:,} hai lekin kal Rs. {scheduled_emi:,} ka EMI jana hai. Aapko Rs. {gap:,} aur chahiye. Options: 1) Overdraft 2) EMI deferral 3) Emergency fund transfer. Konsa?",
        "mr": f"Tatkali: Tumcha balance Rs. {balance:,} ahe pan udyacha Rs. {scheduled_emi:,} cha EMI ahe. Tumhala Rs. {gap:,} adhik lagle. Parayay: 1) Overdraft 2) EMI deferral 3) Emergency fund transfer. Konta?"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }


def _default_engagement_response(state: SarthiState) -> dict:
    """Default engagement response."""
    lang = state.get("language", "en")
    
    responses = {
        "en": "I'm monitoring your financial wellness. Let me know if you'd like spending insights, budget tips, or help with any financial goals.",
        "hi": "Main aapki financial wellness monitor kar raha hoon. Agar aapko spending insights, budget tips, ya financial goals mein madad chahiye, toh batayein.",
        "mr": "Mi tumchi financial wellness monitor karat ahe. Jar tumhala spending insights, budget tips, kiva financial goals madhe madad pahije tar sanga."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }
