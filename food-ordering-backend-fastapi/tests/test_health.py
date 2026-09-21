"""
Smoke tests for the only routes with real behavior in this skeleton.
Everything else is a 501 stub — see test_stub_routes_return_501.
"""

from fastapi.testclient import TestClient


def test_root(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200


def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "health OK!"
    assert "uptime" in body
    assert "timestamp" in body
    assert "serverStartTime" in body


def test_api_health(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["message"] == "health OK!"


def test_stub_routes_return_501(client: TestClient):
    """
    Confirms the structure-only guarantee: business routes are wired and
    reachable, but explicitly not implemented yet.
    """
    response = client.get("/api/restaurant/cities/all")
    assert response.status_code == 501
    assert "message" in response.json()
