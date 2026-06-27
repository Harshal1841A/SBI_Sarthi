from dotenv import load_dotenv
load_dotenv()
import hashlib
import json
import time
from typing import List, Dict, Optional
from datetime import datetime

# ────────────────────────────────────────────────────────────────
# Immutable Audit Trail — RBI FREE-AI + DPDP Compliance
# Hash-chain artifacts for every agent decision.
# SHA-256 + prev_hash link for tamper detection.
# Persisted to append-only JSONL for restart survival.
# ────────────────────────────────────────────────────────────────

import structlog
import os

logger = structlog.get_logger("audit")

_audit_chain: List[dict] = []
_AUDIT_LOG_PATH = os.environ.get("SARTHI_AUDIT_LOG", os.path.join(os.path.expanduser("~"), ".sarthi_cache", "audit.jsonl"))

def _load_audit_chain() -> None:
    """Load existing audit records from disk on startup."""
    global _audit_chain
    if os.path.exists(_AUDIT_LOG_PATH):
        try:
            with open(_AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                _audit_chain = [json.loads(line) for line in f if line.strip()]
        except Exception as e:
            logger.error("Failed to load audit log", error=str(e))
            _audit_chain = []

def _append_audit_to_disk(artifact: dict) -> None:
    """Append a single audit artifact to the persistent JSONL file."""
    try:
        os.makedirs(os.path.dirname(_AUDIT_LOG_PATH), mode=0o700, exist_ok=True)
        with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(artifact, default=str) + "\n")
    except Exception as e:
        logger.error("Failed to persist audit artifact", error=str(e))

# Load on module import
_load_audit_chain()


def create_audit_artifact(
    event_type: str,
    session_id: str,
    agent_name: str,
    decision: dict,
    state_snapshot: dict,
    prev_hash: Optional[str] = None
) -> dict:
    """Create an immutable audit artifact for any significant event.
    
    Event types:
    - "agent_decision": Any agent routing or action decision
    - "hitl_interrupt": Human-in-the-loop triggered
    - "hitl_approval": Human approved/rejected an action
    - "consent_grant": Consent granted or rejected
    - "consent_revoke": Consent revoked
    - "shield_block": Shield agent blocked an action
    - "shield_flag": Shield agent flagged but allowed
    - "transaction_auth": Voice/transaction authorization
    - "saga_compensation": Saga rollback executed
    - "pii_scrub": PII scrubbing applied
    - "prompt_injection": Injection attempt detected
    """
    artifact = {
        "event_type": event_type,
        "session_id": session_id,
        "agent_name": agent_name,
        "decision": decision,
        "state_snapshot": _sanitize_state(state_snapshot),
        "timestamp": time.time(),
        "timestamp_iso": datetime.utcnow().isoformat() + "Z",
        "prev_hash": prev_hash or (_audit_chain[-1]["hash"] if _audit_chain else "0" * 64)
    }
    
    # SHA-256 hash
    payload = json.dumps({k: v for k, v in artifact.items() if k != "hash"}, sort_keys=True).encode('utf-8')
    artifact["hash"] = hashlib.sha256(payload).hexdigest()
    
    _audit_chain.append(artifact)
    _append_audit_to_disk(artifact)
    logger.info("Audit event recorded", event_type=event_type, session_id=session_id, hash=artifact["hash"])
    return artifact


def _sanitize_state(state: dict) -> dict:
    """Remove sensitive fields from state snapshot for audit.
    Aadhaar, PAN, and other PII are NEVER stored in audit logs.
    """
    if not state:
        return {}
    
    sensitive_keys = [
        "aadhaar_number", "pan_number", "kyc_token", 
        "account_id", "phone", "email", "dob"
    ]
    
    sanitized = {}
    for key, value in state.items():
        if key in sensitive_keys:
            sanitized[key] = "[REDACTED]"
        elif key == "messages" and isinstance(value, list):
            # Scrub PII from messages
            sanitized[key] = [_scrub_message(m) for m in value[-5:]]  # Last 5 only
        else:
            sanitized[key] = value
    
    return sanitized


def _scrub_message(msg: dict) -> dict:
    """Scrub PII from a single message for audit logging."""
    from security.pii_scrubber import scrub_pii
    if isinstance(msg, dict) and "content" in msg:
        return {
            "role": msg.get("role", "unknown"),
            "content": scrub_pii(msg.get("content", "")),
            "timestamp": msg.get("timestamp")
        }
    return msg


def verify_audit_chain() -> bool:
    """Verify integrity of the entire audit chain.
    Returns False immediately on any broken link.
    """
    for i, artifact in enumerate(_audit_chain):
        # Reconstruct payload
        payload_dict = {k: v for k, v in artifact.items() if k != "hash"}
        payload_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
        expected_hash = hashlib.sha256(payload_bytes).hexdigest()
        
        if artifact["hash"] != expected_hash:
            return False
        
        # Verify chain link
        if i > 0:
            if artifact["prev_hash"] != _audit_chain[i - 1]["hash"]:
                return False
        else:
            if artifact["prev_hash"] != "0" * 64:
                return False
    
    return True


def get_audit_logs(
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    start_time: Optional[float] = None,
    end_time: Optional[float] = None,
    limit: int = 100
) -> List[dict]:
    """Query audit logs with filters."""
    logs = _audit_chain
    
    if session_id:
        logs = [l for l in logs if l["session_id"] == session_id]
    if event_type:
        logs = [l for l in logs if l["event_type"] == event_type]
    if start_time:
        logs = [l for l in logs if l["timestamp"] >= start_time]
    if end_time:
        logs = [l for l in logs if l["timestamp"] <= end_time]
    
    return logs[-limit:]


def get_audit_stats() -> dict:
    """Get summary statistics for the audit trail."""
    if not _audit_chain:
        return {"total_events": 0, "chain_integrity": True}
    
    event_counts = {}
    for artifact in _audit_chain:
        event_counts[artifact["event_type"]] = event_counts.get(artifact["event_type"], 0) + 1
    
    return {
        "total_events": len(_audit_chain),
        "chain_integrity": verify_audit_chain(),
        "event_breakdown": event_counts,
        "first_event": _audit_chain[0]["timestamp_iso"],
        "last_event": _audit_chain[-1]["timestamp_iso"]
    }
