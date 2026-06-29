import pytest
import asyncio
import os
import sys
import time

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from voice.vad import session_buffers, cleanup_session_buffer, process_audio_chunk
from utils.cache import cached_llm_call, clear_cache


class TestVAD:
    def test_session_buffer_cleanup(self):
        import numpy as np
        audio = np.zeros(4000, dtype=np.int16).tobytes()
        asyncio.run(process_audio_chunk("sess_1", audio))
        assert "sess_1" in session_buffers
        cleanup_session_buffer("sess_1")
        assert "sess_1" not in session_buffers


class TestCache:
    def test_cached_llm_call(self):
        clear_cache()
        call_count = 0
        def mock_fn():
            nonlocal call_count
            call_count += 1
            return {"result": "test"}
        result1 = cached_llm_call("test_hash", mock_fn, 60)
        result2 = cached_llm_call("test_hash", mock_fn, 60)
        assert result1 == result2
        assert call_count == 1

    def test_cache_ttl_expiry(self):
        def mock_fn():
            return {"time": time.time()}
        result1 = cached_llm_call("ttl_test", mock_fn, 0)
        time.sleep(0.1)
        result2 = cached_llm_call("ttl_test", mock_fn, 0)
        assert result1 != result2
