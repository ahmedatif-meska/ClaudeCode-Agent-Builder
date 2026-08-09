"""Proves the app boots, the lifespan builds the agent, and capabilities are reported."""

from fastapi.testclient import TestClient

from app.main import app


def test_health_reports_the_agent_and_its_capabilities() -> None:
    with TestClient(app) as client:  # `with` runs the lifespan
        response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert isinstance(body["capabilities"], list)
    # The key must never travel to a client.
    assert "sk-" not in response.text
