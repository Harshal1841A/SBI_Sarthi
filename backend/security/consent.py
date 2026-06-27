from dotenv import load_dotenv
load_dotenv()
import hashlib
import hmac as hmac_module
import json
import time
import os
from typing import List, Optional
from datetime import datetime

# ────────────────────────────────────────────────────────────────
# Hash-Chain Consent Artifacts — DPDP Act 2023 Compliance
# Immutable, cryptographically linked consent records.
# Every consent is a separate artifact (NOT bundled).
# 4 distinct purposes: P001, P002, P003, P004
# ────────────────────────────────────────────────────────────────

# FIX#4: Load SERVER_SECRET from environment — never generate at runtime.
# A new random secret on every server restart makes all stored HMACs unverifiable.
# One-time setup: python -c "import secrets; print(secrets.token_hex(32))"
# Store in .env as: SARTHI_HMAC_SECRET=<64-char hex string>
_raw_secret = os.environ.get("SARTHI_HMAC_SECRET", "")
if not _raw_secret or len(_raw_secret) < 64 or _raw_secret.startswith("GENERATE_ME") or _raw_secret == "0" * 64:
    import logging
    logging.warning("SARTHI_HMAC_SECRET not set or invalid. Using prototype default secret for demo environment.")
    _raw_secret = "a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0"

try:
    SERVER_SECRET: bytes = bytes.fromhex(_raw_secret[:64])
except ValueError:
    SERVER_SECRET = bytes.fromhex("a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0")

# Consent purpose definitions per DPDP Act 2023 + RBI norms
CONSENT_PURPOSES = {
    "P001": {
        "name": "KYC Verification",
        "description": "Identity verification for account opening and maintenance",
        "retention": "As long as account is active",
        "mandatory": True,
        "revocable": False
    },
    "P002": {
        "name": "Credit Risk Assessment",
        "description": "Credit score and risk evaluation for loan/credit card applications",
        "retention": "7 years per RBI norms",
        "mandatory": False,
        "revocable": False  # RBI mandates retention
    },
    "P003": {
        "name": "Personalized Product Recommendations",
        "description": "AI-driven product recommendations based on transaction patterns",
        "retention": "2 years",
        "mandatory": False,
        "revocable": True
    },
    "P004": {
        "name": "Marketing Communications",
        "description": "Promotional offers, new product announcements via WhatsApp/SMS",
        "retention": "1 year",
        "mandatory": False,
        "revocable": True
    }
}


class ConsentError(Exception):
    """Raised when consent operations fail."""
    pass


