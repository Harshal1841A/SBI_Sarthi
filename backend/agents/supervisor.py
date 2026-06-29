from typing import Any, Optional
from state import SarthiState
from security.pii_scrubber import scrub_pii
from security.prompt_injection import shield_guard, calculate_risk_score
from security.audit import create_audit_artifact
from utils.cache import cached_llm_call, async_cached_llm_call
from nlp.nemotron_client import NemotronClient
import asyncio
import re
import hashlib

# ────────────────────────────────────────────────────────────────
# Supervisor Node — Intent Router + Context Manager + Escalation
# The brain of the orchestration layer. Determines which agent
# handles each turn based on intent classification + confidence.
# ────────────────────────────────────────────────────────────────

# Banking intent routing map
INTENT_ROUTING = {
    "account_open": "acquisition",
    "kyc_upload": "acquisition",
    "loan_application": "acquisition",
    "product_recommendation": "adoption",
    "balance_inquiry": "assist",
    "transaction_history": "assist",
    "spending_alert": "engagement",
    "churn_risk": "engagement",
    "fraud_report": "assist",      # FIX M4: assist handles card-block + HITL, not shield
    "compliance_query": "shield",
    "dormant_reactivation": "engagement",
    "overdraft_prevention": "engagement",
    "general_chat": "assist",
    "human_escalation": "assist",
    "consent_management": "acquisition"
}

# Few-shot intent classification examples (embedded for prototype)
INTENT_FEW_SHOT = """
Classify the banking intent from the user's message. Respond ONLY with JSON:
{"intent": "<intent>", "confidence": 0.0-1.0, "entities": {}}

Examples:
1. "Mujhe khata kholna hai" -> {"intent": "account_open", "confidence": 0.95, "entities": {"language": "hi"}}
2. "Maza khatavatun paisa kami zala" -> {"intent": "fraud_report", "confidence": 0.92, "entities": {"language": "mr", "amount": "unknown"}}
3. "Mere account ka balance kitna hai" -> {"intent": "balance_inquiry", "confidence": 0.98, "entities": {"language": "hi"}}
4. "Mujhe loan chahiye tailoring ke liye" -> {"intent": "loan_application", "confidence": 0.94, "entities": {"language": "hi", "purpose": "business"}}
5. "Mujhe education loan ke baare mein jankari chahiye" -> {"intent": "product_recommendation", "confidence": 0.89, "entities": {"language": "hi", "product": "education_loan"}}
6. "Mera card block karo" -> {"intent": "fraud_report", "confidence": 0.91, "entities": {"language": "hi", "action": "card_block"}}
7. "Mujhe bachat yojna ke baare mein batao" -> {"intent": "product_recommendation", "confidence": 0.88, "entities": {"language": "hi", "product": "savings"}}
8. "Mera khata band karun deu ka?" -> {"intent": "churn_risk", "confidence": 0.87, "entities": {"language": "mr", "intent": "account_closure"}}
"""

import threading

# Lazy singleton — created on first use to avoid import-time side effects
_nemotron_instance: Optional[NemotronClient] = None
_nemotron_lock = threading.Lock()

def _get_nemotron() -> NemotronClient:
    global _nemotron_instance
    if _nemotron_instance is None:
        with _nemotron_lock:
            if _nemotron_instance is None:
                _nemotron_instance = NemotronClient()
    return _nemotron_instance

