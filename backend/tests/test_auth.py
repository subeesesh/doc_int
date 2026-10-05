"""Tests for authentication endpoints."""
import pytest
import uuid


UNIQUE = lambda: uuid.uuid4().hex[:8]


def test_register_success(client):
    email = f"user_{UNIQUE()}@test.local"
    resp = client.post("/auth/register", json={
        "name": "Alice",
        "email": email,
        "password": "strongpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["email"] == email
    assert "user_id" in data


def test_register_duplicate_email(client):
    email = f"dup_{UNIQUE()}@test.local"
    client.post("/auth/register", json={"name": "Bob", "email": email, "password": "pass123"})
    resp = client.post("/auth/register", json={"name": "Bob2", "email": email, "password": "pass456"})
    assert resp.status_code == 400


def test_login_success(client):
    email = f"login_{UNIQUE()}@test.local"
    password = "loginpass123"
    client.post("/auth/register", json={"name": "Charlie", "email": email, "password": password})
    
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["email"] == email


def test_login_wrong_password(client):
    email = f"wp_{UNIQUE()}@test.local"
    client.post("/auth/register", json={"name": "Dave", "email": email, "password": "correct"})
    
    resp = client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_email(client):
    resp = client.post("/auth/login", json={"email": "nobody@test.local", "password": "whatever"})
    assert resp.status_code == 401


def test_get_me_authenticated(client, auth_headers):
    resp = client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "email" in data
    assert "id" in data


def test_get_me_unauthenticated(client):
    resp = client.get("/auth/me")
    assert resp.status_code == 401


def test_get_me_invalid_token(client):
    resp = client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert resp.status_code == 401
