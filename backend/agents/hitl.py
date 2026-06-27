from typing import Any
from state import SarthiState
from security.audit import create_audit_artifact

# ────────────────────────────────────────────────────────────────
# HITL Nodes — Human-in-the-Loop Pause and Resume
# hitl_pause: graph execution halts, state checkpointed, supervisor notified
# hitl_resume: graph resumes after human approval via Command(resume=...)
# ────────────────────────────────────────────────────────────────


def hitl_pause_node(state: SarthiState) -> dict:
    """HITL Pause Node: interrupt graph execution, checkpoint state, notify dashboard.
    
    When the graph reaches this node, execution HALTS. The thread enters
    'interrupted' state. The Supervisor Dashboard polls for interrupted threads.
    Human officer reviews context and clicks Approve/Reject.
    """
    interrupt_reason = state.get("interrupt_reason", "unknown")
    session_id = state["session_id"]
    
    create_audit_artifact(
        event_type="hitl_interrupt",
        session_id=session_id,
        agent_name="hitl_pause",
        decision={
            "reason": interrupt_reason,
            "timestamp": state.get("metadata", {}).get("timestamp"),
            "risk_score": state.get("risk_score", 0.0)
        },
        state_snapshot=dict(state)
    )
    
    # The response here is what the user sees while waiting
    lang = state.get("language", "en")
    responses = {
        "en": "Your request requires human review for security and compliance. An SBI officer is reviewing your case. This typically takes 2-5 minutes. Please stay connected.",
        "hi": "Aapki request suraksha aur compliance ke liye human review mein hai. Ek SBI adhikari aapka case dekh raha hai. Ye aam taur par 2-5 minute leta hai. Kripaya jude rahein.",
        "mr": "Tumchi request suraksha ani compliance sathi human review madhye ahe. Ek SBI adhikari tumcha case pahat ahe. He samanyapane 2-5 minute ghete. Kripaya jodle raha."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "interrupted": True,
        "interrupt_reason": interrupt_reason,
        "requires_hitl": True,
        "hitl_timestamp": __import__('time').time(),
        "status": "RUNNING"
    }


def hitl_resume_node(state: SarthiState) -> dict:
    """HITL Resume Node: graph resumes after human approval.
    
    This node is triggered by:
    await graph.ainvoke(
        Command(resume={"approved": True, "approver_id": "officer_123"}),
        config={"configurable": {"thread_id": thread_id}}
    )
    """
    human_decision = state.get("human_decision", {})
    approved = human_decision.get("approved", False)
    approver_id = human_decision.get("approver_id", "unknown")
    reason = human_decision.get("reason", "")
    
    create_audit_artifact(
        event_type="hitl_approval" if approved else "hitl_rejection",
        session_id=state["session_id"],
        agent_name="hitl_resume",
        decision={
            "approved": approved,
            "approver_id": approver_id,
            "reason": reason,
            "interrupt_reason": state.get("interrupt_reason")
        },
        state_snapshot=dict(state)
    )
    
    if not approved:
        # Human rejected — trigger compensation
        return {
            "response_text": _get_rejection_message(state),
            "status": "FAILED",
            "interrupted": False,
            "requires_hitl": False,
            "metadata": {
                **state.get("metadata", {}),
                "hitl_rejection": {
                    "approver_id": approver_id,
                    "reason": reason
                }
            }
        }
    
    # Approved — continue with the flow
    lang = state.get("language", "en")
    
    # Determine what to do next based on interrupt reason
    interrupt_reason = state.get("interrupt_reason", "")
    
    if "v_kyc" in interrupt_reason:
        return _resume_vkyc(state, approver_id)
    elif "loan" in interrupt_reason or "fund" in interrupt_reason:
        return _resume_loan(state, approver_id)
    elif "fraud" in interrupt_reason or "block" in interrupt_reason:
        return _resume_fraud_action(state, approver_id)
    else:
        return _generic_resume(state, approver_id)


