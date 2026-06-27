import json
import time
import os
import hashlib
from typing import Callable, Any, Optional

# ────────────────────────────────────────────────────────────────
# Two-Layer Cache — Memory + Disk (survives process restart)
# Prevents NIM 429 rate-limit kills during live demos.
# Both layers check TTL expiry before serving (FIX#8).
# ────────────────────────────────────────────────────────────────

LLM_RESPONSE_CACHE: dict = {}
DEMO_CACHE: dict = {}

# Secure cache directory — not world-readable /tmp
cache_dir = os.environ.get("SARTHI_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".sarthi_cache"))


def _read_cache(prompt_hash: str) -> tuple[bool, Any]:
    if prompt_hash in LLM_RESPONSE_CACHE:
        entry = LLM_RESPONSE_CACHE[prompt_hash]
        if entry.get("expires_at", 0) > time.time():
            return True, entry["result"]
        del LLM_RESPONSE_CACHE[prompt_hash]
    
    cache_file = os.path.join(cache_dir, f"{prompt_hash}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get("expires_at", 0) > time.time():
                LLM_RESPONSE_CACHE[prompt_hash] = data
                return True, data["result"]
            os.remove(cache_file)
        except (json.JSONDecodeError, OSError):
            os.remove(cache_file) if os.path.exists(cache_file) else None
    return False, None

def _write_cache(prompt_hash: str, result: Any, ttl_seconds: int) -> None:
    cache_entry = {
        "result": result,
        "expires_at": time.time() + ttl_seconds,
        "created_at": time.time()
    }
    LLM_RESPONSE_CACHE[prompt_hash] = cache_entry
    try:
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{prompt_hash}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_entry, f, default=str)
    except OSError:
        pass

def cached_llm_call(prompt_hash: str, real_fn: Callable, ttl_seconds: int = 3600) -> Any:
    """Two-layer cache: memory (fastest) -> disk (survives restart) -> live call."""
    hit, val = _read_cache(prompt_hash)
    if hit: return val
    
    result = real_fn()
    _write_cache(prompt_hash, result, ttl_seconds)
    return result

async def async_cached_llm_call(prompt_hash: str, real_fn: Callable, ttl_seconds: int = 3600) -> Any:
    """Async version of cached_llm_call."""
    hit, val = _read_cache(prompt_hash)
    if hit: return val
    
    result = await real_fn()
    _write_cache(prompt_hash, result, ttl_seconds)
    return result

def cache_demo_state(flow_name: str, state: dict) -> None:
    """Cache pre-computed demo states for live presentations."""
    DEMO_CACHE[flow_name] = {
        "state": state,
        "expires_at": time.time() + 86400  # 24 hours
    }


def get_demo_state(flow_name: str) -> Optional[dict]:
    """Retrieve cached demo state if not expired."""
    entry = DEMO_CACHE.get(flow_name)
    if entry and entry.get("expires_at", 0) > time.time():
        return entry["state"]
    return None


def pre_cache_demo_interactions():
    """Pre-run all 8-10 demo interaction turns and cache them.
    This prevents NIM rate-limit kills during live demos.
    """
    demo_flows = [
        "account_open_marathi",
        "balance_inquiry_hindi",
        "loan_application_marathi",
        "kyc_upload_error",
        "cross_sell_education_loan",
        "fraud_report_english",
        "human_escalation_request",
        "consent_grant_kyc",
        "v_kyc_handoff",
        "saga_rollback_demo"
    ]
    
    for flow in demo_flows:
        # In production: execute_demo_flow(flow) and cache
        # For prototype: placeholder
        cache_demo_state(flow, {"flow": flow, "cached": True, "timestamp": time.time()})
    
    return len(demo_flows)


def clear_cache() -> dict:
    """Clear all caches. Returns statistics."""
    mem_count = len(LLM_RESPONSE_CACHE)
    disk_count = 0
    
    LLM_RESPONSE_CACHE.clear()
    DEMO_CACHE.clear()
    
    cache_dir = os.environ.get("SARTHI_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".sarthi_cache"))
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            if f.endswith('.json'):
                try:
                    os.remove(os.path.join(cache_dir, f))
                    disk_count += 1
                except OSError:
                    pass
    
    return {
        "memory_entries_cleared": mem_count,
        "disk_entries_cleared": disk_count,
        "status": "cleared"
    }


def get_cache_stats() -> dict:
    """Get cache statistics."""
    cache_dir = os.environ.get("SARTHI_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".sarthi_cache"))
    disk_entries = 0
    if os.path.exists(cache_dir):
        disk_entries = len([f for f in os.listdir(cache_dir) if f.endswith('.json')])
    
    return {
        "memory_entries": len(LLM_RESPONSE_CACHE),
        "disk_entries": disk_entries,
        "demo_entries": len(DEMO_CACHE)
    }
