"""Tests for the /health endpoint."""
import pytest


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_has_status_field(client):
    resp = client.get("/health")
    data = resp.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")


def test_health_has_services(client):
    resp = client.get("/health")
    data = resp.json()
    assert "services" in data
    assert isinstance(data["services"], dict)
    # Expect at minimum these keys
    for key in ("postgres", "qdrant", "redis", "minio", "neo4j", "llm"):
        assert key in data["services"], f"Missing service key: {key}"
