from typing import Any
from state import SarthiState
from security.audit import create_audit_artifact
from utils.cache import cached_llm_call

# ────────────────────────────────────────────────────────────────
# Assist Agent — 12-Language Support, Human Escalation, Code-Switching
# Handles: balance inquiry, transaction history, general queries,
# human escalation with full context transfer
# Query containment target: 95% (BofA Erica benchmark: 98%)
# ────────────────────────────────────────────────────────────────


def assist_agent(state: SarthiState) -> dict:
    """Assist Agent: omnichannel support with human escalation.
    
    Confidence threshold: < 0.85 -> automatic human escalation.
    Context handoff: full transcript + entities + profile + pending actions.
    """
    intent = state.get("current_intent", "general_chat")
    confidence = state.get("confidence_score", 0.5)
    lang = state.get("language", "en")
    messages = state.get("messages", [])
    
    # Auto-escalate if confidence too low
    if confidence < 0.85 and len(messages) > 2:
        return _handle_human_escalation(state)
    
    # Route based on intent
    if intent == "balance_inquiry":
        return _handle_balance_inquiry(state)
    elif intent == "transaction_history":
        return _handle_transaction_history(state)
    elif intent == "fraud_report":
        return _handle_fraud_report(state)
    elif intent == "human_escalation":
        return _handle_human_escalation(state)
    else:
        return _handle_general_chat(state)


def _handle_balance_inquiry(state: SarthiState) -> dict:
    """Handle balance inquiry with language-aware response."""
    lang = state.get("language", "en")
    user_id = state.get("user_id") or "demo_user"
    
    # Mock transaction lookup
    balances = {
        "demo_user": {"savings": 45230, "current": 12500, "fd": 200000},
        "ramesh_patil": {"savings": 1200, "current": 500},
        "priya_sharma": {"savings": 125000, "current": 45000, "fd": 500000}
    }
    
    user_balance = balances.get(user_id, {"savings": 0})
    
    responses = {
        "en": f"Your savings account balance is Rs. {user_balance.get('savings', 0):,}. Current account: Rs. {user_balance.get('current', 0):,}.",
        "hi": f"आपका बचत खाता बैलेंस रु. {user_balance.get('savings', 0):,} है। करंट अकाउंट: रु. {user_balance.get('current', 0):,}।",
        "mr": f"तुमचा बचत खाता बॅलन्स रु. {user_balance.get('savings', 0):,} आहे. चालू खाते: रु. {user_balance.get('current', 0):,}.",
        "hi-en": f"Aapka savings balance Rs. {user_balance.get('savings', 0):,} hai. Current account mein Rs. {user_balance.get('current', 0):,} hai."
    }
    
    return {
        "response_text": responses.get(lang, responses.get("en")),
        "status": "IDLE"
    }


def _handle_transaction_history(state: SarthiState) -> dict:
    """Handle transaction history request."""
    lang = state.get("language", "en")
    
    # Mock transactions
    transactions = [
        {"date": "2026-06-15", "desc": "UPI Payment", "amount": -2500, "type": "debit"},
        {"date": "2026-06-14", "desc": "Salary Credit", "amount": 85000, "type": "credit"},
        {"date": "2026-06-13", "desc": "ATM Withdrawal", "amount": -10000, "type": "debit"},
        {"date": "2026-06-12", "desc": "Electricity Bill", "amount": -3200, "type": "debit"}
    ]
    
    tx_lines = "\n".join([
        f"{t['date']}: {t['desc']} — Rs. {abs(t['amount']):,} ({t['type']})"
        for t in transactions[:5]
    ])
    
    responses = {
        "en": f"Your last 5 transactions:\n{tx_lines}",
        "hi": f"आपके पिछले 5 लेन-देन:\n{tx_lines}",
        "mr": f"तुमचे शेवटचे 5 व्यवहार:\n{tx_lines}"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }


def _handle_fraud_report(state: SarthiState) -> dict:
    """Handle fraud report — card block + chargeback initiation."""
    lang = state.get("language", "en")
    entities = state.get("extracted_entities", {})
    amount = entities.get("amount", "unknown")
    
    # High-risk action -> HITL interrupt
    create_audit_artifact(
        event_type="hitl_interrupt",
        session_id=state["session_id"],
        agent_name="assist",
        decision={"action": "fraud_report", "amount": amount, "reason": "card_block_request"},
        state_snapshot=dict(state)
    )
    
    responses = {
        "en": f"I understand you reported a fraudulent transaction of Rs. {amount}. I can block your card immediately. This requires officer approval. Shall I proceed?",
        "hi": f"मैं समझ गया कि आपने रु. {amount} के धोखाधड़ी वाले लेन-देन की रिपोर्ट की है। मैं आपका कार्ड तुरंत ब्लॉक कर सकता हूँ। इसके लिए अधिकारी की मंजूरी चाहिए। क्या मैं आगे बढ़ूँ?",
        "mr": f"मला समजले की तुम्ही रु. {amount} च्या फसव्या व्यवहाराची नोंद केली आहे. मी तुमचे कार्ड त्वरित ब्लॉक करू शकतो. यासाठी अधिकाऱ्याची मंजुरी लागेल. मी पुढे जाऊ का?"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "interrupted": True,
        "interrupt_reason": "fraud_card_block",
        "requires_hitl": True,
        "status": "RUNNING"
    }


