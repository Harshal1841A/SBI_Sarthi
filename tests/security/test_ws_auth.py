import sys
import os
sys.path.insert(0, os.path.abspath('backend'))

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from main import app, API_TOKEN


def test_ws_auth_rejection() -> None:
    """Assert rejection without token or with bad token on WebSocket connection."""
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/voice?token=bad_token") as ws:
            ws.receive_json()
    assert exc_info.value.code == 4001

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/voice") as ws:
            ws.send_json({"type": "auth", "token": "wrong_token"})
            ws.receive_json()
    assert exc_info.value.code == 4001


def test_ws_auth_success() -> None:
    """Assert success when authenticating with good token via first frame."""
    client = TestClient(app)
    with client.websocket_connect("/ws/voice") as ws:
        ws.send_json({"type": "auth", "token": API_TOKEN})
        data = ws.receive_json()
        assert data.get("type") == "session_init"