def create_consent_artifact(
    user_id: str,
    purpose_id: str,
    lang: str,
    granted: bool,
    prev_hash: str = "0" * 64,
    channel: str = "unknown"
) -> dict:
    """Create a cryptographically immutable consent artifact.
    
    Args:
        user_id: Unique user identifier
        purpose_id: One of P001, P002, P003, P004
        lang: ISO 639-1 language code
        granted: True/False — explicit rejection is also recorded
        prev_hash: SHA-256 hash of previous consent artifact in chain
        channel: "voice", "chat", "whatsapp", "app"
        
    Returns:
        Artifact dict with hash, hmac_sig, and all metadata.
    """
    if purpose_id not in CONSENT_PURPOSES:
        raise ConsentError(f"Invalid purpose_id: {purpose_id}")
    
    artifact = {
        "user_id": user_id,
        "purpose_id": purpose_id,
        "purpose_name": CONSENT_PURPOSES[purpose_id]["name"],
        "language": lang,
        "granted": granted,
        "timestamp": time.time(),
        "timestamp_iso": datetime.utcnow().isoformat() + "Z",
        "prev_hash": prev_hash,
        "channel": channel,
        "retention": CONSENT_PURPOSES[purpose_id]["retention"],
        "revocable": CONSENT_PURPOSES[purpose_id]["revocable"]
    }
    
    # SHA-256 hash of the payload (excluding hash and hmac_sig themselves)
    payload = json.dumps({k: v for k, v in artifact.items() if k not in ("hash", "hmac_sig")}, sort_keys=True).encode('utf-8')
    artifact["hash"] = hashlib.sha256(payload).hexdigest()
    
    # HMAC-SHA256 for tamper detection (FIX#3: use hmac_module, key is "hmac_sig")
    artifact["hmac_sig"] = hmac_module.new(
        SERVER_SECRET,
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return artifact


def verify_consent_artifact(artifact: dict) -> bool:
    """Verify integrity of a single consent artifact.
    Returns True if hash and HMAC both match.
    """
    # Reconstruct payload
    payload_dict = {k: v for k, v in artifact.items() if k not in ("hash", "hmac_sig")}
    payload_bytes = json.dumps(payload_dict, sort_keys=True).encode('utf-8')
    
    # Verify SHA-256 hash
    expected_hash = hashlib.sha256(payload_bytes).hexdigest()
    if artifact.get("hash") != expected_hash:
        return False
    
    # Verify HMAC
    expected_hmac = hmac_module.new(
        SERVER_SECRET,
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    if artifact.get("hmac_sig") != expected_hmac:
        return False
    
    return True


def verify_consent_chain(artifacts: List[dict]) -> bool:
    """Verify integrity of the full hash-chain.
    Returns False immediately on first broken link or invalid HMAC.
    """
    for i, artifact in enumerate(artifacts):
        # Verify individual artifact integrity
        if not verify_consent_artifact(artifact):
            return False
        
        # Verify hash chain link (except for genesis block)
        if i > 0:
            if artifact["prev_hash"] != artifacts[i - 1]["hash"]:
                return False
        else:
            # Genesis block: prev_hash must be all zeros
            if artifact["prev_hash"] != "0" * 64:
                return False
    
    return True


# Persistent storage for consent artifacts (replace with PostgreSQL in production)
_CONSENT_STORE_DIR = os.environ.get("SARTHI_CONSENT_DIR", os.path.join(os.path.expanduser("~"), ".sarthi_cache", "consents"))


def _get_consent_path(user_id: str) -> str:
    """Return the file path for a user's consent chain."""
    safe_user_id = hashlib.sha256(user_id.encode()).hexdigest()[:16]
    return os.path.join(_CONSENT_STORE_DIR, f"{safe_user_id}.json")


def _load_consent_chain(user_id: str) -> List[dict]:
    """Load a user's consent chain from disk."""
    path = _get_consent_path(user_id)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def _save_consent_chain(user_id: str, chain: List[dict]) -> None:
    """Persist a user's consent chain to disk."""
    try:
        os.makedirs(_CONSENT_STORE_DIR, mode=0o700, exist_ok=True)
        path = _get_consent_path(user_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(chain, f, default=str)
    except Exception as e:
        print(f"Failed to persist consent chain: {e}")


def store_consent_artifact(artifact: dict) -> None:
    """Store consent artifact in append-only chain (memory + disk)."""
    user_id = artifact["user_id"]
    chain = _load_consent_chain(user_id)
    chain.append(artifact)
    _save_consent_chain(user_id, chain)


def get_consent_chain(user_id: str) -> List[dict]:
    """Retrieve full consent chain for a user."""
    return _load_consent_chain(user_id)


def get_last_consent_hash(user_id: str) -> str:
    """Get the hash of the last consent artifact for chain linking."""
    chain = _load_consent_chain(user_id)
    if not chain:
        return "0" * 64
    return chain[-1]["hash"]


def get_user_consents(user_id: str) -> List[dict]:
    """Get all consent artifacts for a user with current status."""
    chain = _load_consent_chain(user_id)
    # Return latest state per purpose_id
    latest_by_purpose = {}
    for artifact in chain:
        pid = artifact["purpose_id"]
        # If there's a newer artifact, it overrides
        if pid not in latest_by_purpose or artifact["timestamp"] > latest_by_purpose[pid]["timestamp"]:
            latest_by_purpose[pid] = artifact
    
    return list(latest_by_purpose.values())


def revoke_consent_artifact(user_id: str, purpose_id: str) -> dict:
    """Revoke a consent by appending a new artifact with granted=False.
    This is append-only — the original grant is NOT deleted.
    """
    if purpose_id not in CONSENT_PURPOSES:
        raise ConsentError(f"Invalid purpose_id: {purpose_id}")
    
    if not CONSENT_PURPOSES[purpose_id]["revocable"]:
        raise ConsentError(f"Purpose {purpose_id} cannot be revoked (RBI mandated retention)")
    
    artifact = create_consent_artifact(
        user_id=user_id,
        purpose_id=purpose_id,
        lang="en",  # Default for revocation
        granted=False,
        prev_hash=get_last_consent_hash(user_id),
        channel="app"
    )
    store_consent_artifact(artifact)
    return artifact


def get_consent_notice(purpose_id: str, lang: str = "en") -> dict:
    """Get the consent notice text for a given purpose and language.
    For prototype: returns English/Hindi/Marathi templates.
    Production: full 22 Eighth Schedule language templates via IndicTrans2.
    """
    purpose = CONSENT_PURPOSES.get(purpose_id)
    if not purpose:
        return {"error": "Invalid purpose"}
    
    # Pre-translated templates for 3 priority languages
    templates = {
        "P001": {
            "en": f"Your data will be used for {purpose['name']}. Retained: {purpose['retention']}. Do you consent?",
            "hi": f"आपका डेटा {purpose['name']} के लिए उपयोग किया जाएगा। रिटेंशन: {purpose['retention']}। क्या आप सहमत हैं?",
            "mr": f"तुमचा डेटा {purpose['name']} साठी वापरला जाईल. रिटेंशन: {purpose['retention']}. तुम्ही सहमत आहात का?"
        },
        "P002": {
            "en": f"Your data may be used for {purpose['name']}. Retained: {purpose['retention']}. Do you consent?",
            "hi": f"आपका डेटा {purpose['name']} के लिए उपयोग किया जा सकता है। रिटेंशन: {purpose['retention']}। क्या आप सहमत हैं?",
            "mr": f"तुमचा डेटा {purpose['name']} साठी वापरला जाऊ शकतो. रिटेंशन: {purpose['retention']}. तुम्ही सहमत आहात का?"
        },
        "P003": {
            "en": f"We can recommend SBI products based on your spending. Retained: {purpose['retention']}. Revocable anytime. Do you consent?",
            "hi": f"हम आपके खर्च के आधार पर SBI उत्पाद सुझा सकते हैं। रिटेंशन: {purpose['retention']}। कभी भी रद्द कर सकते हैं। क्या आप सहमत हैं?",
            "mr": f"आम्ही तुमच्या खर्चावर आधारित SBI उत्पादने सूचवू शकतो. रिटेंशन: {purpose['retention']}. कधीही रद्द करता येते. तुम्ही सहमत आहात का?"
        },
        "P004": {
            "en": f"Receive marketing messages from SBI (offers, new products). Retained: {purpose['retention']}. Revocable anytime. Do you consent?",
            "hi": f"SBI से मार्केटिंग संदेश प्राप्त करें (ऑफर, नए उत्पाद)। रिटेंशन: {purpose['retention']}। कभी भी रद्द कर सकते हैं। क्या आप सहमत हैं?",
            "mr": f"SBI कडून मार्केटिंग मेसेज मिळवा (ऑफर्स, नवीन उत्पादने). रिटेंशन: {purpose['retention']}. कधीही रद्द करता येते. तुम्ही सहमत आहात का?"
        }
    }
    
    text = templates.get(purpose_id, {}).get(lang, templates.get(purpose_id, {}).get("en", "Consent notice unavailable"))
    
    return {
        "purpose_id": purpose_id,
        "purpose_name": purpose["name"],
        "language": lang,
        "text": text,
        "mandatory": purpose["mandatory"],
        "revocable": purpose["revocable"],
        "retention": purpose["retention"]
    }
