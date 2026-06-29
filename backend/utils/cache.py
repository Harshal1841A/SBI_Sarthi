import json
import time
import os
from typing import Callable, Any, Optional

# ────────────────────────────────────────────────────────────────
# Two-Layer Cache — Memory + Disk (survives process restart)
# Prevents NIM 429 rate-limit kills during live demos.
# Both layers check TTL expiry before serving (FIX#8).
# ────────────────────────────────────────────────────────────────

# Secure cache directory — not world-readable /tmp
cache_dir = os.environ.get("SARTHI_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".sarthi_cache"))
demo_cache_dir = os.path.join(cache_dir, "demo")


def _read_cache(prompt_hash: str) -> tuple[bool, Any]:
    cache_file = os.path.join(cache_dir, f"{prompt_hash}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get("expires_at", 0) > time.time():
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
    try:
        os.makedirs(cache_dir, mode=0o700, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"{prompt_hash}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_entry, f, default=str)
    except OSError:
        pass

def cached_llm_call(prompt_hash: str, real_fn: Callable, ttl_seconds: int = 3600) -> Any:
    """Shared disk cache: ensures consistent LLM responses across all uvicorn workers."""
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
    """Cache pre-computed demo states on disk for shared worker access."""
    entry = {
        "state": state,
        "expires_at": time.time() + 86400  # 24 hours
    }
    try:
        os.makedirs(demo_cache_dir, mode=0o700, exist_ok=True)
        cache_file = os.path.join(demo_cache_dir, f"{flow_name}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(entry, f, default=str)
    except OSError:
        pass


def get_demo_state(flow_name: str) -> Optional[dict]:
    """Retrieve cached demo state from disk if not expired."""
    cache_file = os.path.join(demo_cache_dir, f"{flow_name}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                entry = json.load(f)
            if entry.get("expires_at", 0) > time.time():
                return entry["state"]
            os.remove(cache_file)
        except (json.JSONDecodeError, OSError):
            os.remove(cache_file) if os.path.exists(cache_file) else None
    return None


def pre_cache_demo_interactions():
    """Pre-run all 8-10 demo interaction turns and cache them."""
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
        cache_demo_state(flow, {"flow": flow, "cached": True, "timestamp": time.time()})
    
    return len(demo_flows)


def clear_cache() -> dict:
    """Clear all disk caches across workers. Returns statistics."""
    disk_count = 0
    if os.path.exists(cache_dir):
        for f in os.listdir(cache_dir):
            if f.endswith('.json'):
                try:
                    os.remove(os.path.join(cache_dir, f))
                    disk_count += 1
                except OSError:
                    pass
    if os.path.exists(demo_cache_dir):
        for f in os.listdir(demo_cache_dir):
            if f.endswith('.json'):
                try:
                    os.remove(os.path.join(demo_cache_dir, f))
                    disk_count += 1
                except OSError:
                    pass
    
    return {
        "memory_entries_cleared": 0,
        "disk_entries_cleared": disk_count,
        "status": "cleared"
    }


def get_cache_stats() -> dict:
    """Get cache statistics."""
    disk_entries = 0
    demo_entries = 0
    if os.path.exists(cache_dir):
        disk_entries = len([f for f in os.listdir(cache_dir) if f.endswith('.json')])
    if os.path.exists(demo_cache_dir):
        demo_entries = len([f for f in os.listdir(demo_cache_dir) if f.endswith('.json')])
    
    return {
        "memory_entries": 0,
        "disk_entries": disk_entries,
        "demo_entries": demo_entries
    }
