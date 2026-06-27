from dotenv import load_dotenv
load_dotenv()
import json
import secrets  # FIX L-2: top-level import, not repeated inside conditionals
try:
    from langgraph.types import Command
except ImportError:
    Command = None
import os
import sys
import uuid
import asyncio
import redis.asyncio as redis
import asyncpg
import time
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

# Local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state import SarthiState
from graph import get_graph
from security.pii_scrubber import scrub_pii, detect_pii
from security.verhoeff import validate_aadhaar, validate_pan, AadhaarValidationError
from security.consent import (
    create_consent_artifact, store_consent_artifact, get_last_consent_hash,
    get_consent_chain, get_user_consents, revoke_consent_artifact, get_consent_notice,
    verify_consent_chain
)
from security.audit import create_audit_artifact, get_audit_logs, get_audit_stats
from security.prompt_injection import shield_guard, detect_prompt_injection
from voice.vad import process_audio_chunk, cleanup_session_buffer, session_buffers
from voice.tts import text_to_speech, tts_cascade
from integrations.sbi_mock import sbi_api
from integrations.yono_mock import yono_api
from integrations.kyc_mock import kyc_api
from utils.cache import get_cache_stats, clear_cache, pre_cache_demo_interactions
from channels.whatsapp import whatsapp_router
from channels.ivr import ivr_router
from middleware.rate_limiter import RateLimitMiddleware
from utils.feature_flags import feature_flags
import structlog
import logging

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

# FIX M-1: Single authoritative token initialisation — removed duplicate block.
# Load from environment; generate ephemeral tokens if missing (dev only).
API_TOKEN        = os.environ.get("SARTHI_API_TOKEN", "")
SUPERVISOR_TOKEN = os.environ.get("SARTHI_SUPERVISOR_TOKEN", "")
HMAC_SECRET      = os.environ.get("SARTHI_HMAC_SECRET", "")

if not API_TOKEN:
    # Also accept frontend env-var name for zero-config demo startup
    API_TOKEN = os.environ.get("VITE_SARTHI_TOKEN", "") or os.environ.get("VITE_SARTHI_API_TOKEN", "")

if not API_TOKEN:
    API_TOKEN = secrets.token_hex(32)
    print(f"WARNING: SARTHI_API_TOKEN not set. Generated temporary token: {API_TOKEN}")

if not SUPERVISOR_TOKEN:
    SUPERVISOR_TOKEN = secrets.token_hex(32)
    print(f"WARNING: SARTHI_SUPERVISOR_TOKEN not set. Generated temporary token: {SUPERVISOR_TOKEN}")

DEMO_MODE = os.environ.get("SARTHI_DEMO_MODE", "true").lower() == "true"
security = HTTPBearer(auto_error=False)

ACTIVE_DEMO_TOKENS: set[str] = set()