async def supervisor_node(state: SarthiState) -> dict:
    """Supervisor: classify intent, route to appropriate agent, update risk.
    
    This is the entry point of the LangGraph. Every user message flows here first.
    """
    messages = state.get("messages", [])
    if not messages:
        return {
            "response_text": "Namaskar. I am Sarthi, your AI assistant. How can I help you today?",
            "current_intent": "greeting",
            "confidence_score": 1.0,
            "next_agent": "assist"
        }
    
    last_message = messages[-1]
    user_text = last_message.get("content", "")
    
    # Scrub PII before any processing
    scrubbed = scrub_pii(user_text)
    
    # Intent classification (with caching/LLM)
    prompt_hash = f"intent_{hashlib.sha256(scrubbed.encode('utf-8')).hexdigest()[:16]}"
    
    # Try LLM first (with async cache)
    async def do_llm_call():
        return await _classify_intent_llm(scrubbed, state.get("language", "en"))
        
    intent_result = await async_cached_llm_call(prompt_hash, do_llm_call)
    
    intent = intent_result.get("intent", "general_chat")
    confidence = intent_result.get("confidence", 0.5)
    entities = intent_result.get("entities", {})
    
    # Calculate risk score
    risk_score = calculate_risk_score(user_text, "", intent, entities)
    
    # Determine routing
    if confidence < 0.85:
        target_agent = "assist"
    else:
        target_agent = INTENT_ROUTING.get(intent, "assist")
    
    # Auto-HITL for high-risk actions
    requires_hitl = False
    interrupt_reason = None
    if risk_score > 0.7:
        requires_hitl = True
        interrupt_reason = f"high_risk:{intent}"
        target_agent = "hitl_pause"
    elif intent in ["loan_sanction", "fund_transfer"]:
        try:
            amt_val = float(str(entities.get("amount", 0)).replace(",", ""))
        except (ValueError, TypeError):
            amt_val = 0.0
        if amt_val > 50000:
            requires_hitl = True
            interrupt_reason = "high_value_action"
            target_agent = "hitl_pause"

    # Priority overrides (Active flows)
    if state.get("interrupted"):
        if state.get("human_decision"):
            # Human has made a decision via Command(resume=...) — resume the flow
            target_agent = "hitl_resume"
        else:
            # FIX M-9: still waiting for human decision.
            # Do NOT re-route to hitl_pause — the graph is already halted there.
            # Return the current pause state without changing routing; LangGraph
            # will not actually reach this code until Command(resume=...) is sent.
            return {
                "current_intent": state.get("current_intent", "general_chat"),
                "confidence_score": state.get("confidence_score", 0.0),
                "extracted_entities": state.get("extracted_entities", {}),
                "risk_score": state.get("risk_score", 0.0),
                "requires_hitl": True,
                "interrupted": True,
                "interrupt_reason": state.get("interrupt_reason"),
                "next_agent": "hitl_pause",
                "pii_scrubbed_input": scrubbed,
                "metadata": {
                    **state.get("metadata", {}),
                    "supervisor_routing": "hitl_pause",
                }
            }
    elif state.get("onboarding_step", "idle") not in ["idle", "complete"]:
        # If we are in the middle of an acquisition flow, override the intent
        # unless it's a high-risk action that needs HITL
        if not requires_hitl:
            target_agent = "acquisition"
    
    # Log to audit
    create_audit_artifact(
        event_type="agent_decision",
        session_id=state["session_id"],
        agent_name="supervisor",
        decision={
            "intent": intent,
            "confidence": confidence,
            "routed_to": target_agent,
            "risk_score": risk_score,
            "requires_hitl": requires_hitl
        },
        state_snapshot=dict(state)
    )
    
    return {
        "current_intent": intent,
        "confidence_score": confidence,
        "extracted_entities": entities,
        "risk_score": risk_score,
        "requires_hitl": requires_hitl,
        "interrupted": requires_hitl,
        "interrupt_reason": interrupt_reason,
        "next_agent": target_agent,
        "pii_scrubbed_input": scrubbed,
        "metadata": {
            **state.get("metadata", {}),
            "supervisor_routing": target_agent,
            "intent_classification": intent,
            "risk_score": risk_score
        }
    }


async def _classify_intent_llm(text: str, language: str) -> dict:
    """Real LLM intent classification via NVIDIA Nemotron-3-Ultra-550B."""
    from security.pii_scrubber import scrub_pii
    
    scrubbed = scrub_pii(text)
    
    system_prompt = """You are Sarthi, SBI's banking AI. Classify the user's intent.
    Respond ONLY with valid JSON: {"intent": "...", "confidence": 0.0-1.0, "entities": {"language": "..."}}
    
    Valid intents: account_open, kyc_upload, loan_application, product_recommendation, 
    balance_inquiry, transaction_history, spending_alert, churn_risk, fraud_report, 
    compliance_query, dormant_reactivation, human_escalation, general_chat.
    
    Confidence must be between 0.0 and 1.0."""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Language: {language}. Message: {scrubbed}"}
    ]
    
    try:
        raw = await asyncio.wait_for(
            _get_nemotron().chat(messages, temperature=0.1, max_tokens=256),
            timeout=5.0
        )
        import json
        result = json.loads(raw.strip())
        # Validate
        assert "intent" in result
        assert "confidence" in result
        assert 0.0 <= result["confidence"] <= 1.0
        return result
    except (Exception, asyncio.TimeoutError, asyncio.CancelledError) as e:
        # Fallback to rule-based
        return _classify_intent_fallback(text, language)

