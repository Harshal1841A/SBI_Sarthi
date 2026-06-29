import sys
import os
import json
import pytest
from unittest.mock import AsyncMock, patch

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from fastapi.testclient import TestClient
import main  # pyrefly: ignore [missing-import]
from main import app  # pyrefly: ignore [missing-import]
from security.audit import get_audit_logs, create_audit_artifact  # pyrefly: ignore [missing-import]
from voice import vad  # pyrefly: ignore [missing-import]


class MockGraph:
    def __init__(self):
        self.invoked_payloads = []

    async def ainvoke(self, payload, config=None):
        self.invoked_payloads.append(payload)
        return {
            "response_text": "Safe response",
            "current_intent": "general",
            "confidence_score": 0.95,
            "requires_hitl": False
        }


@pytest.fixture
def mock_graph():
    graph = MockGraph()
    with patch("main.get_graph", return_value=graph):
        yield graph


def test_websocket_chat_pii_scrubbing(mock_graph):
    """Test that raw PII sent over /ws/chat/{user_id} is scrubbed before reaching LLM payloads or audit logs."""
    client = TestClient(app)
    token = main.API_TOKEN or "test_token"
    main.API_TOKEN = token

    with client.websocket_connect("/ws/chat/test_user") as ws:
        ws.send_json({"type": "auth", "token": token})
        ws.send_text(json.dumps({"message": "My PAN is ABCDE1234F and Aadhaar is 234123412000"}))
        response = ws.receive_json()
        assert response["response"] == "Safe response"

    assert len(mock_graph.invoked_payloads) > 0
    content = mock_graph.invoked_payloads[0]["messages"][0]["content"]
    assert "ABCDE1234F" not in content
    assert "234123412000" not in content
    assert "[PAN]" in content
    assert "[AADHAAR]" in content

    create_audit_artifact(
        event_type="agent_decision",
        session_id="ws_test_user",
        agent_name="test_agent",
        decision={"status": "ok"},
        state_snapshot={"messages": [{"role": "user", "content": content}]}
    )
    logs = get_audit_logs(session_id="ws_test_user")
    for log in logs:
        log_str = json.dumps(log)
        assert "ABCDE1234F" not in log_str
        assert "234123412000" not in log_str


def test_websocket_voice_text_pii_scrubbing(mock_graph):
    """Test that text messages sent over /ws/voice are scrubbed before reaching LLM payloads."""
    client = TestClient(app)
    token = main.API_TOKEN or "test_token"
    main.API_TOKEN = token

    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "auth", "token": token})
        _ = ws.receive_json()  # consume session_init message
        ws.send_json({"text": json.dumps({"message": "My phone is 9876543210"})})
        _ = ws.receive_bytes()  # audio response
        meta = ws.receive_json()
        assert meta["type"] == "response_meta"

    assert len(mock_graph.invoked_payloads) > 0
    content = mock_graph.invoked_payloads[0]["messages"][0]["content"]
    assert "9876543210" not in content
    assert "[PHONE]" in content


@pytest.mark.asyncio
async def test_process_audio_chunk_pii_scrubbing():
    """Test that speech transcribed in process_audio_chunk is scrubbed."""
    with patch.object(vad._asr, "transcribe", new_callable=AsyncMock) as mock_transcribe, \
         patch("voice.vad.load_vad_model", return_value="energy_fallback"):
        mock_transcribe.return_value = {
            "text": "My Aadhaar number is 234123412000",
            "confidence": 0.95
        }
        # 16000 samples of high amplitude PCM int16 (32000 bytes) to trigger energy VAD threshold
        fake_pcm = (10000).to_bytes(2, byteorder="little", signed=True) * 16000
        result = await vad.process_audio_chunk("test_session", fake_pcm, "en")
        assert result is not None
        assert result["text"] == "My Aadhaar number is 234123412000"
        assert result["scrubbed_text"] is not None
        assert "234123412000" not in result["scrubbed_text"]
        assert "[AADHAAR]" in result["scrubbed_text"]
