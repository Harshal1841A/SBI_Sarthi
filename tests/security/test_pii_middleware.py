import sys
import os
sys.path.insert(0, os.path.abspath('backend'))

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from security.pii_middleware import PIIIngressMiddleware


@pytest.fixture
def app_with_middleware() -> FastAPI:
    """Create a test FastAPI app with PIIIngressMiddleware."""
    app = FastAPI()
    app.add_middleware(PIIIngressMiddleware)

    @app.post("/api/chat/message")
    async def echo_handler(request: Request) -> dict:
        """Echo back the JSON body received by the route handler."""
        data = await request.json()
        return {"received": data}

    return app


def test_pii_middleware_scrubs_aadhaar(app_with_middleware: FastAPI) -> None:
    """Test that 12-digit Aadhaar numbers in POST /api/chat/* are scrubbed to [AADHAAR]."""
    client = TestClient(app_with_middleware)
    payload = {"message": "My Aadhaar number is 234567890123 please verify."}
    response = client.post("/api/chat/message", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "[AADHAAR]" in data["received"]["message"]
    assert "234567890123" not in data["received"]["message"]
