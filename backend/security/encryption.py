import hashlib
import os
import hmac
from typing import Optional
import structlog

logger = structlog.get_logger()

# ────────────────────────────────────────────────────────────────
# Field Encryption / Hashing — RBI Data Localisation Compliance
# One-way SHA-256 hashing for sensitive identifiers stored in state.
# Reversible encryption is NOT used here; for production, integrate
# with HSM or AWS KMS / Azure Key Vault.
# ────────────────────────────────────────────────────────────────

# Salt loaded from environment — must be set for deterministic hashing
_FIELD_SALT = os.environ.get("SARTHI_FIELD_SALT", "").encode("utf-8")

if not _FIELD_SALT:
    import secrets
    _FIELD_SALT = secrets.token_bytes(16)
    logger.warning("sarthi_field_salt_missing", message="Generated temporary salt. Set SARTHI_FIELD_SALT for deterministic hashing across restarts.")


def hash_field(value: str) -> str:
    """One-way SHA-256 hash of a sensitive field with application salt.
    
    Args:
        value: Raw sensitive value (e.g., Aadhaar number).
        
    Returns:
        Hex-encoded SHA-256 digest. Irreversible.
    """
    if not value:
        return ""
    payload = value.encode("utf-8") + _FIELD_SALT
    return hashlib.sha256(payload).hexdigest()


def verify_field_hash(value: str, hashed: str) -> bool:
    """Verify a raw value against a stored hash.
    
    Args:
        value: Raw value to check.
        hashed: Previously stored hash from hash_field().
        
    Returns:
        True if the value matches the hash.
    """
    if not value or not hashed:
        return False
    return hmac.compare_digest(hash_field(value), hashed)
