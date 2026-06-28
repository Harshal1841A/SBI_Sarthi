from typing import Any
from state import SarthiState
from security.prompt_injection import shield_guard, detect_prompt_injection
from security.pii_scrubber import detect_pii
from security.audit import create_audit_artifact

# ────────────────────────────────────────────────────────────────
# Shield Agent — Asynchronous Parallel Compliance Monitoring
# Hallucination detection, prompt injection defense, RBI policy alignment,
# bias auditing, PII scrubbing verification.
# Runs on EVERY message — input + output validation.
# ────────────────────────────────────────────────────────────────


async def shield_agent(state: SarthiState) -> dict:
    """Shield Agent: comprehensive security and compliance validation.
    
    This is NOT just a gate — it's a parallel compliance monitor that
    validates every input and output against:
    1. Prompt injection (100% known pattern block rate)
    2. Hallucination (financial advice fact-checking)
    3. RBI policy alignment (FREE-AI 7 Sutras)
    4. Bias auditing (gender/regional fairness)
    5. PII scrubbing verification (100% external API coverage)
    """
    messages = state.get("messages", [])
    if not messages:
        return {"shield_flags": [], "response_text": "Shield active."}
    
    last_msg = messages[-1]
    input_text = last_msg.get("content", "")
    
    # Get the last response text (from another agent)
    output_text = state.get("response_text", "")
    
    # Run full shield guard
    guard_result = shield_guard(input_text, output_text, dict(state))
    
    # Log all shield decisions
    create_audit_artifact(
        event_type="shield_flag" if guard_result["action"] != "allow" else "shield_pass",
        session_id=state["session_id"],
        agent_name="shield",
        decision={
            "input_safe": guard_result["input_safe"],
            "output_safe": guard_result["output_safe"],
            "flags": guard_result["flags"],
            "action": guard_result["action"],
            "risk_score": guard_result["risk_score"]
        },
        state_snapshot=dict(state)
    )
    
    # Handle different action outcomes
    if guard_result["action"] == "block":
        return _handle_block(state, guard_result)
    elif guard_result["action"] == "rewrite":
        return _handle_rewrite(state, guard_result)
    elif guard_result["action"] == "escalate":
        return _handle_escalate(state, guard_result)
    
    # Allow — but still record flags
    return {
        "shield_flags": guard_result["flags"],
        "risk_score": guard_result["risk_score"],
        "response_text": output_text,
        "status": state.get("status", "IDLE")
    }


def _handle_block(state: SarthiState, guard_result: dict) -> dict:
    """Block the request entirely — return safe rejection."""
    lang = state.get("language", "en")
    
    # Security alert for prompt injection or critical violations
    if not guard_result["input_safe"]:
        create_audit_artifact(
            event_type="prompt_injection",
            session_id=state["session_id"],
            agent_name="shield",
            decision={
                "action": "blocked",
                "flags": guard_result["flags"],
                "input_text_length": len(state.get("messages", [{}])[-1].get("content", ""))
            },
            state_snapshot=dict(state)
        )
    
    responses = {
        "en": "I cannot process this request for security reasons. If you need assistance, please contact your nearest SBI branch or call 1800-11-2211.",
        "hi": "Suraksha karanon se main ye request process nahi kar sakta. Agar madad chahiye, toh apne najdiki SBI branch se sampark karein ya 1800-11-2211 par call karein.",
        "mr": "Surakshatecha karanani mi hi request process karu shakat nahi. Jar madad pahije tar tumchya javalatil SBI branch shi sampark kara kiva 1800-11-2211 var call kara."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "shield_flags": guard_result["flags"],
        "risk_score": 1.0,
        "status": "BLOCKED"
    }


def _handle_rewrite(state: SarthiState, guard_result: dict) -> dict:
    """Rewrite the output to remove hallucination or policy violations."""
    lang = state.get("language", "en")
    
    # In production: call LLM to rewrite with RAG facts
    # For prototype: return safe fallback message
    responses = {
        "en": "I can only provide general information about SBI products. For specific rates and terms, please visit sbi.co.in or visit your branch.",
        "hi": "Main SBI products ke baare mein sirf general jankari de sakta hoon. Specific rates aur terms ke liye kripya sbi.co.in par jayein ya apne branch visit karein.",
        "mr": "Mi SBI utpadanenchyabaddal fakt general mahiti deu shakto. Specific dar ani terms sathi kripaya sbi.co.in var ja kiva tumche branch visit kara."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "shield_flags": guard_result["flags"] + ["rewritten:hallucination_detected"],
        "risk_score": guard_result["risk_score"],
        "status": "IDLE"
    }


def _handle_escalate(state: SarthiState, guard_result: dict) -> dict:
    """Escalate to human for high-risk but not obviously malicious requests."""
    lang = state.get("language", "en")
    
    create_audit_artifact(
        event_type="hitl_interrupt",
        session_id=state["session_id"],
        agent_name="shield",
        decision={"action": "escalate", "reason": guard_result["flags"], "risk_score": guard_result["risk_score"]},
        state_snapshot=dict(state)
    )
    
    responses = {
        "en": "This request requires human review for your security. I'm connecting you to an SBI officer. Please wait.",
        "hi": "Ye request aapki suraksha ke liye human review mein hai. Main aapko SBI adhikari se jod raha hoon. Kripaya pratiksha karein.",
        "mr": "Hi request tumchya surakshite sathi human review madhye ahe. Mi tumhala SBI adhikaryashi jodat ahe. Kripaya pratiksha kara."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "shield_flags": guard_result["flags"],
        "risk_score": guard_result["risk_score"],
        "interrupted": True,
        "interrupt_reason": "shield_escalation",
        "requires_hitl": True,
        "status": "RUNNING"
    }