def verify_api_token(request: Request, creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> None:
    """Validate Bearer token for standard API endpoints."""
    if DEMO_MODE:
        return
    token = request.headers.get("X-Sarthi-Token") or (creds.credentials if creds else None)
    if not token or (token != API_TOKEN and token not in ACTIVE_DEMO_TOKENS):
        raise HTTPException(status_code=403, detail="Unauthorized")

def verify_supervisor_token(request: Request, creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> None:
    """Validate Bearer token for supervisor-only endpoints."""
    if DEMO_MODE:
        return
    token = request.headers.get("X-Sarthi-Supervisor-Token") or (creds.credentials if creds else None)
    if not token or (token != SUPERVISOR_TOKEN and token not in ACTIVE_DEMO_TOKENS):
        raise HTTPException(status_code=403, detail="Supervisor access required")

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
    user_id: Optional[str] = "demo_user"

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
    # Startup
    print("Sarthi API starting up...")
    
    # Initialize Databases
    try:
        await postgres_db.connect()
        await redis_cache.connect()
    except Exception as e:
        print(f"! Database connection failed (running in degraded mode): {e}")
        
    pre_cache_demo_interactions()
    
    # Verify graph compilation
    try:
        graph = get_graph()
        print(f"[OK] LangGraph compiled successfully: {type(graph)}")
    except Exception as e:
        print(f"[ERROR] Graph compilation failed: {e}")
        raise
    
    yield
    
    # Shutdown
    print("Sarthi API shutting down...")
    
    await postgres_db.disconnect()
    await redis_cache.disconnect()
    
    cleanup_stats = clear_cache()
    print(f"Cache cleanup: {cleanup_stats}")

# ────────────────────────────────────────────────────────────────
# FastAPI App
# ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Sarthi API",
    description="Sarthi - Agentic AI Banking Platform for SBI",
    version="2.0.0",
    lifespan=lifespan
)

# FIX M-2: CORS origins are env-gated.
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
_ALLOWED_ORIGINS = (
    _PRODUCTION_ORIGINS + _DEV_ORIGINS
    if os.environ.get("SARTHI_ENV", "development") != "production"
    else _PRODUCTION_ORIGINS
)

_is_demo = DEMO_MODE

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _is_demo else _ALLOWED_ORIGINS,
    allow_credentials=not _is_demo,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"] if _is_demo else ["Authorization", "Content-Type", "X-Request-ID", "X-Sarthi-Token", "X-Sarthi-Supervisor-Token"],
)

@app.middleware("http")
async def strip_api_prefix(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        request.scope["path"] = request.url.path[4:]
    return await call_next(request)

# Rate Limiting Middleware
app.add_middleware(RateLimitMiddleware, rate_limit=100, window=60)

# Include Channel Routers
app.include_router(whatsapp_router, prefix="/whatsapp", tags=["channels"])
app.include_router(ivr_router, prefix="/ivr", tags=["channels"])

api_router = APIRouter(dependencies=[Depends(verify_api_token)])

# ────────────────────────────────────────────────────────────────
# Health & Metrics
# ────────────────────────────────────────────────────────────────

@app.get("/health")
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
        "hitl_pending": len(get_interrupted_threads()),
        "cache": get_cache_stats(),
        "audit": get_audit_stats()
    }

# ────────────────────────────────────────────────────────────────
# Voice WebSocket
# ────────────────────────────────────────────────────────────────

@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    """WebSocket endpoint for voice conversations.
    
    Protocol:
    1. Client connects with ?token=<API_TOKEN>
    2. Server accepts, assigns session_id
    3. Client sends Int16 PCM chunks (160 samples = 10ms at 16kHz)
    4. Server accumulates, runs VAD, sends back audio when ready
    """
    # FIX#7: WebSocket auth via query param
    token = websocket.query_params.get("token")
    if not token or token != API_TOKEN:
        await websocket.close(code=4003, reason="Unauthorized")
        return
    
    await websocket.accept()
    session_id = str(uuid.uuid4())
    
    # FIX#5: Init per-session buffer
    ACTIVE_SESSIONS.inc()
    
    try:
        # Send welcome
        await websocket.send_json({
            "type": "session_init",
            "session_id": session_id,
            "message": "Namaste. Main Sarthi hoon. Boliye."
        })
        
        while True:
            try:
                data = await websocket.receive()
                
                if data["type"] == "websocket.disconnect":
                    break
                
                if "bytes" in data:
                    pcm_bytes = data["bytes"]
                    
                    # Process audio chunk
                    result = await process_audio_chunk(session_id, pcm_bytes)
                    
                    if result is None:
                        continue  # Buffer accumulating
                    
                    if result.get("needs_repeat"):
                        # ASR confidence too low — ask user to repeat
                        repeat_audio = await tts_cascade(
                            "Ek baar phir bolein, main sun raha hoon", "hi"
                        )
                        await websocket.send_bytes(repeat_audio)
                        continue
                    
                    # Run graph with transcribed text (or placeholder)
                    transcribed_text = result.get("text") or "[voice input received]"
                    scrubbed = scrub_pii(transcribed_text)
                    
                    graph = get_graph()
                    graph_result = await asyncio.to_thread(graph.invoke,
                        {
                            "messages": [{"role": "user", "content": scrubbed}],
                            "session_id": session_id,
                            "language": "hi",
                            "channel": "voice"
                        },
                        config={"configurable": {"thread_id": session_id}}
                    )
                    
                    response_text = graph_result.get("response_text", "")
                    
                    # Convert to speech
                    audio_response = await tts_cascade(response_text, "hi")
                    
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
                        # FIX H-3: initialise msg_json before try so it is always defined
                        msg_json: dict = {}
                        try:
                            msg_json = json.loads(msg_data)
                            text_content = msg_json.get("message", msg_data)
                        except json.JSONDecodeError:
                            text_content = msg_data

                        lang = msg_json.get("language", "hi")
                        scrubbed = scrub_pii(text_content)
                        graph = get_graph()
                        graph_result = await asyncio.to_thread(graph.invoke,
                            {
                                "messages": [{"role": "user", "content": scrubbed}],
                                "session_id": session_id,
                                "language": lang,
                                "channel": "voice"
                            },
                            config={"configurable": {"thread_id": session_id}}
                        )

                        response_text = graph_result.get("response_text", "")
                        audio_response = await tts_cascade(response_text, lang)
                        await websocket.send_bytes(audio_response)

                        await websocket.send_json({
                            "type": "response_meta",
                            "intent": graph_result.get("current_intent"),
                            "confidence": graph_result.get("confidence_score"),
                            "requires_hitl": graph_result.get("requires_hitl", False)
                        })
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
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
async def process_chat_message(msg: ChatMessage):
    """Process a text chat message through the agent graph."""
    # PII scrubbing
    scrubbed = scrub_pii(msg.message)
    
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
    
    # Invoke graph
    graph = get_graph()
    
    start_time = time.time()
    result = await asyncio.to_thread(graph.invoke,
        {
            "messages": [{"role": "user", "content": scrubbed}],
            "session_id": msg.session_id,
            "user_id": msg.user_id,
            "language": msg.language,
            "channel": msg.channel
        },
        config={"configurable": {"thread_id": msg.session_id}}
    )
    latency = time.time() - start_time
    REQUEST_LATENCY.labels(endpoint="/chat/message").observe(latency)
    
    # Update metrics
    if result.get("interrupted"):
        HITL_PENDING.inc()
    
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

