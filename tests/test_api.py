import pytest
import os
import sys
from fastapi.testclient import TestClient

backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

import main
from main import app


class TestAPI:
    def test_health_check(self):
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["version"] == "2.0.0"
        assert "services" in data
