from typing import TypedDict, Annotated, List, Optional, Any
import operator

def _append_message(messages: list, new_msg: dict) -> list:
    """Reducer helper: append a message to the conversation history."""
    return messages + [new_msg]

class SarthiState(TypedDict):
    """Immutable state schema for the Sarthi multi-agent orchestration graph.
    
    All fields are checkpointed via LangGraph SqliteSaver in WAL mode.
    Fields marked as Annotated with operator.add are REDUCER fields that
    accumulate across graph invocations (e.g., messages append).
    """
    # ── Core Identity ─────────────────────────────────────────────
    session_id: str
    user_id: Optional[str]
    language: str  # ISO 639-1 + script variant (e.g., "hi", "mr", "en", "hi-en")
    channel: str  # "voice", "chat", "whatsapp", "ivr"

    # ── Conversation ──────────────────────────────────────────────
    messages: Annotated[List[dict], operator.add]
    current_intent: Optional[str]
    extracted_entities: dict
    confidence_score: float

    # ── Onboarding (Acquisition) ──────────────────────────────────
    onboarding_step: str  # e.g., "idle", "collect_aadhaar", "collect_pan", "e_kyc", "v_kyc", "consent_collection", "fund_account"
    aadhaar_number: Optional[str]  # HASHED — never store raw
    aadhaar_last4: Optional[str]    # Masked display: "**** **** 0123"
    pan_number: Optional[str]     # HASHED — never store raw
    kyc_token: Optional[str]
    profile_id: Optional[str]
    account_id: Optional[str]
    document_images: Annotated[List[dict], operator.add]  # [{doc_type, url, extracted_text, validated}]

    # ── Saga Pattern ────────────────────────────────────────────────
    status: str  # "IDLE", "RUNNING", "FAILED", "COMPLETE", "COMPENSATED"
    completed_steps: Annotated[List[str], operator.add]
    compensation_log: Annotated[List[str], operator.add]
    last_error: Optional[str]

    # ── Compliance ────────────────────────────────────────────────
    consent_artifacts: Annotated[List[dict], operator.add]
    pii_scrubbed_input: str
    shield_flags: Annotated[List[str], operator.add]
    audit_log: Annotated[List[dict], operator.add]

    # ── HITL ────────────────────────────────────────────────────────
    interrupted: bool
    interrupt_reason: Optional[str]
    human_decision: Optional[dict]  # {"approved": bool, "reason": str, "approver_id": str}
    hitl_timestamp: Optional[float]

    # ── Response ────────────────────────────────────────────────────
    response_text: str
    response_stream: Optional[Any]  # async generator for streaming TTS
    audio_chunks: Annotated[List[bytes], operator.add]

    # ── Metadata ────────────────────────────────────────────────────
    metadata: dict  # timestamps, risk scores, agent routing history
    risk_score: float  # 0.0-1.0, recalculated by shield after each turn
    requires_hitl: bool
    next_agent: Optional[str]