def _classify_intent_fallback(text: str, language: str) -> dict:
    try:
        text_lower = text.lower()
        marathi_words = ["khata", "khate", "paisa", "muli", "mulichi", "shikshan", "madat", "sangaa", "nako", "barobar"]
        hindi_words = ["mujhe", "mera", "meri", "chahiye", "batao", "karo", "bhaiya"]

        detected_lang = language
        if any(re.search(r'\b' + w + r'\b', text_lower) for w in marathi_words):
            detected_lang = "mr"
        elif any(re.search(r'\b' + w + r'\b', text_lower) for w in hindi_words):
            detected_lang = "hi"

        intent_map = {
            "account_open": ["khata ugad", "khata khol", "account open", "new account", "savings account", "bachat khata", "अकाउंट खोलो", "खाता खोलो"],
            "kyc_upload": ["aadhaar", "pan card", "document upload", "kyc", "आधार", "पैन"],
            "loan_application": ["loan chahiye", "loan chahie", "loan apply", "mudra", "education loan", "personal loan", "लोन चाहिए", "ऋण चाहिए", "लोन"],
            "product_recommendation": ["product", "recommend", "suggest", "bachat yojna", "scheme", "fd", "rd", "insurance", "बचत योजना"],
            "balance_inquiry": ["balance", "kitna hai", "ketna", "balance kitna", "account balance", "paisa kitna", "बैलेंस कितना है", "बैलेंस", "शेष राशि"],
            "transaction_history": ["transaction", "history", "statement", "last payment", "recent", "लेनदेन", "स्टेटमेंट"],
            "spending_alert": ["spend", "spending", "budget", "overdraft", "expense", "खर्च"],
            "churn_risk": ["close account", "band kar", "churn", "leave", "switch bank", "dusra bank", "खाता बंद"],
            "fraud_report": ["fraud", "hack", "unauthorized", "galat", "galti", "card block", "unknown transaction", "कार्ड ब्लॉक करो", "कार्ड ब्लॉक", "धोखाधड़ी"],
            "compliance_query": ["compliance", "policy", "rbi", "dpdp", "consent", "privacy", "गोपनीयता"],
            "dormant_reactivation": ["dormant", "activate", "inactive", "use nahi", "long time", "सक्रिय"],
            "human_escalation": ["human", "agent", "officer", "manager", "banda", "aadmi", "madad", "एजेंट", "अधिकारी", "मदद"]
        }

        # FIX H-6: Score ALL intents and pick the best match.
        # The original code short-circuited on the first matching keyword,
        # making classification order-dependent and non-exhaustive.
        # Now we count keyword hits per intent and normalise to a confidence score.
        best_intent = "general_chat"
        best_score = 0
        best_confidence = 0.5

        for intent, keywords in intent_map.items():
            hits = sum(1 for kw in keywords if kw in text_lower)
            if hits > best_score:
                best_score = hits
                best_intent = intent
                # Confidence scales from 0.75 (1 hit) to 0.97 (many hits)
                best_confidence = min(0.75 + 0.04 * (hits - 1), 0.97)

        entities = {"language": detected_lang}
        amount_match = re.search(r'(?:Rs\.?\s?|\u20b9\s?)(\d[\d,]*)', text, re.IGNORECASE)
        if amount_match:
            entities["amount"] = int(amount_match.group(1).replace(",", ""))

        products = ["education_loan", "personal_loan", "home_loan", "car_loan", "recurring_deposit", "fixed_deposit", "savings"]
        for p in products:
            if p.replace("_", " ") in text_lower or p.replace("_", "") in text_lower:
                entities["product"] = p

        return {
            "intent": best_intent,
            "confidence": best_confidence,
            "entities": entities
        }
    except Exception as e:
        return {
            "intent": "general_chat",
            "confidence": 0.5,
            "entities": {"language": language, "error": str(e)}
        }


def route_intent(state: SarthiState) -> str:
    """Conditional edge function: route from supervisor to target agent.
    Called by LangGraph conditional edge after supervisor_node executes.
    """
    next_agent = state.get("next_agent")
    if next_agent:
        return next_agent
    
    intent = state.get("current_intent", "general_chat")
    confidence = state.get("confidence_score", 0.0)
    
    if confidence < 0.85:
        return "assist"
    
    return INTENT_ROUTING.get(intent, "assist")