def _resume_vkyc(state: SarthiState, approver_id: str) -> dict:
    """Resume after V-KYC approval."""
    lang = state.get("language", "en")
    
    responses = {
        "en": "Video verification approved! Your account is now fully verified. Let's proceed with the final steps.",
        "hi": "Video verification manjur ho gaya! Aapka khata ab fully verified hai. Aage ke steps shuru karte hain.",
        "mr": "Video verification manjur zale! Tumche khata atta purnapane verify zale. Shevdtche step suru karuya."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "interrupted": False,
        "requires_hitl": False,
        "completed_steps": ["create_profile", "verify_kyc", "v_kyc"],
        "status": "RUNNING"
    }


def _resume_loan(state: SarthiState, approver_id: str) -> dict:
    """Resume after loan approval."""
    lang = state.get("language", "en")
    entities = state.get("extracted_entities", {})
    loan_amount = entities.get("amount", 50000)
    
    loan_id = f"LN_SBI_2026_{hash(state['session_id'] + approver_id) & 0xFFFFFF:06x}"
    
    responses = {
        "en": f"Congratulations! Your loan of Rs. {loan_amount:,} is sanctioned by officer {approver_id}. Loan ID: {loan_id}. Disbursement will happen within 24 hours.",
        "hi": f"Badhai ho! Aapka Rs. {loan_amount:,} ka loan adhikari {approver_id} dwara manjur ho gaya. Loan ID: {loan_id}. Rakam 24 ghante mein jama ho jayegi.",
        "mr": f"Abhinandan! Tumche Rs. {loan_amount:,} che loan adhikari {approver_id} dware manjur zale. Loan ID: {loan_id}. Rakam 24 tasat jama honar."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "interrupted": False,
        "requires_hitl": False,
        "status": "COMPLETE"
    }


def _resume_fraud_action(state: SarthiState, approver_id: str) -> dict:
    """Resume after fraud action (card block) approval."""
    lang = state.get("language", "en")
    
    responses = {
        "en": f"Your card has been blocked by officer {approver_id} for your security. A new card will be dispatched within 3 working days. Chargeback process initiated.",
        "hi": f"Aapka card adhikari {approver_id} dwara suraksha ke liye block kar diya gaya hai. Naya card 3 working days mein bheja jayega. Chargeback process shuru ho gaya hai.",
        "mr": f"Tumche card adhikari {approver_id} dware surakshite sathi block kele gele. Nave card 3 working daysat pathavle jael. Chargeback process suru zale."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "interrupted": False,
        "requires_hitl": False,
        "status": "COMPLETE"
    }


def _generic_resume(state: SarthiState, approver_id: str) -> dict:
    """Generic resume after HITL approval."""
    lang = state.get("language", "en")
    
    responses = {
        "en": "Your request has been approved. Proceeding now.",
        "hi": "Aapki request manjur ho gayi hai. Ab aage badh rahe hain.",
        "mr": "Tumchi request manjur zaleli ahe. Aata pudhe jat ahe."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "interrupted": False,
        "requires_hitl": False,
        "status": "RUNNING"
    }


def _get_rejection_message(state: SarthiState) -> str:
    """Generate rejection message."""
    lang = state.get("language", "en")
    
    responses = {
        "en": "Your request has been reviewed and could not be approved at this time. Please visit your nearest SBI branch for assistance.",
        "hi": "Aapki request review ki gayi hai aur is samay manjur nahi ki ja sakti. Kripya madad ke liye apne najdiki SBI branch visit karein.",
        "mr": "Tumchi request review keli geleli ahe ani ya veli manjur kili ja shakat nahi. Kripaya madati sathi tumche javalatil SBI branch visit kara."
    }
    
    return responses.get(lang, responses["en"])


def wait_human_approval(state: SarthiState) -> str:
    """Conditional edge: check if human has approved, rejected, or not yet decided.

    FIX H-5: Returns three possible values:
    - "pending"  → no human_decision yet; graph routes to END and halts at checkpoint.
                   The thread stays interrupted. When Command(resume={...}) arrives,
                   LangGraph re-runs from hitl_pause and this function is called again.
    - "approved" → human approved; graph continues to hitl_resume.
    - "rejected" → human rejected; graph continues to compensation (saga rollback).
    """
    decision = state.get("human_decision")
    if not decision:
        # No decision yet — graph halts here (routed to END in graph.py)
        return "pending"
    if decision.get("approved"):
        return "approved"
    return "rejected"
