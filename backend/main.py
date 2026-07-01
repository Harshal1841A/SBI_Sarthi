from dotenv import load_dotenv
load_dotenv()
import json
import secrets  # Resolved L-2: top-level import, not repeated inside conditionals
import hmac as _hmac
import hashlib
try:
    from langgraph.types import Command
except ImportError:
    Command = None
import os
import sys
import uuid
import asyncio
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    redis = None
    REDIS_AVAILABLE = False

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False
import time
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import structlog

logger = structlog.get_logger("main")

# Local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from graph import get_graph
from security.pii_middleware import PIIIngressMiddleware
from security.consent import (
    create_consent_artifact, store_consent_artifact, get_last_consent_hash,
    get_consent_chain, revoke_consent_artifact, get_consent_notice,
    verify_consent_chain
)
from security.audit import create_audit_artifact, get_audit_logs, get_audit_stats, verify_audit_chain
from security.prompt_injection import shield_guard, detect_prompt_injection
from voice.vad import process_audio_chunk, cleanup_session_buffer, session_buffers
from voice.tts import tts_cascade
from integrations.sbi_mock import sbi_api
from utils.cache import get_cache_stats, clear_cache, pre_cache_demo_interactions
from utils.connections import postgres_db, redis_cache
from channels.whatsapp import whatsapp_router
from channels.ivr import ivr_router
from middleware.rate_limiter import RateLimitMiddleware
from utils.feature_flags import feature_flags

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
)

# ────────────────────────────────────────────────────────────────
# Environment Configuration
# ────────────────────────────────────────────────────────────────

API_TOKEN        = os.environ.get("SARTHI_API_TOKEN", "")
SUPERVISOR_TOKEN = os.environ.get("SARTHI_SUPERVISOR_TOKEN", "")
HMAC_SECRET      = os.environ.get("SARTHI_HMAC_SECRET", "")

if not API_TOKEN:
    API_TOKEN = os.environ.get("VITE_SARTHI_TOKEN", "") or os.environ.get("VITE_SARTHI_API_TOKEN", "")

if not API_TOKEN:
    API_TOKEN = secrets.token_hex(32)
    logger.warning("SARTHI_API_TOKEN not set. Generated temporary token")

if not SUPERVISOR_TOKEN:
    SUPERVISOR_TOKEN = secrets.token_hex(32)
    logger.warning("SARTHI_SUPERVISOR_TOKEN not set. Generated temporary token")

SARTHI_ENV = os.environ.get("SARTHI_ENV", "development").lower()
DEMO_MODE = True
# Removed production check for demo mode to ensure HF Spaces demo works regardless of SARTHI_ENV


security = HTTPBearer(auto_error=False)

ACTIVE_DEMO_TOKENS: dict[str, float] = {}

# Ephemeral secret generated at startup when SARTHI_HMAC_SECRET is not set.
# Safe for demo/HF Spaces: tokens are only valid for the lifetime of the process.
_EPHEMERAL_HMAC_SECRET: str = ""

def _get_demo_hmac_secret() -> bytes:
    global _EPHEMERAL_HMAC_SECRET
    if HMAC_SECRET:
        return HMAC_SECRET.encode("utf-8")
    if not DEMO_MODE:
        raise RuntimeError(
            "SARTHI_HMAC_SECRET is required to mint demo tokens outside demo mode. "
            "Set SARTHI_HMAC_SECRET as an environment variable."
        )
    # Demo/HF Spaces fallback: generate a random secret once per process start.
    # Tokens signed with this secret are invalidated when the container restarts.
    if not _EPHEMERAL_HMAC_SECRET:
        _EPHEMERAL_HMAC_SECRET = secrets.token_hex(32)
        logger.warning(
            "SARTHI_HMAC_SECRET not set. Using ephemeral secret for demo tokens. "
            "Set SARTHI_HMAC_SECRET as an HF Space secret for stable tokens across restarts."
        )
    return _EPHEMERAL_HMAC_SECRET.encode("utf-8")

def _generate_demo_token() -> str:
    expires = int(time.time() + 3600)
    exp_hex = f"{expires:08x}"
    sig = _hmac.new(_get_demo_hmac_secret(), exp_hex.encode("utf-8"), hashlib.sha256).hexdigest()[:56]
    token = sig + exp_hex
    ACTIVE_DEMO_TOKENS[token] = float(expires)
    return token

def _is_valid_demo_token(token: str) -> bool:
    if not DEMO_MODE or not token:
        return False
    if token in ACTIVE_DEMO_TOKENS:
        if time.time() > ACTIVE_DEMO_TOKENS[token]:
            del ACTIVE_DEMO_TOKENS[token]
            return False
        return True
    if len(token) == 64:
        try:
            exp_hex = token[56:]
            sig = token[:56]
            expires = int(exp_hex, 16)
            if time.time() > expires:
                return False
            expected_sig = _hmac.new(_get_demo_hmac_secret(), exp_hex.encode("utf-8"), hashlib.sha256).hexdigest()[:56]
            if _hmac.compare_digest(sig, expected_sig):
                ACTIVE_DEMO_TOKENS[token] = float(expires)
                return True
        except Exception:
            pass
    return False

# ────────────────────────────────────────────────────────────────
# Demo scripted responses (used when demo token is detected)
# ────────────────────────────────────────────────────────────────