def _handle_human_escalation(state: SarthiState) -> dict:
    """Handle human escalation with full context transfer."""
    lang = state.get("language", "en")
    
    # Build context summary for human agent
    messages = state.get("messages", [])
    transcript_summary = []
    for i, msg in enumerate(messages[-10:]):  # Last 10 messages
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        transcript_summary.append(f"{role}: {content[:100]}")
    
    context = {
        "session_id": state["session_id"],
        "user_id": state.get("user_id", "unknown"),
        "language": lang,
        "intent": state.get("current_intent", "unknown"),
        "entities": state.get("extracted_entities", {}),
        "transcript": transcript_summary,
        "pending_actions": state.get("completed_steps", []),
        "risk_score": state.get("risk_score", 0.0),
        "shield_flags": state.get("shield_flags", [])
    }
    
    create_audit_artifact(
        event_type="hitl_interrupt",
        session_id=state["session_id"],
        agent_name="assist",
        decision={"action": "human_escalation", "context": context},
        state_snapshot=dict(state)
    )
    
    responses = {
        "en": "I'm connecting you to a human agent who speaks your language. All your context has been transferred. Please wait a moment.",
        "hi": "मैं आपको आपकी भाषा बोलने वाले मानव एजेंट से जोड़ रहा हूँ। आपका सारा विवरण ट्रांसफर हो गया है। कृपया प्रतीक्षा करें।",
        "mr": "मी तुम्हाला तुमची भाषा बोलणाऱ्या मानवी एजंटशी जोडत आहे. तुमची सर्व माहिती हस्तांतरित केली आहे. कृपया प्रतीक्षा करा."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "interrupted": True,
        "interrupt_reason": "human_escalation",
        "requires_hitl": True,
        "status": "RUNNING",
        "metadata": {**state.get("metadata", {}), "escalation_context": context}
    }


def _handle_general_chat(state: SarthiState) -> dict:
    """Handle general chat when no specific intent matches."""
    lang = state.get("language", "en")
    user_text = state.get("messages", [{}])[-1].get("content", "")
    
    # Check for code-switching patterns
    text_lower = user_text.lower()
    
    # Marathi-English
    if any(w in text_lower for w in ["khata", "khate", "paisa", "muli", "sangaa", "ho", "nako"]):
        lang = "mr"
    # Hindi-English
    elif any(w in text_lower for w in ["mujhe", "mera", "hai", "chahiye", "batao", "bhaiya"]):
        lang = "hi"
    
    # Greetings
    greetings = ["hello", "hi", "namaste", "namaskar", "assalamualaikum", "sat sri akal"]
    if any(g in text_lower for g in greetings):
        responses = {
            "en": "Namaste! I am Sarthi, your SBI digital banking assistant. How can I help you today?",
            "hi": "नमस्ते! मैं सारथी हूँ, आपका SBI डिजिटल बैंकिंग साथी। आज मैं आपकी क्या मदद कर सकता हूँ?",
            "mr": "नमस्कार! मी सारथी आहे, तुमचा SBI डिजिटल बँकिंग साथी. आज मी तुमची काय मदत करू शकतो?",
            "hi-en": "Namaste! I'm Sarthi, your SBI digital buddy. Aaj kya help chahiye?"
        }
        return {
            "response_text": responses.get(lang, responses["en"]),
            "status": "IDLE"
        }
    
    # Default response
    responses = {
        "en": "I can help you with account opening, balance inquiry, loans, or connect you to a human agent. What do you need?",
        "hi": "मैं आपकी मदद कर सकता हूँ: खाता खोलना, बैलेंस पता करना, लोन, या मानव एजेंट से बात। आपको क्या चाहिए?",
        "mr": "मी तुमची मदत करू शकतो: खाते उघडणे, बॅलन्स पाहणे, कर्ज, किंवा मानवी एजंटशी बोलणे. तुम्हाला काय हवे आहे?"
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "status": "IDLE"
    }
