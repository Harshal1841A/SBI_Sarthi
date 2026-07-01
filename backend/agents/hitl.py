import time
import hashlib
from state import SarthiState
from security.audit import create_audit_artifact

# ────────────────────────────────────────────────────────────────
# HITL Nodes — Human-in-the-Loop Pause and Resume
# hitl_pause: graph execution halts, state checkpointed, supervisor notified
# hitl_resume: graph resumes after human approval via Command(resume=...)
# ────────────────────────────────────────────────────────────────


async def hitl_pause_node(state: SarthiState) -> dict:
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
        "hi": "आपकी रिक्वेस्ट सुरक्षा और कंप्लायंस के लिए ह्यूमन रिव्यू में है। एक SBI अधिकारी आपका केस देख रहा है। यह आमतौर पर 2-5 मिनट लेता है। कृपया जुड़े रहें।",
        "mr": "तुमची रिक्वेस्ट सुरक्षा आणि कंप्लायन्ससाठी ह्यूमन रिव्ह्यू मध्ये आहे. एक SBI अधिकारी तुमची केस पाहत आहे. यास साधारणपणे २-५ मिनिटे लागतात. कृपया जोडलेले राहा."
    }
    
    return {
        "response_text": responses.get(lang, responses["en"]),
        "interrupted": True,
        "interrupt_reason": interrupt_reason,
        "requires_hitl": True,
        "hitl_timestamp": time.time(),
        "status": "INTERRUPTED"
    }


async def hitl_resume_node(state: SarthiState) -> dict:
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
        "hi": "वीडियो वेरिफिकेशन मंजूर हो गया! आपका खाता अब पूरी तरह से वेरिफाइड है। आगे के स्टेप्स शुरू करते हैं।",
        "mr": "व्हिडिओ व्हेरिफिकेशन मंजूर झाले! तुमचे खाते आता पूर्णपणे व्हेरिफाय झाले आहे. पुढचे स्टेप्स सुरू करूया."
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
    
    loan_id = f"LN_SBI_2026_{hashlib.sha256((state['session_id'] + approver_id).encode('utf-8')).hexdigest()[:6]}"
    
    responses = {
        "en": f"Congratulations! Your loan of Rs. {loan_amount:,} is sanctioned by officer {approver_id}. Loan ID: {loan_id}. Disbursement will happen within 24 hours.",
        "hi": f"बधाई हो! आपका Rs. {loan_amount:,} का लोन अधिकारी {approver_id} द्वारा मंजूर हो गया है। लोन ID: {loan_id}। रकम 24 घंटे में जमा हो जाएगी।",
        "mr": f"अभिनंदन! तुमचे Rs. {loan_amount:,} चे लोन अधिकारी {approver_id} द्वारे मंजूर झाले आहे. लोन ID: {loan_id}। रक्कम २४ तासात जमा होईल."
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
        "hi": f"आपका कार्ड अधिकारी {approver_id} द्वारा सुरक्षा के लिए ब्लॉक कर दिया गया है। नया कार्ड 3 वर्किंग डेज में भेजा जाएगा। चार्ज बैक प्रोसेस शुरू हो गया है।",
        "mr": f"तुमचे कार्ड अधिकारी {approver_id} द्वारे सुरक्षेसाठी ब्लॉक केले गेले आहे. नवीन कार्ड ३ वर्किंग डेजमध्ये पाठवले जाईल. चार्ज बॅक प्रोसेस सुरू झाली आहे."
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
        "hi": "आपकी रिक्वेस्ट मंजूर हो गई है। अब आगे बढ़ रहे हैं।",
        "mr": "तुमची रिक्वेस्ट मंजूर झाली आहे. आता पुढे जात आहे."
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
        "hi": "आपकी रिक्वेस्ट रिव्यू की गई है और इस समय मंजूर नहीं की जा सकती। कृपया मदद के लिए अपनी नज़दीकी SBI ब्रांच विजिट करें।",
        "mr": "तुमची रिक्वेस्ट रिव्ह्यू केली गेली आहे आणि यावेळी मंजूर केली जाऊ शकत नाही. कृपया मदतीसाठी तुमच्या जवळील SBI ब्रांचला भेट द्या."
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
