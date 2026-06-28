from typing import Any
from state import SarthiState
from security.audit import create_audit_artifact

# ────────────────────────────────────────────────────────────────
# Compensation Node — Saga Pattern Rollback
# Executes compensating transactions in REVERSE order when any
# step in the onboarding saga fails.
# Steps: create_profile -> verify_kyc -> fund_account
# ────────────────────────────────────────────────────────────────


async def compensation_node(state: SarthiState) -> dict:
    """Compensation Node: execute Saga rollback in reverse order.
    
    Onboarding saga steps (in order):
    1. create_profile
    2. verify_kyc  
    3. fund_account
    
    Compensation (in reverse):
    1. Reverse fund_account (refund initial deposit)
    2. Invalidate KYC token
    3. Archive profile
    """
    completed_steps = state.get("completed_steps", [])
    logs = []
    
    # Process in reverse order
    for step in reversed(completed_steps):
        if step == "fund_account":
            result = _reverse_funding(state)
            acct_id = (result or {}).get('account_id') or 'unknown'
            status = (result or {}).get('status', 'unknown')
            logs.append(f"Reversed funding for account {acct_id[:8]}***: {status}")
        
        elif step == "v_kyc":
            result = _reverse_vkyc(state)
            logs.append(f"Reversed V-KYC verification: {result['status']}")
        
        elif step == "verify_kyc":
            result = _invalidate_kyc(state)
            logs.append(f"Invalidated KYC token {result['token_prefix']}***: {result['status']}")
        
        elif step == "create_profile":
            result = _archive_profile(state)
            logs.append(f"Archived profile {result['profile_id'][:8]}***: {result['status']}")
    
    create_audit_artifact(
        event_type="saga_compensation",
        session_id=state["session_id"],
        agent_name="compensation",
        decision={
            "original_status": state.get("status"),
            "completed_steps": completed_steps,
            "compensation_steps": len(logs)
        },
        state_snapshot=dict(state)
    )
    
    return {
        "compensation_log": logs,
        "status": "COMPENSATED",
        "response_text": _get_compensation_message(state),
        "onboarding_step": "idle",
        "completed_steps": []  # Clear completed steps after compensation
    }


def _reverse_funding(state: SarthiState) -> dict:
    """Mock: reverse account funding (refund initial deposit)."""
    account_id = state.get("account_id") or "unknown"
    
    # In production: call core banking API to reverse the initial deposit
    return {
        "account_id": account_id,
        "status": "reversed",
        "refund_amount": 500,
        "refund_initiated": True
    }


def _reverse_vkyc(state: SarthiState) -> dict:
    """Mock: reverse V-KYC verification."""
    return {
        "status": "invalidated",
        "vkyc_session_id": state.get("session_id", "unknown") + "_vkyc"
    }


def _invalidate_kyc(state: SarthiState) -> dict:
    """Mock: invalidate KYC token."""
    kyc_token = state.get("kyc_token", "unknown")
    return {
        "token_prefix": kyc_token[:10] if kyc_token != "unknown" else "unknown",
        "status": "invalidated"
    }


def _archive_profile(state: SarthiState) -> dict:
    """Mock: archive customer profile."""
    profile_id = state.get("profile_id") or f"prof_{state['session_id'][:8]}"
    return {
        "profile_id": profile_id,
        "status": "archived",
        "archive_date": "2026-06-18",
        "retention_days": 7  # User can resume within 7 days
    }


def _get_compensation_message(state: SarthiState) -> str:
    """Generate user-facing message after compensation."""
    lang = state.get("language", "en")
    
    responses = {
        "en": "We apologize, but there was a technical issue with your account setup. Your data is secure and any deposited amount will be refunded within 24 hours. Would you like to try again?",
        "hi": "Kshama kijiye, aapke account setup mein technical samasya aayi hai. Aapka data surakshit hai aur koi bhi jama rakam 24 ghante mein wapas ho jayegi. Kya aap dubara prayas karna chahenge?",
        "mr": "Kshama kara, tumchya account setup madhye technical samasya ali. Tumcha data surakshit ahe ani koni jama rakam 24 tasat parat milen. Tumhi parat prayatna karu ichchita ka?"
    }
    
    return responses.get(lang, responses["en"])


def check_onboarding_status_for_compensation(state: SarthiState) -> str:
    """Conditional edge from acquisition to determine if compensation is needed.
    Returns: 'done' or 'compensate'
    """
    if state.get("status") == "FAILED":
        return "compensate"
    return "done"
