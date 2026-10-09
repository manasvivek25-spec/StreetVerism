"""Tests for CORS configuration and X-Mock-Data exposure."""

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_cors_options_preflight_with_authority_key():
    """Verify OPTIONS preflight with Origin and x-authority-key header succeeds."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "x-authority-key,content-type",
    }
    response = client.options("/api/alerts", headers=headers)
    assert response.status_code == 200
    allow_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "x-authority-key" in allow_headers
    assert "content-type" in allow_headers


def test_cors_expose_headers_includes_x_mock_data():
    """Verify normal response with Origin includes access-control-expose-headers containing X-Mock-Data."""
    headers = {"Origin": "http://localhost:5173"}
    response = client.get("/health", headers=headers)
    assert response.status_code == 200
    expose_headers = response.headers.get("access-control-expose-headers", "")
    assert "X-Mock-Data" in expose_headers
    assert response.headers.get("X-Mock-Data") == "1"


def test_cors_wildcard_disables_credentials():
    """Verify that wildcard origin disables Access-Control-Allow-Credentials."""
    headers = {"Origin": "http://localhost:5173"}
    response = client.get("/health", headers=headers)
    assert response.headers.get("access-control-allow-credentials") is None