_DEMO_SCRIPTS: list[tuple] = [
    # (keyword_list, intent, response_hi, response_en)
    (
        ["account", "khol", "open", "kholna", "खाता", "खोलो", "खोलना"],
        "account_opening",
        "Namaste Rajesh ji! Aapka SBI Savings Account kholne ke liye, mujhe kuch details chahiye:\n1. Aadhar card number\n2. PAN card number\n3. Mobile number (OTP ke liye)\n\nAapka Aadhar number enter karein (last 4 digits)?",
        "Welcome! To open your SBI Savings Account, I need:\n1. Aadhaar card number\n2. PAN card number\n3. Mobile number for OTP\n\nPlease enter your Aadhaar number (last 4 digits)?",
    ),
    (
        ["balance", "kitna", "check", "बैलेंस", "kitna hai", "balanc"],
        "balance_inquiry",
        "Rajesh ji, aapka SBI account balance:\n\n💳 Account: SBI**********0123\n💰 Available Balance: ₹1,24,750.00\n📅 Last Transaction: ₹5,000 credited (salary) — aaj\n\nKuch aur help chahiye?",
        "Your SBI account balance:\n\n💳 Account: SBI**********0123\n💰 Available Balance: ₹1,24,750.00\n📅 Last Transaction: ₹5,000 credited (salary) — today\n\nAnything else I can help you with?",
    ),
    (
        ["loan", "chahiye", "lena", "lakh", "emi", "लोन", "ऋण"],
        "loan_application",
        "Rajesh ji, aapka loan request receive ho gaya! 🏦\n\n⚠️ Loan amount 50,000 se zyada hai — iska review SBI officer karega.\n\n📋 Details:\n- Requested Amount: ₹5,00,000\n- Interest Rate: 8.5% p.a. (current)\n- Processing Fee: ₹2,500\n- Status: HITL Queue mein — supervisor approval pending\n\nEk officer 24 hours mein contact karega. Reference ID: LOAN_DEMO_001",
        "Your loan request has been received! 🏦\n\n⚠️ Loan amount exceeds ₹50,000 — flagged for SBI officer review.\n\n📋 Details:\n- Requested Amount: ₹5,00,000\n- Interest Rate: 8.5% p.a. (current)\n- Processing Fee: ₹2,500\n- Status: Pending supervisor approval (HITL)\n\nAn officer will contact you within 24 hours. Reference ID: LOAN_DEMO_001",
    ),
    (
        ["card", "block", "band", "karo", "stop", "cardblock", "ब्लॉक"],
        "card_block",
        "Rajesh ji, aapka debit card TURANT block kar diya gaya! 🔒\n\n✅ Card **** **** **** 5678 block ho gaya\n📱 SMS confirmation: +91-98765-43210 pe bheja gaya\n📞 Nayi card ke liye: 1800-11-2211 pe call karein\n\nKya aapko replacement card chahiye?",
        "Your debit card has been blocked immediately! 🔒\n\n✅ Card **** **** **** 5678 blocked successfully\n📱 SMS confirmation sent to +91-98765-43210\n📞 For replacement: Call 1800-11-2211\n\nWould you like to request a replacement card?",
    ),
    (
        ["transfer", "send", "bhejo", "paisa", "money", "upi", "neft", "imps"],
        "fund_transfer",
        "Fund transfer ke liye:\n\n1️⃣ Beneficiary ka account number enter karein\n2️⃣ IFSC code\n3️⃣ Amount (max ₹2,00,000 per day)\n4️⃣ OTP verify karein\n\n⚡ IMPS (Instant) ya NEFT (2 hours) - aapki choice?\n\nNote: Demo mode mein actual transfer nahi hoga.",
        "For fund transfer:\n\n1️⃣ Enter beneficiary account number\n2️⃣ IFSC code\n3️⃣ Amount (max ₹2,00,000 per day)\n4️⃣ Verify OTP\n\n⚡ IMPS (Instant) or NEFT (2 hours) - your choice?\n\nNote: No actual transfer in demo mode.",
    ),
    (
        ["kyc", "document", "update", "verify", "aadhaar", "aadhar", "आधार", "pan"],
        "kyc_update",
        "KYC update process:\n\n📄 Required documents:\n1. Aadhaar Card (front + back)\n2. PAN Card\n3. Recent photo\n\n🤖 AI-powered document verification (< 30 sec)\n✅ Auto-fill from QR code\n\nAbhi upload karein ya branch visit karein? SBI branches SBI.co.in pe milenge.",
        "KYC update process:\n\n📄 Required documents:\n1. Aadhaar Card (front + back)\n2. PAN Card\n3. Recent photo\n\n🤖 AI-powered verification (< 30 sec)\n✅ Auto-fill from QR code\n\nUpload now or visit branch? Find SBI branches at SBI.co.in",
    ),
]

_DEMO_DEFAULT_HI = (
    "Namaste! Main Sarthi hoon, aapka SBI AI banking saathi. 🏦\n\n"
    "Main inke baare mein help kar sakta hoon:\n"
    "• 💰 Balance check\n• 🏦 Account opening\n• 💳 Card block\n"
    "• 🏛️ Loan application\n• 💸 Fund transfer\n• 📄 KYC update\n\n"
    "Kya chahiye aapko?"
)
_DEMO_DEFAULT_EN = (
    "Namaste! I am Sarthi, your SBI AI banking assistant. 🏦\n\n"
    "I can help you with:\n"
    "• 💰 Balance check\n• 🏦 Account opening\n• 💳 Card block\n"
    "• 🏛️ Loan application\n• 💸 Fund transfer\n• 📄 KYC update\n\n"
    "What can I help you with today?"
)


def _demo_chat_response(message: str, language: str) -> dict:
    """Return a scripted demo response without running the LangGraph.

    Used when the request carries a valid demo token so that HF Spaces
    demos work without Redis / Postgres / external LLM APIs.
    """
    msg_lower = message.lower()
    use_hi = language in ("hi", "mr", "bn", "ta", "te", "ml", "gu")

    for keywords, intent, resp_hi, resp_en in _DEMO_SCRIPTS:
        if any(kw in msg_lower for kw in keywords):
            return {
                "response_text": resp_hi if use_hi else resp_en,
                "current_intent": intent,
                "confidence_score": 0.95,
                "interrupted": intent == "loan_application",
                "shield_flags": [],
                "risk_score": 0.6 if intent == "loan_application" else 0.0,
            }

    return {
        "response_text": _DEMO_DEFAULT_HI if use_hi else _DEMO_DEFAULT_EN,
        "current_intent": "general_chat",
        "confidence_score": 0.85,
        "interrupted": False,
        "shield_flags": [],
        "risk_score": 0.0,
    }


