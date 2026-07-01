from state import SarthiState
from security.audit import create_audit_artifact

# ────────────────────────────────────────────────────────────────
# Engagement Agent — Financial Wellness, Churn Prevention, Dormant Reactivation
# Monitors: spending velocity, overdraft risk, life events, churn signals
# Interventions: voice (high urgency), WhatsApp (medium), in-app (low)
# ────────────────────────────────────────────────────────────────


async def engagement_agent(state: SarthiState) -> dict:
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
        "hi": f"मैंने देखा कि आप {overspend_category} पर Rs. {overspend_amount:,} ज़्यादा खर्च कर रहे हैं। क्या मैं बजट एडजस्टमेंट सजेस्ट करूँ?",
        "mr": f"माझ्या लक्षात आले की तुम्ही {overspend_category} वर Rs. {overspend_amount:,} जास्त खर्च करत आहात. मी बजेट ऍडजस्टमेंट सजेस्ट करू का?"
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
        "hi": "मैंने देखा कि आप SBI छोड़ने का सोच रहे हैं। हम आपके रिश्ते की कदर करते हैं। क्या मैं आपके लिए पर्सनलाइज्ड रिटेंशन प्लान ला सकता हूँ? बेहतर FD रेट या फी वेवर?",
        "mr": "माझ्या लक्षात आले की तुम्ही SBI सोडण्याचा विचार करत आहात. आम्ही तुमच्या नात्याला महत्त्व देतो. मी तुमच्यासाठी पर्सनलाइज्ड रिटेंशन प्लॅन आणू शकतो का? उत्तम FD रेट किंवा फी वेव्हर?"
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
        "hi": "नमस्ते! मैं SBI से सारथी बोल रहा हूँ। आपका खाता कुछ समय से इनएक्टिव है। मैं 2 मिनट में इसे एक्टिवेट कर सकता हूँ। क्या आप आगे बढ़ना चाहेंगे?",
        "mr": "नमस्कार! मी SBI कडून सारथी बोलत आहे. तुमचे खाते काही काळापासून इनऍक्टिव्ह आहे. मी २ मिनिटांत ते ऍक्टिव्हेट करू शकतो. तुम्हाला पुढे जायला आवडेल का?"
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
        "hi": f"तत्काल: आपका बैलेंस Rs. {balance:,} है लेकिन कल Rs. {scheduled_emi:,} का EMI जाना है। आपको Rs. {gap:,} और चाहिए। ऑप्शंस: 1) ओवरड्राफ्ट 2) EMI डेफरल 3) इमरजेंसी फण्ड ट्रांसफर। कौन सा?",
        "mr": f"तात्काळ: तुमचा बॅलन्स Rs. {balance:,} आहे पण उद्याचा Rs. {scheduled_emi:,} चा EMI आहे. तुम्हाला Rs. {gap:,} अधिक हवे आहेत. पर्याय: 1) ओवरड्राफ्ट 2) EMI डेफरल 3) इमरजेंसी फण्ड ट्रान्सफर. कोणता?"
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
        "hi": "मैं आपकी फाइनेंशियल वेलनेस मॉनिटर कर रहा हूँ। अगर आपको स्पेंडिंग इनसाइट्स, बजट टिप्स, या फाइनेंशियल गोल्स में मदद चाहिए, तो बताएं।",
        "mr": "मी तुमची फायनान्शियल वेलनेस मॉनिटर करत आहे. जर तुम्हाला स्पेंडिंग इनसाइट्स, बजेट टिप्स, किंवा फायनान्शियल गोल्समध्ये मदत हवी असेल तर सांगा."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }
