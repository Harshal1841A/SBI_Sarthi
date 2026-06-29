from typing import Any
from state import SarthiState
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

import asyncio
import os
import threading
import aiosqlite
try:
    import psycopg_pool
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:
    AsyncPostgresSaver = None
    psycopg_pool = None

# Import all agent nodes
from agents.supervisor import supervisor_node, route_intent
from agents.acquisition import acquisition_agent, check_onboarding_status
from agents.adoption import adoption_agent
from agents.engagement import engagement_agent
from agents.assist import assist_agent
from agents.shield import shield_agent
from agents.compensation import compensation_node
from agents.hitl import hitl_pause_node, hitl_resume_node, wait_human_approval

# ────────────────────────────────────────────────────────────────
# LangGraph StateGraph Builder — Sarthi Multi-Agent Orchestration
# Deterministic routing, HITL breakpoints, Saga Pattern support.
# ────────────────────────────────────────────────────────────────

def build_graph() -> Any:
    """Build and compile the Sarthi LangGraph StateGraph with Postgres or SQLite checkpointing."""
    builder = StateGraph(SarthiState)

    def _wrap(node_fn: Any, name: str) -> Any:
        """Wrap an agent node to catch exceptions and return safe state asynchronously."""
        async def _async_wrapper(state: SarthiState) -> dict:
            try:
                if asyncio.iscoroutinefunction(node_fn):
                    return await node_fn(state)
                return node_fn(state)
            except Exception as e:
                from security.audit import create_audit_artifact  # pyrefly: ignore [missing-import]
                try:
                    create_audit_artifact(
                        event_type="agent_error",
                        session_id=state.get("session_id", "unknown"),
                        agent_name=name,
                        decision={"error": str(e)},
                        state_snapshot={"status": state.get("status")}
                    )
                except Exception:
                    pass
                return {
                    "response_text": "Sorry, I encountered a technical issue. Please try again or contact SBI at 1800-11-2211.",
                    "status": "IDLE",
                    "shield_flags": [f"agent_error:{name}"]
                }
        return _async_wrapper

    # Add all nodes with error handling
    builder.add_node("supervisor", _wrap(supervisor_node, "supervisor"))
    builder.add_node("acquisition", _wrap(acquisition_agent, "acquisition"))
    builder.add_node("adoption", _wrap(adoption_agent, "adoption"))
    builder.add_node("engagement", _wrap(engagement_agent, "engagement"))
    builder.add_node("assist", _wrap(assist_agent, "assist"))
    builder.add_node("shield", _wrap(shield_agent, "shield"))
    builder.add_node("compensation", _wrap(compensation_node, "compensation"))
    builder.add_node("hitl_pause", _wrap(hitl_pause_node, "hitl_pause"))
    builder.add_node("hitl_resume", _wrap(hitl_resume_node, "hitl_resume"))

    # Set entry point
    builder.set_entry_point("supervisor")

    # ── Supervisor routing edges ────────────────────────────────
    builder.add_conditional_edges(
        "supervisor",
        route_intent,
        {
            "acquisition": "acquisition",
            "adoption": "adoption",
            "engagement": "engagement",
            "assist": "assist",
            "shield": "shield",
            "hitl_pause": "hitl_pause"
        }
    )

    # ── Acquisition edges ─────────────────────────────────────────
    builder.add_conditional_edges(
        "acquisition",
        check_onboarding_status,
        {
            "complete": "adoption",
            "failed": "compensation",
            "interrupted": "hitl_pause",
            "running": "shield"
        }
    )

    # ── Adoption / Engagement / Assist edges ────────────────────
    builder.add_edge("adoption", "shield")
    builder.add_edge("engagement", "shield")
    builder.add_edge("assist", "shield")

    # ── HITL edges ──────────────────────────────────────────────
    # see issue #101 (2026-06-29): hitl_pause uses LangGraph interrupt — the conditional edge
    # wait_human_approval() is only called AFTER Command(resume=...) is sent.
    # Before that the graph is truly halted at the checkpoint.
    builder.add_conditional_edges(
        "hitl_pause",
        wait_human_approval,
        {
            "approved": "hitl_resume",
            "rejected": "compensation",
            "pending": END  # Graph halts — waiting for human
        }
    )

    # hitl_resume → route back to appropriate agent
    def hitl_resume_router(state: SarthiState) -> str:
        """After HITL resume, route back to the interrupted flow."""
        interrupt_reason = state.get("interrupt_reason", "")
        if "v_kyc" in interrupt_reason:
            return "acquisition"
        elif "loan" in interrupt_reason or "fund" in interrupt_reason:
            return "acquisition"
        elif "fraud" in interrupt_reason or "block" in interrupt_reason:
            return "assist"
        elif "high_risk" in interrupt_reason or "shield" in interrupt_reason:
            return "shield"
        else:
            return "assist"

    builder.add_conditional_edges(
        "hitl_resume",
        hitl_resume_router,
        {
            "acquisition": "acquisition",
            "assist": "assist",
            "shield": "shield"
            # NOTE: adoption/engagement removed — hitl_resume_router never returns them (see issue #102 2026-06-29)
        }
    )

    # ── Shield / Compensation edges ─────────────────────────────
    builder.add_edge("shield", END)
    builder.add_edge("compensation", END)

    db_url = os.environ.get("DATABASE_URL")
    env = os.environ.get("SARTHI_ENV", "development")

    if db_url and AsyncPostgresSaver is not None and psycopg_pool is not None:
        pool = psycopg_pool.AsyncConnectionPool(conninfo=db_url, open=False)
        memory = AsyncPostgresSaver(pool)
    else:
        if env == "production":
            raise RuntimeError("Refusing to start with SQLite checkpointing when SARTHI_ENV == 'production'. DATABASE_URL must be set.")
        db_path = os.environ.get("SQLITE_PATH", "checkpoints.db")
        if os.path.exists(db_path) and env != "development":
            raise RuntimeError(f"Refusing to reuse on-disk SQLite at {db_path} outside development.")
        conn = aiosqlite.connect(db_path)
        memory = AsyncSqliteSaver(conn)

    graph = builder.compile(checkpointer=memory)
    return graph


_graph_instance: Any = None
_graph_lock = threading.Lock()


def get_graph() -> Any:
    """Get or create the compiled graph instance (thread-safe singleton)."""
    global _graph_instance
    if _graph_instance is None:
        with _graph_lock:
            if _graph_instance is None:
                _graph_instance = build_graph()
    return _graph_instance
