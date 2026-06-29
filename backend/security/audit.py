from dotenv import load_dotenv
load_dotenv()
import hashlib
import json
import time
from typing import List, Dict, Optional, Any
from datetime import datetime
from contextlib import contextmanager

# ────────────────────────────────────────────────────────────────
# Immutable Audit Trail — RBI FREE-AI + DPDP Compliance
# Hash-chain artifacts for every agent decision.
# SHA-256 + prev_hash link for tamper detection.
# Persisted to append-only JSONL for restart survival.
# ────────────────────────────────────────────────────────────────

import structlog
import os

logger = structlog.get_logger("audit")

_AUDIT_LOG_PATH = os.environ.get("SARTHI_AUDIT_LOG", os.path.join(os.path.expanduser("~"), ".sarthi_cache", "audit.jsonl"))

@contextmanager
def _file_lock(path: str, timeout: float = 2.0):
    lock_path = path + ".lock"
    start_time = time.time()
    fd = None
    while time.time() - start_time < timeout:
        if os.path.exists(lock_path):
            try:
                if time.time() - os.path.getmtime(lock_path) > 5.0:
                    os.remove(lock_path)
            except OSError:
                pass
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except OSError:
            time.sleep(0.005)
    if fd is None:
        logger.warning("lock_acquire_timeout", path=path)
        # Do NOT yield — raise so callers know the operation is unsafe
        raise RuntimeError(f"Could not acquire audit lock on {path} within {timeout}s")
    else:
        os.close(fd)
    try:
        yield
    finally:
        if os.path.exists(lock_path):
            try:
                os.remove(lock_path)
            except OSError:
                pass

def _get_chain_from_disk() -> List[dict]:
    """Load existing audit records from disk dynamically for multi-worker consistency."""
    if os.path.exists(_AUDIT_LOG_PATH):
        try:
            with _file_lock(_AUDIT_LOG_PATH):
                with open(_AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
                    return [json.loads(line) for line in f if line.strip()]
        except Exception as e:
            logger.error("Failed to load audit log", error=str(e))
    return []

def _get_last_hash_from_disk() -> str:
    """O(1) last hash lookup avoiding full log read."""
    if not os.path.exists(_AUDIT_LOG_PATH):
        return "0" * 64
    try:
        # For read operations, attempt lock but fall back to reading without it
        # if the lock is contended (read is safer than a failed write).
        try:
            lock_ctx = _file_lock(_AUDIT_LOG_PATH, timeout=0.5)
            lock_ctx.__enter__()
            locked = True
        except RuntimeError:
            locked = False
            lock_ctx = None
        try:
            with open(_AUDIT_LOG_PATH, "rb") as f:
                try:
                    f.seek(-2048, os.SEEK_END)
                except OSError:
                    f.seek(0)
                lines = f.read().splitlines()
                for line in reversed(lines):
                    if line.strip():
                        try:
                            return json.loads(line.decode('utf-8'))["hash"]
                        except (json.JSONDecodeError, KeyError, UnicodeDecodeError):
                            # Skip malformed/truncated lines from crash-mid-write (BUG M6)
                            continue
        finally:
            if locked and lock_ctx is not None:
                try:
                    lock_ctx.__exit__(None, None, None)
                except Exception:
                    pass
    except Exception as e:
        logger.warning("Failed to read last audit hash (using genesis hash)", error=str(e))
    return "0" * 64

def _append_audit_to_disk(artifact: dict) -> None:
    """Append a single audit artifact to the persistent JSONL file."""
    try:
        os.makedirs(os.path.dirname(_AUDIT_LOG_PATH), mode=0o700, exist_ok=True)
        with _file_lock(_AUDIT_LOG_PATH):
            with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(artifact, default=str) + "\n")
    except Exception as e:
        logger.error("Failed to persist audit artifact", error=str(e))


def create_audit_artifact(
    event_type: str,
    session_id: str,
    agent_name: str,
    decision: dict,
    state_snapshot: dict,
    prev_hash: Optional[str] = None
) -> dict:
    """Create an immutable audit artifact for any significant event."""
    last_hash = prev_hash or _get_last_hash_from_disk()
    
    artifact = {
        "event_type": event_type,
        "session_id": session_id,
        "agent_name": agent_name,
        "decision": decision,
        "state_snapshot": _sanitize_state(state_snapshot),
        "timestamp": time.time(),
        "timestamp_iso": datetime.utcnow().isoformat() + "Z",
        "prev_hash": last_hash
    }
    
    # SHA-256 hash
    payload = json.dumps({k: v for k, v in artifact.items() if k != "hash"}, sort_keys=True).encode('utf-8')
    artifact["hash"] = hashlib.sha256(payload).hexdigest()
    
    _append_audit_to_disk(artifact)
    logger.info("Audit event recorded", event_type=event_type, session_id=session_id, hash=artifact["hash"])
    return artifact


def _sanitize_state(state: Any) -> Any:
    """Remove sensitive fields recursively from state snapshot for audit.
    Aadhaar, PAN, and other PII are NEVER stored in audit logs.
    """
    if isinstance(state, dict):
        sensitive_keys = {
            "aadhaar_number", "pan_number", "kyc_token", 
            "account_id", "phone", "email", "dob", "password", "secret"
        }
        sanitized = {}
        for key, value in state.items():
            if key in sensitive_keys:
                sanitized[key] = "[REDACTED]"
            elif key == "messages" and isinstance(value, list):
                # Scrub PII from messages
                sanitized[key] = [_scrub_message(m) for m in value[-5:]]  # Last 5 only
            else:
                sanitized[key] = _sanitize_state(value)
        return sanitized
    elif isinstance(state, list):
        return [_sanitize_state(item) for item in state]
    return state


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
    chain = _get_chain_from_disk()
    for i, artifact in enumerate(chain):
        # Reconstruct payload
        payload_dict = {k: v for k, v in artifact.items() if k != "hash"}
        payload_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
        expected_hash = hashlib.sha256(payload_bytes).hexdigest()
        
        if artifact["hash"] != expected_hash:
            return False
        
        # Verify chain link
        if i > 0:
            if artifact["prev_hash"] != chain[i - 1]["hash"]:
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
    logs = _get_chain_from_disk()
    
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
    chain = _get_chain_from_disk()
    if not chain:
        return {"total_events": 0, "chain_integrity": True}
    
    event_counts = {}
    for artifact in chain:
        event_counts[artifact["event_type"]] = event_counts.get(artifact["event_type"], 0) + 1
    
    return {
        "total_events": len(chain),
        "chain_integrity": verify_audit_chain(),
        "event_breakdown": event_counts,
        "first_event": chain[0]["timestamp_iso"],
        "last_event": chain[-1]["timestamp_iso"]
    }
