from typing import Any
from state import SarthiState
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

import asyncio
import os
import threading
import sqlite3

# Import all agent nodes
from agents.supervisor import supervisor_node, route_intent
from agents.acquisition import acquisition_agent, check_onboarding_status
from agents.adoption import adoption_agent
from agents.engagement import engagement_agent
from agents.assist import assist_agent
from agents.shield import shield_agent
from agents.compensation import compensation_node, check_onboarding_status_for_compensation
from agents.hitl import hitl_pause_node, hitl_resume_node, wait_human_approval

# ────────────────────────────────────────────────────────────────
# LangGraph StateGraph Builder — Sarthi Multi-Agent Orchestration
# Deterministic routing, HITL breakpoints, Saga Pattern support.
# ────────────────────────────────────────────────────────────────

def build_graph():
    """Build and compile the Sarthi LangGraph StateGraph.

    Returns:
        Compiled graph with SqliteSaver checkpointing.
    """
    builder = StateGraph(SarthiState)

    # FIX C-3: Never use asyncio.run() inside a wrapper called from asyncio.to_thread()
    # — that creates a NEW event loop inside a thread that already has one, causing deadlock.
    # Instead: run async nodes synchronously via a dedicated per-call event loop in the thread.
    def _wrap(node_fn, name: str):
        """Wrap an agent node to catch exceptions and return safe state.
        
        Sync nodes are called directly.
        Async nodes are run via asyncio.run() which is safe here because graph.invoke()
        is always called from asyncio.to_thread() — the thread has NO running event loop.
        """
        if asyncio.iscoroutinefunction(node_fn):
            def _sync_wrapper(state: SarthiState) -> dict:
                try:
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    return loop.run_until_complete(node_fn(state))
                except Exception as e:
                    from security.audit import create_audit_artifact
                    try:
                        create_audit_artifact(
                            event_type="agent_error",
                            session_id=state.get("session_id", "unknown"),
                            agent_name=name,
                            decision={"error": str(e)},
                            state_snapshot={"status": state.get("status")}
                        )
                    except Exception:
                        pass  # Audit failure must never mask the original error
                    return {
                        "response_text": "Sorry, I encountered a technical issue. Please try again or contact SBI at 1800-11-2211.",
                        "status": "IDLE",
                        "shield_flags": [f"agent_error:{name}"]
                    }
            return _sync_wrapper
        else:
            def _sync_wrapper(state: SarthiState) -> dict:
                try:
                    return node_fn(state)
                except Exception as e:
                    from security.audit import create_audit_artifact
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
            return _sync_wrapper

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
            "running": "acquisition"
        }
    )

    # ── Adoption / Engagement / Assist edges ────────────────────
    builder.add_edge("adoption", "shield")
    builder.add_edge("engagement", "shield")
    builder.add_edge("assist", "shield")

    # ── HITL edges ──────────────────────────────────────────────
    # FIX H-5: hitl_pause uses LangGraph interrupt — the conditional edge
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
            "adoption": "adoption",
            "engagement": "engagement",
            "assist": "assist",
            "shield": "shield"
        }
    )

    # ── Shield / Compensation edges ─────────────────────────────
    builder.add_edge("shield", END)
    builder.add_edge("compensation", END)

    # FIX H-2: Use check_same_thread=False with a high timeout and WAL mode.
    # This allows concurrent threads to use the connection without locking errors.
    db_path = os.environ.get("SQLITE_PATH", "checkpoints.db")
    conn = sqlite3.connect(db_path, check_same_thread=False, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    memory = SqliteSaver(conn)
    graph = builder.compile(checkpointer=memory)

    return graph


# FIX H-1: Thread-safe singleton with explicit lock.
# Prevents race condition when multiple threads in the same uvicorn worker cold-start simultaneously.
_graph_instance = None
_graph_lock = threading.Lock()


def get_graph():
    """Get or create the compiled graph instance (thread-safe singleton)."""
    global _graph_instance
    if _graph_instance is None:
        with _graph_lock:
            # Double-checked locking: re-check inside lock
            if _graph_instance is None:
                _graph_instance = build_graph()
    return _graph_instance