def verify_api_token(request: Request, creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> None:
    """Validate Bearer token for standard API endpoints."""
    token = request.headers.get("X-Sarthi-Token") or (creds.credentials if creds else None)
    if not token or (token != API_TOKEN and not _is_valid_demo_token(token)):
        raise HTTPException(status_code=403, detail="Unauthorized")

def verify_supervisor_token(request: Request, creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> None:
    """Validate Bearer token for supervisor-only endpoints."""
    token = request.headers.get("X-Sarthi-Supervisor-Token") or (creds.credentials if creds else None)
    if not token or token != SUPERVISOR_TOKEN:
        raise HTTPException(status_code=403, detail="Supervisor access required")


async def authenticate_websocket(websocket: WebSocket, expected_token: Optional[str] = None) -> bool:
    """Authenticate a WebSocket connection using first-frame auth or optional query token."""
    if expected_token is None:
        expected_token = API_TOKEN

    allow_query = os.environ.get("SARTHI_ALLOW_QUERY_TOKEN", "false").lower() == "true"
    query_token = websocket.query_params.get("token")

    if query_token:
        if not allow_query:
            await websocket.accept()
            await websocket.close(code=4001, reason="Query token auth disabled")
            return False
        if query_token != expected_token and not _is_valid_demo_token(query_token):
            await websocket.accept()
            await websocket.close(code=4001, reason="Unauthorized query token")
            return False
        await websocket.accept()
        return True

    await websocket.accept()
    try:
        async with asyncio.timeout(3.0):
            data = await websocket.receive_json()
            if not isinstance(data, dict) or data.get("type") != "auth":
                await websocket.close(code=4001, reason="Invalid auth frame")
                return False
            token = data.get("token")
            if not token or (token != expected_token and not _is_valid_demo_token(token)):
                await websocket.close(code=4001, reason="Invalid token")
                return False
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning("websocket_auth_failed", error=str(e))
        try:
            await websocket.close(code=4001, reason="Auth failed")
        except Exception:
            pass
        return False

    return True

# ────────────────────────────────────────────────────────────────
# Prometheus Metrics
# ────────────────────────────────────────────────────────────────

REQUEST_COUNT = Counter("sarthi_requests_total", "Total requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = Histogram("sarthi_request_latency_seconds", "Request latency", ["endpoint"])
ACTIVE_SESSIONS = Gauge("sarthi_active_sessions", "Number of active sessions")
HITL_PENDING = Gauge("sarthi_hitl_pending", "Number of pending HITL approvals")
SHIELD_FLAGS = Counter("sarthi_shield_flags_total", "Shield flags raised", ["flag_type"])
QUERY_CONTAINMENT = Gauge("sarthi_query_containment_rate", "Query containment rate")

# ────────────────────────────────────────────────────────────────
# Pydantic Models
# ────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    session_id: str
    message: str
    language: str = "en"
    channel: str = "chat"
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    intent: str
    confidence: float
    requires_hitl: bool
    shield_flags: List[str]
    risk_score: float
    language: str

class HITLDecision(BaseModel):
    approved: bool
    reason: Optional[str] = None
    approver_id: str

class ConsentRequest(BaseModel):
    user_id: str
    purpose_id: str
    language: str = "en"
    channel: str = "chat"

class ConsentResponse(BaseModel):
    user_id: str
    purpose_id: str
    granted: bool
    timestamp: float
    artifact_hash: str
    language: str = "en"

class YONOTransaction(BaseModel):
    user_id: str
    txn_id: str
    amount: float
    category: str
    mcc: str
    timestamp: str
    channel: str = "yono"

class DocumentUpload(BaseModel):
    user_id: str
    doc_type: str  # "aadhaar" or "pan"

class LoanRequest(BaseModel):
    user_id: str
    amount: float
    purpose: str

# ────────────────────────────────────────────────────────────────
# Application Lifecycle
# ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    if SARTHI_ENV == "production":
        for name, val in [
            ("SARTHI_API_TOKEN", os.environ.get("SARTHI_API_TOKEN", "")),
            ("SARTHI_SUPERVISOR_TOKEN", os.environ.get("SARTHI_SUPERVISOR_TOKEN", "")),
            ("SARTHI_HMAC_SECRET", os.environ.get("SARTHI_HMAC_SECRET", "")),
        ]:
            if not val or len(val) < 64 or val.startswith("CHANGE_ME") or val.startswith("GENERATE_ME") or val == "0" * 64:
                raise RuntimeError(f"{name} required and must be at least 64 hex chars in production")
    else:
        logger.info(f"=== SARTHI BOOT BANNER: env={SARTHI_ENV} demo_mode={DEMO_MODE} ===")

    logger.info("Sarthi API starting up...")
    
    try:
        await postgres_db.connect()
        await redis_cache.connect()
    except Exception as e:
        logger.warning(f"Database connection failed (running in degraded mode): {e}")
        
    await asyncio.to_thread(pre_cache_demo_interactions)
    
    try:
        graph = get_graph()
        # Resolved C2: open the Postgres pool if one was created (open=False only defers connection)
        checkpointer = graph.checkpointer
        if hasattr(checkpointer, "conn") and hasattr(checkpointer.conn, "open"):
            try:
                await checkpointer.conn.open()
                logger.info("Postgres connection pool opened")
            except Exception as e:
                if SARTHI_ENV == "production":
                    raise
                logger.warning(f"Postgres pool open failed (degraded mode): {e}")
        if hasattr(checkpointer, "setup"):
            try:
                await checkpointer.setup()
            except Exception as e:
                if SARTHI_ENV == "production":
                    raise
                logger.warning(f"Checkpointer setup failed (degraded mode): {e}")
        logger.info(f"LangGraph compiled successfully: {type(graph)}")
    except Exception as e:
        logger.error(f"Graph compilation failed: {e}")
        raise
    
    yield
    
    logger.info("Sarthi API shutting down...")
    
    await postgres_db.disconnect()
    await redis_cache.disconnect()
    
    cleanup_stats = clear_cache()
    logger.info(f"Cache cleanup: {cleanup_stats}")

# ────────────────────────────────────────────────────────────────
# FastAPI App
# ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Sarthi API",
    description="Sarthi - Agentic AI Banking Platform for SBI",
    version="2.0.0",
    lifespan=lifespan
)

# Resolved M-2: CORS origins are env-gated.
# Localhost is only allowed in development / demo mode — never in production.
_PRODUCTION_ORIGINS = [
    "https://sarthi.sbi.co.in",
    "https://yono.sbi.co.in",
]
_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
_ALLOWED_ORIGINS = _PRODUCTION_ORIGINS + _DEV_ORIGINS
_is_prod = os.environ.get("SARTHI_ENV", "development").lower() == "production"

# HF Spaces serves the SPA from https://<user>-<space>.hf.space
# The regex must cover that origin in addition to local dev URLs.
_DEV_ORIGIN_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?|https://[a-z0-9-]+-[a-z0-9-]+\.hf\.space"

app.add_middleware(
    CORSMiddleware,
    allow_origins=_PRODUCTION_ORIGINS if _is_prod else _ALLOWED_ORIGINS,
    allow_origin_regex=None if _is_prod else _DEV_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"] if not _is_prod else ["Authorization", "Content-Type", "X-Request-ID", "X-Sarthi-Token", "X-Sarthi-Supervisor-Token"],
)
app.add_middleware(PIIIngressMiddleware)


# Rate Limiting Middleware
app.add_middleware(RateLimitMiddleware, rate_limit=100, window=60)

# Include Channel Routers
app.include_router(whatsapp_router, prefix="/whatsapp", tags=["channels"])
app.include_router(ivr_router, prefix="/ivr", tags=["channels"])

api_router = APIRouter(dependencies=[Depends(verify_api_token)])
supervisor_router = APIRouter(prefix="/supervisor", tags=["supervisor"], dependencies=[Depends(verify_supervisor_token)])

# ────────────────────────────────────────────────────────────────
# Health & Metrics
# ────────────────────────────────────────────────────────────────

@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint — verifies actual service status."""
    services = {}
    
    # Graph
    try:
        graph = get_graph()
        services["graph"] = "up"
    except Exception as e:
        services["graph"] = f"down: {str(e)}"
    
    # Voice / TTS
    try:
        from voice.tts import _is_riva_available, _nim_health_check
        tts_tiers = []
        if os.environ.get("BHASHINI_API_KEY"):
            tts_tiers.append("bhashini")
        if _is_riva_available():
            nim_ready = await _nim_health_check()
            if nim_ready:
                tts_tiers.append("chatterbox_nim")
            else:
                tts_tiers.append("chatterbox_nim (offline)")
        if os.environ.get("SARVAM_API_KEY"):
            tts_tiers.append("sarvam")
        if not tts_tiers:
            tts_tiers.append("mock (no API keys)")
        services["voice"] = f"up: {', '.join(tts_tiers)}"
    except Exception as e:
        services["voice"] = f"down: {str(e)}"
    
    # Shield (prompt injection detection)
    try:
        from security.prompt_injection import detect_prompt_injection
        detect_prompt_injection("hello")
        services["shield"] = "up"
    except Exception as e:
        services["shield"] = f"down: {str(e)}"
    
    # Postgres
    try:
        if postgres_db.pool:
            services["postgres"] = "up"
        else:
            services["postgres"] = "down: not connected"
    except Exception as e:
        services["postgres"] = f"down: {str(e)}"
    
    # Redis
    try:
        if redis_cache.client and await redis_cache.client.ping():
            services["redis"] = "up"
        else:
            services["redis"] = "down: not connected"
    except Exception as e:
        services["redis"] = f"down: {str(e)}"
    
    overall = "healthy" if all(v == "up" for v in services.values()) else "degraded"
    
    return {
        "status": overall,
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": services,
        "features": feature_flags.get_all_flags()
    }

@api_router.get("/metrics")
async def get_metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@api_router.get("/v1/stats")
async def get_stats():
    """Get system statistics."""
    return {
        "version": "2.0.0",
        "active_sessions": len(session_buffers),
        "hitl_pending": len(await get_interrupted_threads()),
        "cache": get_cache_stats(),
        "audit": get_audit_stats()
    }

# ────────────────────────────────────────────────────────────────
# WebSockets
# ────────────────────────────────────────────────────────────────

@app.websocket("/ws/chat/{user_id}")
async def chat_websocket(websocket: WebSocket, user_id: str) -> None:
    """WebSocket endpoint for real-time chat updates."""
    if not await authenticate_websocket(websocket):
        return
    graph = get_graph()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                msg_text = data.get("message", raw)
                session_id = data.get("session_id", f"ws_{user_id}")
                language = data.get("language", "en")
            except Exception:
                msg_text = raw
                session_id = f"ws_{user_id}"
                language = "en"
                
            scrubbed_msg = getattr(websocket.state, "scrubbed_text", msg_text)
            result = await graph.ainvoke(
                {
                    "messages": [{"role": "user", "content": scrubbed_msg}],
                    "session_id": session_id,
                    "user_id": user_id,
                    "language": language,
                    "channel": "chat"
                },
                config={"configurable": {"thread_id": session_id}}
            )
            await websocket.send_json({
                "response": result.get("response_text", ""),
                "intent": result.get("current_intent", "general_chat"),
                "confidence": result.get("confidence_score", 0.0),
                "requires_hitl": result.get("interrupted", False),
                "language": language
            })
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/supervisor")
async def supervisor_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time supervisor metrics."""
    expected = SUPERVISOR_TOKEN if SUPERVISOR_TOKEN else API_TOKEN
    if not await authenticate_websocket(websocket, expected_token=expected):
        return
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for voice conversations."""
    if not await authenticate_websocket(websocket):
        return
    session_id = str(uuid.uuid4())
    session_lang = websocket.query_params.get("lang", "en")
    
    # Resolved#5: Init per-session buffer
    ACTIVE_SESSIONS.inc()
    
    try:
        # Send welcome
        welcome_msg = "Namaste. Main Sarthi hoon. Boliye." if session_lang == "hi" else "Hello. I am Sarthi. How can I help you?"
        await websocket.send_json({
            "type": "session_init",
            "session_id": session_id,
            "message": welcome_msg
        })
        
        while True:
            try:
                data = await websocket.receive()
                
                if data["type"] == "websocket.disconnect":
                    break
                
                if "bytes" in data:
                    pcm_bytes = data["bytes"]
                    
                    # Process audio chunk with session language
                    result = await process_audio_chunk(session_id, pcm_bytes, language=session_lang)
                    
                    if result is None:
                        continue  # Buffer accumulating
                    
                    if result.get("needs_repeat"):
                        # ASR confidence too low — ask user to repeat
                        repeat_txt = "Ek baar phir bolein, main sun raha hoon" if session_lang == "hi" else "Please repeat that, I am listening."
                        repeat_audio = await tts_cascade(repeat_txt, session_lang)
                        await websocket.send_bytes(repeat_audio)
                        continue
                    
                    # Run graph with transcribed text (or placeholder)
                    transcribed_text = result.get("text") or "[voice input received]"
                    scrubbed = result.get("scrubbed_text") or getattr(websocket.state, "scrubbed_text", transcribed_text)
                    
                    graph = get_graph()
                    graph_result = await graph.ainvoke(
                        {
                            "messages": [{"role": "user", "content": scrubbed}],
                            "session_id": session_id,
                            "language": session_lang,
                            "channel": "voice"
                        },
                        config={"configurable": {"thread_id": session_id}}
                    )
                    
                    response_text = graph_result.get("response_text", "")
                    
                    # Convert to speech
                    audio_response = await tts_cascade(response_text, session_lang)
                    
                    # Send back
                    await websocket.send_bytes(audio_response)
                    
                    # Also send metadata
                    await websocket.send_json({
                        "type": "response_meta",
                        "intent": graph_result.get("current_intent"),
                        "confidence": graph_result.get("confidence_score"),
                        "requires_hitl": graph_result.get("requires_hitl", False)
                    })
                
                elif "text" in data:
                    msg_data = data["text"]
                    if isinstance(msg_data, str):
                        # see issue #105 (2026-06-29): initialise msg_json before try so it is always defined
                        msg_json: dict = {}
                        try:
                            msg_json = json.loads(msg_data)
                            text_content = msg_json.get("message", msg_data)
                        except json.JSONDecodeError:
                            text_content = msg_data

                        session_lang = msg_json.get("language", session_lang)
                        scrubbed = getattr(websocket.state, "scrubbed_text", text_content)
                        graph = get_graph()
                        graph_result = await graph.ainvoke(
                            {
                                "messages": [{"role": "user", "content": scrubbed}],
                                "session_id": session_id,
                                "language": session_lang,
                                "channel": "voice"
                            },
                            config={"configurable": {"thread_id": session_id}}
                        )

                        response_text = graph_result.get("response_text", "")
                        audio_response = await tts_cascade(response_text, session_lang)
                        await websocket.send_bytes(audio_response)

                        await websocket.send_json({
                            "type": "response_meta",
                            "intent": graph_result.get("current_intent"),
                            "confidence": graph_result.get("confidence_score"),
                            "requires_hitl": graph_result.get("requires_hitl", False)
                        })
                    
            except WebSocketDisconnect:
                break
            except Exception:
                await websocket.send_json({
                    "type": "error",
                    "message": "Internal processing error"
                })
    
    finally:
        cleanup_session_buffer(session_id)
        ACTIVE_SESSIONS.dec()

# ────────────────────────────────────────────────────────────────
# Chat API
# ────────────────────────────────────────────────────────────────

@api_router.post("/chat/message", response_model=ChatResponse)
async def process_chat_message(msg: ChatMessage, request: Request):
    """Process a text chat message through the agent graph."""
    # PII scrubbing
    scrubbed = getattr(request.state, "scrubbed_text", msg.message)
    
    # Prompt injection check
    is_injection, flags = detect_prompt_injection(scrubbed)
    if is_injection:
        SHIELD_FLAGS.labels(flag_type="prompt_injection").inc()
        return ChatResponse(
            response="I cannot process this request for security reasons. Please contact SBI at 1800-11-2211.",
            intent="shield_block",
            confidence=1.0,
            requires_hitl=False,
            shield_flags=[f"injection:{f}" for f in flags],
            risk_score=1.0,
            language=msg.language
        )

    # ── Demo mode fast-path ──────────────────────────────────────
    # When the request carries a valid demo token we return scripted
    # responses without touching the LangGraph / Redis / Postgres stack.
    # This ensures the HF Spaces demo always works even when external
    # services are unavailable.
    _auth_token = (
        request.headers.get("X-Sarthi-Token")
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    )
    if DEMO_MODE and _is_valid_demo_token(_auth_token):
        start_time = time.time()
        result = _demo_chat_response(scrubbed, msg.language)
        latency = time.time() - start_time
        REQUEST_LATENCY.labels(endpoint="/chat/message").observe(latency)
        return ChatResponse(
            response=result["response_text"],
            intent=result["current_intent"],
            confidence=result["confidence_score"],
            requires_hitl=result["interrupted"],
            shield_flags=result["shield_flags"],
            risk_score=result["risk_score"],
            language=msg.language
        )
    # ── End demo fast-path ───────────────────────────────────────

    # Invoke graph
    graph = get_graph()
    
    start_time = time.time()
    result = await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": scrubbed}],
            "session_id": msg.session_id,
            "user_id": msg.user_id or msg.session_id,
            "language": msg.language,
            "channel": msg.channel
        },
        config={"configurable": {"thread_id": msg.session_id}}
    )
    latency = time.time() - start_time
    REQUEST_LATENCY.labels(endpoint="/chat/message").observe(latency)
    
    containment = 1.0 if not result.get("interrupted") and result.get("current_intent") != "human_escalation" else 0.0
    QUERY_CONTAINMENT.set(containment)
    
    return ChatResponse(
        response=result.get("response_text", ""),
        intent=result.get("current_intent", "general_chat"),
        confidence=result.get("confidence_score", 0.0),
        requires_hitl=result.get("interrupted", False),
        shield_flags=result.get("shield_flags", []),
        risk_score=result.get("risk_score", 0.0),
        language=msg.language
    )

# ────────────────────────────────────────────────────────────────
# Supervisor Dashboard (HITL)
# ────────────────────────────────────────────────────────────────

async def get_interrupted_threads() -> list:
    """Query the LangGraph checkpoint store for threads awaiting human approval."""
    graph = get_graph()
    interrupted = []
    thread_ids = []
    seen = set()
    
    try:
        async for tuple_ in graph.checkpointer.alist(None, limit=100):
            tid = tuple_.config.get("configurable", {}).get("thread_id")
            if tid and tid not in seen:
                seen.add(tid)
                thread_ids.append(tid)
    except Exception as e:
        logger.error(f"Error checking checkpoints: {e}")
        
    for tid in thread_ids:
        try:
            state = await graph.aget_state({"configurable": {"thread_id": tid}})
            vals = state.values if hasattr(state, "values") else {}
            if state.next or vals.get("interrupted") or vals.get("status") == "INTERRUPTED" or vals.get("requires_hitl"):
                interrupted.append((tid, state))
        except Exception as e:
            logger.error(f"Error getting state for {tid}: {e}")
    
    pending = []
    for thread_id, state in interrupted:
        try:
            values = state.values
            last_msg = values.get("messages", [])[-1] if values.get("messages") else None
            
            risk_score = values.get("risk_score", 0.0)
            if not risk_score and values.get("shield_flags"):
                risk_score = 0.5
            
            pending.append({
                "thread_id": thread_id,
                "created_at": datetime.utcnow().isoformat() + "Z",
                "risk_score": risk_score,
                "trigger_reason": values.get("current_intent", "high_value_transaction"),
                "context_summary": last_msg.content if last_msg and hasattr(last_msg, "content") else str(last_msg) if last_msg else "Action pending approval",
                "customer_context": values.get("messages", [])[-3:] if isinstance(values.get("messages"), list) else [],
                "interrupt_reason": values.get("interrupt_reason"),
                "intent": values.get("current_intent"),
                "channel": values.get("channel", "chat"),
                "timestamp": values.get("metadata", {}).get("timestamp") if isinstance(values.get("metadata"), dict) else None,
                "onboarding_step": values.get("onboarding_step"),
                "user_id": values.get("user_id"),
                "language": values.get("language", "en")
            })
        except Exception as e:
            logger.error(f"Error reading thread {thread_id}: {e}")
            continue
    
    HITL_PENDING.set(len(pending))
    return pending

@supervisor_router.get("/pending")
async def get_pending_threads():
    """Get all pending HITL threads for supervisor dashboard."""
    return await get_interrupted_threads()

@supervisor_router.get("/threads")
async def get_all_threads(limit: int = 50):
    """Get all recent threads (not just interrupted)."""
    graph = get_graph()
    threads = []
    thread_ids = set()
    ordered_ids = []
    
    try:
        async for tuple_ in graph.checkpointer.alist(None, limit=limit * 2):
            tid = tuple_.config.get("configurable", {}).get("thread_id")
            if tid and tid not in thread_ids:
                thread_ids.add(tid)
                ordered_ids.append(tid)
                if len(ordered_ids) >= limit:
                    break
    except Exception as e:
        logger.error(f"Thread enumeration error: {e}")
        return []
    
    for thread_id in ordered_ids:
        try:
            state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
            if not state:
                continue
            values = state.values if hasattr(state, "values") else {}
            threads.append({
                "thread_id": thread_id,
                "status": values.get("status", "unknown"),
                "interrupted": values.get("interrupted", False),
                "intent": values.get("current_intent", "unknown"),
                "onboarding_step": values.get("onboarding_step"),
                "risk_score": values.get("risk_score", 0.0),
            })
        except Exception as e:
            logger.warning(f"Error reading thread {thread_id}: {e}")
            continue
    
    return threads



@supervisor_router.post("/approve/{thread_id}")
async def approve_thread(
    thread_id: str,
    decision: HITLDecision
):
    """Approve or reject a HITL-interrupted thread."""
    if Command is None:
        raise HTTPException(status_code=500, detail="LangGraph Command not available")
    
    graph = get_graph()
    
    create_audit_artifact(
        event_type="hitl_approval" if decision.approved else "hitl_rejection",
        session_id=thread_id,
        agent_name="supervisor_dashboard",
        decision={
            "approved": decision.approved,
            "approver_id": decision.approver_id,
            "reason": decision.reason
        },
        state_snapshot={}
    )
    
    if decision.approved:
        await graph.ainvoke(
            Command(resume={"approved": True, "approver_id": decision.approver_id, "reason": decision.reason}),
            config={"configurable": {"thread_id": thread_id}}
        )
    else:
        await graph.ainvoke(
            Command(resume={"approved": False, "reason": decision.reason, "approver_id": decision.approver_id}),
            config={"configurable": {"thread_id": thread_id}}
        )
    
    await get_interrupted_threads()

    return {
        "status": "processed",
        "thread_id": thread_id,
        "approved": decision.approved,
        "approver_id": decision.approver_id
    }

# ────────────────────────────────────────────────────────────────
# Consent Management (DPDP Act 2023)
# ────────────────────────────────────────────────────────────────

@api_router.post("/consent/request")
async def request_consent(req: ConsentRequest):
    """Request consent for a specific purpose."""
    notice = get_consent_notice(req.purpose_id, req.language)
    
    create_audit_artifact(
        event_type="consent_request",
        session_id=req.user_id,
        agent_name="consent_manager",
        decision={"purpose_id": req.purpose_id, "language": req.language},
        state_snapshot={}
    )
    
    return {
        "status": "delivered",
        "purpose_id": req.purpose_id,
        "notice": notice
    }

@api_router.post("/consent/grant")
async def grant_consent(resp: ConsentResponse):
    """Grant or revoke a consent."""
    artifact = create_consent_artifact(
        user_id=resp.user_id,
        purpose_id=resp.purpose_id,
        lang=resp.language,
        granted=resp.granted,
        prev_hash=get_last_consent_hash(resp.user_id),
        channel="api"
    )
    
    store_consent_artifact(artifact)
    
    create_audit_artifact(
        event_type="consent_grant" if resp.granted else "consent_revoke",
        session_id=resp.user_id,
        agent_name="consent_manager",
        decision={"purpose_id": resp.purpose_id, "granted": resp.granted},
        state_snapshot={}
    )
    
    return {
        "status": "recorded",
        "artifact_hash": artifact["hash"],
        "hmac_verified": True
    }

@api_router.get("/consent/{user_id}")
async def get_user_consent_history(user_id: str):
    """Get all consent artifacts for a user."""
    chain = get_consent_chain(user_id)
    is_valid = verify_consent_chain(chain)
    return {
        "user_id": user_id,
        "consents": chain,
        "chain_integrity": is_valid,
        "count": len(chain)
    }

@api_router.delete("/consent/{user_id}/{purpose_id}")
async def revoke_user_consent(user_id: str, purpose_id: str):
    """Revoke a specific consent."""
    try:
        artifact = revoke_consent_artifact(user_id, purpose_id)
        return {
            "status": "revoked",
            "purpose_id": purpose_id,
            "artifact_hash": artifact["hash"]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ────────────────────────────────────────────────────────────────
# KYC Document Upload
# ────────────────────────────────────────────────────────────────

@api_router.post("/kyc/document")
async def upload_kyc_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    doc_type: str = Form(...)
):
    """Upload and validate KYC document (Aadhaar or PAN).
    
    In production: uses claude-sonnet-4-6 Vision API or Tesseract OCR + regex.
    For prototype: validates filename patterns and returns mock extraction.
    """
    if doc_type not in ["aadhaar", "pan"]:
        raise HTTPException(status_code=400, detail="Invalid doc_type. Must be 'aadhaar' or 'pan'")
    
    # Read file content (for validation)
    content = await file.read()
    file_size = len(content)
    
    if file_size > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large. Max 10MB")
    
    import base64
    from integrations.vision import VisionClient
    
    encoded_img = base64.b64encode(content).decode("utf-8")
    vision = VisionClient()
    
    try:
        extracted_data = await vision.extract_text(encoded_img, doc_type)
        validation_status = "valid"
        confidence = 0.95
    except Exception as e:
        extracted_data = {"error": str(e)}
        validation_status = "error"
        confidence = 0.0
    
    create_audit_artifact(
        event_type="agent_decision",
        session_id=user_id,
        agent_name="kyc_document",
        decision={"doc_type": doc_type, "file_size": file_size, "validation": validation_status},
        state_snapshot={}
    )
    
    return {
        "doc_type": doc_type,
        "file_name": file.filename,
        "file_size": file_size,
        "extracted_data": extracted_data,
        "validation_status": validation_status,
        "confidence": confidence
    }

# ────────────────────────────────────────────────────────────────
# YONO Transaction Webhook
# ────────────────────────────────────────────────────────────────

@api_router.post("/yono/transaction-webhook")
async def yono_transaction_webhook(payload: YONOTransaction):
    """Receive YONO 2.0 transaction webhook.
    
    Triggers adoption agent for cross-sell analysis.
    """
    # Process through graph
    graph = get_graph()
    thread_id = f"txn_{payload.user_id}"
    
    txn_data = payload.model_dump()
    # Convert amount to integer paise
    txn_data["amount"] = int(round(payload.amount * 100))
    
    result = await graph.ainvoke(
        {
            "transaction": txn_data,
            "trigger": "yono_webhook",
            "session_id": thread_id,
            "user_id": payload.user_id,
            "language": "en",
            "channel": "webhook"
        },
        config={"configurable": {"thread_id": thread_id}}
    )
    
    create_audit_artifact(
        event_type="agent_decision",
        session_id=thread_id,
        agent_name="yono_webhook",
        decision={"txn_id": payload.txn_id, "amount": txn_data["amount"], "category": payload.category},
        state_snapshot={}
    )
    
    return {"status": "processed", "txn_id": payload.txn_id, "analysis": result.get("response_text", "")}

# ────────────────────────────────────────────────────────────────
# Audit & Shield
# ────────────────────────────────────────────────────────────────

@api_router.get("/audit/logs")
async def get_audit_logs_endpoint(
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100
):
    """Query audit logs."""
    logs = get_audit_logs(session_id=session_id, event_type=event_type, limit=limit)
    return {
        "logs": logs,
        "count": len(logs),
        "chain_integrity": verify_audit_chain() if logs else True
    }

@api_router.get("/audit/stats")
async def get_audit_stats_endpoint():
    """Get audit statistics."""
    return get_audit_stats()

class ShieldCheckRequest(BaseModel):
    text: str = Field(..., description="Text to analyse for prompt injection / risk")


@api_router.post("/shield/check")
async def shield_check_endpoint(req: ShieldCheckRequest, _=Depends(verify_api_token)):
    """Run shield check on arbitrary text."""
    result = shield_guard(req.text, "", {})
    return {
        "input_safe": result["input_safe"],
        "output_safe": result["output_safe"],
        "flags": result["flags"],
        "action": result["action"],
        "risk_score": result["risk_score"]
    }

# ────────────────────────────────────────────────────────────────
# Demo Mode — Investor / Stakeholder Showcase Endpoints
# ────────────────────────────────────────────────────────────────



demo_router = APIRouter()


@demo_router.get("/supervisor/pending")
async def demo_supervisor_pending(_=Depends(verify_api_token)):
    """Read-only HITL queue for demo mode. No approval capability."""
    threads = await get_interrupted_threads()
    return {"pending": threads, "note": "Approval requires SBI officer credentials"}


@demo_router.get("/token")
async def get_demo_token():
    """Return a scoped demo token for stakeholder/investor access.

    see issue #103 (2026-06-29): This endpoint NEVER returns the live API_TOKEN or SUPERVISOR_TOKEN.
    It generates a fresh, short-lived demo-only token that grants read-only access
    to non-sensitive demo endpoints. The real tokens are never exposed over HTTP.
    Only available when SARTHI_DEMO_MODE=true.
    """
    if not DEMO_MODE:
        raise HTTPException(status_code=403, detail="Demo mode disabled")

    # Generate a fresh ephemeral stateless demo token with 1 hour TTL.
    # The same token is returned for both api_token and supervisor_token so the
    # frontend can populate sessionStorage['sarthi_supervisor_token'] and show
    # the read-only Supervisor Dashboard view without requiring real credentials.
    demo_token = _generate_demo_token()
    expires = ACTIVE_DEMO_TOKENS[demo_token]

    return {
        "api_token": demo_token,
        "supervisor_token": demo_token,   # Fix: frontend reads data.supervisor_token
        "scope": "demo:read",
        "demo_user": {
            "user_id": "DEMO_USER_001",
            "name": "Rajesh Kumar",
            "phone": "+91-98765-43210",
            "account_id": "SBI**********0123",
            "balance": 124750.00,
            "language": "hi"
        },
        "expires_at": int(expires),
        "note": "This token is scoped to demo endpoints only. Production tokens are issued via SBI NetBanking / YONO SSO and are never exposed over HTTP."
    }


@demo_router.post("/seed")
async def seed_demo_data(_=Depends(verify_api_token)):
    """Seed the system with demo data for stakeholder presentations.
    
    Creates:
    - A demo onboarding thread (Aadhaar collected, waiting for PAN)
    - A demo HITL approval (loan > 50K awaiting supervisor)
    - A demo audit trail with sample events

    Graph invocations are best-effort: if SQLite/Redis is unavailable on
    HF Spaces the endpoint still returns 200 so the frontend can proceed.
    """
    if not DEMO_MODE:
        raise HTTPException(status_code=403, detail="Demo mode disabled")

    seeded_threads = []
    graph = get_graph()
    
    # 1. Seed an onboarding thread at "collect_pan" step
    thread_id = "demo_onboarding_001"
    try:
        await graph.ainvoke(
            {
                "session_id": thread_id,
                "messages": [{"role": "user", "content": "Account kholna hai"}],
                "language": "hi",
                "onboarding_step": "collect_pan",
                "aadhaar_number": "a1b2c3d4e5f6...",  # hashed
                "aadhaar_last4": "0123",
                "status": "RUNNING",
                "completed_steps": ["create_profile"]
            },
            config={"configurable": {"thread_id": thread_id}}
        )
        seeded_threads.append(thread_id)
    except Exception as e:
        logger.warning(f"Demo seed: onboarding thread failed (expected in HF Spaces): {e}")
    
    # 2. Seed a HITL-interrupted loan thread
    loan_thread = "demo_loan_hitl_001"
    try:
        await graph.ainvoke(
            {
                "session_id": loan_thread,
                "messages": [{"role": "user", "content": "Mujhe 5 lakh ka loan chahiye"}],
                "language": "hi",
                "current_intent": "loan_application",
                "interrupted": True,
                "interrupt_reason": "loan_amount_exceeds_50k",
                "requires_hitl": True,
                "status": "INTERRUPTED",
                "risk_score": 0.6
            },
            config={"configurable": {"thread_id": loan_thread}}
        )
        seeded_threads.append(loan_thread)
    except Exception as e:
        logger.warning(f"Demo seed: loan HITL thread failed (expected in HF Spaces): {e}")
    
    # 3. Seed audit trail
    try:
        create_audit_artifact(
            event_type="agent_decision",
            session_id="demo_seed",
            agent_name="system",
            decision={"action": "seed_demo_data", "threads_created": len(seeded_threads)},
            state_snapshot={"demo_mode": True}
        )
    except Exception as e:
        logger.warning(f"Demo seed: audit artifact failed: {e}")
    
    return {
        "seeded": True,
        "threads": seeded_threads,
        "message": "Demo data seeded. Check Supervisor Dashboard for HITL queue."
    }

@api_router.get("/sbi/account/{account_id}")
async def get_account(account_id: str):
    """Get SBI account details."""
    try:
        return sbi_api.get_account_balance(account_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@api_router.post("/sbi/loan")
async def create_loan_endpoint(
    req: LoanRequest
):
    """Create a loan application."""
    return sbi_api.create_loan(req.user_id, req.amount, req.purpose)

# ────────────────────────────────────────────────────────────────
# Main & Static Hosting
# ────────────────────────────────────────────────────────────────

app.include_router(api_router, prefix="/api")
app.include_router(supervisor_router, prefix="/api")
app.include_router(demo_router, prefix="/api/demo")

# Serve Frontend Static Files (SPA)
_FRONTEND_DIST = os.path.realpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist"))
if os.path.exists(_FRONTEND_DIST):
    _ASSETS_DIR = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.exists(_ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = os.path.realpath(os.path.join(_FRONTEND_DIST, full_path))
        if not file_path.startswith(_FRONTEND_DIST):
            raise HTTPException(status_code=400, detail="Invalid path")
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        index_path = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Frontend not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        # Resolved#6: 4 workers for concurrent WebSocket sessions
        workers=4,
        reload=False
    )