# FIX#5: replaces undefined get_all_thread_ids() with direct SQLite query
def get_interrupted_threads() -> list:
    """Query the LangGraph checkpoint store for threads awaiting human approval.
    
    Uses SqliteSaver tables directly for thread enumeration, then validates
    each thread via graph.get_state() to properly deserialize checkpoint data.
    """
    db_path = os.environ.get("SQLITE_PATH", "checkpoints.db")
    graph = get_graph()
    interrupted = []
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Get distinct thread IDs from the checkpoints table
        cursor = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id DESC LIMIT 100"
        )
        thread_ids = [row["thread_id"] for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        print(f"Thread enumeration error: {e}")
        return []
    
    for thread_id in thread_ids:
        try:
            state = graph.get_state({"configurable": {"thread_id": thread_id}})
            if not state:
                continue
            values = state.values if hasattr(state, "values") else {}
            if isinstance(values, dict) and (values.get("interrupted") or values.get("requires_hitl")):
                interrupted.append(thread_id)
        except Exception as e:
            print(f"Error reading thread {thread_id}: {e}")
            continue
    
    return list(set(interrupted))

@app.get("/supervisor/pending")
async def get_pending_threads(_=Depends(verify_supervisor_token)):
    """Get all pending HITL threads for supervisor dashboard."""
    # FIX C-4: wrap blocking SQLite scan in a thread so the event loop is never blocked
    thread_ids = await asyncio.to_thread(get_interrupted_threads)
    pending = []
    graph = get_graph()
    
    for thread_id in thread_ids:
        try:
            state = graph.get_state({"configurable": {"thread_id": thread_id}})
            if not state:
                continue
                
            values = state.values if hasattr(state, 'values') else {}
            
            # Calculate risk score if not present
            risk_score = values.get("risk_score", 0.0)
            if not risk_score and values.get("shield_flags"):
                risk_score = 0.5
            
            pending.append({
                "thread_id": thread_id,
                "customer_context": values.get("messages", [])[-3:] if isinstance(values.get("messages"), list) else [],
                "interrupt_reason": values.get("interrupt_reason"),
                "risk_score": risk_score,
                "intent": values.get("current_intent"),
                "language": values.get("language", "en"),
                "channel": values.get("channel", "chat"),
                "timestamp": values.get("metadata", {}).get("timestamp") if isinstance(values.get("metadata"), dict) else None,
                "onboarding_step": values.get("onboarding_step"),
                "user_id": values.get("user_id")
            })
        except Exception as e:
            print(f"Error reading thread {thread_id}: {e}")
            continue
    
    HITL_PENDING.set(len(pending))
    return pending

@app.post("/supervisor/approve/{thread_id}")
async def approve_thread(
    thread_id: str,
    decision: HITLDecision,
    _=Depends(verify_supervisor_token)
):
    """Approve or reject a HITL-interrupted thread.
    
    FIX#2: Command is imported from langgraph.types
    """
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
    
    pending_before = set(await asyncio.to_thread(get_interrupted_threads))
    was_pending = thread_id in pending_before

    if decision.approved:
        await asyncio.to_thread(graph.invoke,
            Command(resume={"approved": True, "approver_id": decision.approver_id, "reason": decision.reason}),
            config={"configurable": {"thread_id": thread_id}}
        )
    else:
        await asyncio.to_thread(graph.invoke,
            Command(resume={"approved": False, "reason": decision.reason, "approver_id": decision.approver_id}),
            config={"configurable": {"thread_id": thread_id}}
        )
    
    if was_pending:
        HITL_PENDING.dec()

    return {
        "status": "processed",
        "thread_id": thread_id,
        "approved": decision.approved,
        "approver_id": decision.approver_id
    }

@app.get("/supervisor/threads")
async def get_all_threads(
    limit: int = 50,
    _=Depends(verify_supervisor_token)
):
    """Get all recent threads (not just interrupted)."""
    db_path = os.environ.get("SQLITE_PATH", "checkpoints.db")
    graph = get_graph()
    threads = []
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id DESC LIMIT ?",
            (limit,)
        )
        thread_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
    except Exception as e:
        print(f"Thread enumeration error: {e}")
        return []
    
    for thread_id in thread_ids:
        try:
            state = graph.get_state({"configurable": {"thread_id": thread_id}})
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
            print(f"Error reading thread {thread_id}: {e}")
            continue
    
    return threads

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

@app.post("/yono/transaction-webhook")
async def yono_transaction_webhook(payload: YONOTransaction, _=Depends(verify_api_token)):
    """Receive YONO 2.0 transaction webhook.
    
    Triggers adoption agent for cross-sell analysis.
    """
    # Process through graph
    graph = get_graph()
    thread_id = f"txn_{payload.user_id}"
    
    txn_data = payload.dict()
    # Convert amount to integer paise
    txn_data["amount"] = int(round(payload.amount * 100))
    
    result = await asyncio.to_thread(graph.invoke,
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

@app.get("/audit/logs")
async def get_audit_logs_endpoint(
    session_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 100,
    _=Depends(verify_api_token)
):
    """Query audit logs."""
    logs = get_audit_logs(session_id=session_id, event_type=event_type, limit=limit)
    return {
        "logs": logs,
        "count": len(logs),
        "chain_integrity": True
    }

@app.get("/audit/stats")
async def get_audit_stats_endpoint(_=Depends(verify_api_token)):
    """Get audit statistics."""
    return get_audit_stats()

class ShieldCheckRequest(BaseModel):
    text: str = Field(..., description="Text to analyse for prompt injection / risk")


@app.post("/shield/check")
async def shield_check_endpoint(req: ShieldCheckRequest, _=Depends(verify_api_token)):
    """Run shield check on arbitrary text.

    FIX H-8: text is now in the JSON request body (not a query param).
    Query-param approach sent sensitive text in URLs, which are logged by
    every proxy, CDN, and load balancer in plaintext.
    """
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



@app.get("/demo/supervisor/pending")
async def demo_supervisor_pending(_=Depends(verify_api_token)):
    """Read-only HITL queue for demo mode. No approval capability."""
    threads = await asyncio.to_thread(get_interrupted_threads)
    return {"pending": threads, "note": "Approval requires SBI officer credentials"}


@app.get("/demo/token")
async def get_demo_token():
    """Return a scoped demo token for stakeholder/investor access.

    FIX C-2: This endpoint NEVER returns the live API_TOKEN or SUPERVISOR_TOKEN.
    It generates a fresh, short-lived demo-only token that grants read-only access
    to non-sensitive demo endpoints. The real tokens are never exposed over HTTP.
    Only available when SARTHI_DEMO_MODE=true.
    """
    if not DEMO_MODE:
        raise HTTPException(status_code=403, detail="Demo mode disabled")

    # Generate a fresh ephemeral demo token — NOT the production API_TOKEN
    demo_token = secrets.token_hex(32)
    ACTIVE_DEMO_TOKENS.add(demo_token)

    return {
        "api_token": demo_token,
        "supervisor_token": demo_token,  # enable demo users to test HITL approval dashboard
        "demo_user": {
            "user_id": "DEMO_USER_001",
            "name": "Rajesh Kumar",
            "phone": "+91-98765-43210",
            "account_id": "SBIXXXXXXXXXX0123",
            "balance": 124750.00,
            "language": "hi"
        },
        "expires_at": None,
        "note": "This token is scoped to demo endpoints only. Production tokens are issued via SBI NetBanking / YONO SSO and are never exposed over HTTP."
    }


@app.post("/demo/seed")
async def seed_demo_data(_=Depends(verify_api_token)):
    """Seed the system with demo data for stakeholder presentations.
    
    Creates:
    - A demo onboarding thread (Aadhaar collected, waiting for PAN)
    - A demo HITL approval (loan > 50K awaiting supervisor)
    - A demo audit trail with sample events
    """
    graph = get_graph()
    
    # 1. Seed an onboarding thread at "collect_pan" step
    thread_id = "demo_onboarding_001"
    await asyncio.to_thread(graph.invoke,
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
    
    # 2. Seed a HITL-interrupted loan thread
    loan_thread = "demo_loan_hitl_001"
    await asyncio.to_thread(graph.invoke,
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
    
    # 3. Seed audit trail
    create_audit_artifact(
        event_type="agent_decision",
        session_id="demo_seed",
        agent_name="system",
        decision={"action": "seed_demo_data", "threads_created": 2},
        state_snapshot={"demo_mode": True}
    )
    
    return {
        "seeded": True,
        "threads": [thread_id, loan_thread],
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

app.include_router(api_router)
app.include_router(api_router, prefix="/api")

# Serve Frontend Static Files (SPA)
_FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "dist")
if os.path.exists(_FRONTEND_DIST):
    _ASSETS_DIR = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.exists(_ASSETS_DIR):
        app.mount("/assets", StaticFiles(directory=_ASSETS_DIR), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file_path = os.path.join(_FRONTEND_DIST, full_path)
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
        # FIX#6: 4 workers for concurrent WebSocket sessions
        workers=4,
        reload=False
    )
