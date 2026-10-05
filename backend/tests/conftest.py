"""
Pytest configuration and fixtures for the EDI platform test suite.

NOTE: Models use JSONB (PostgreSQL-only) columns which SQLite cannot handle.
For unit tests (chunking, fusion, security, knowledge extraction) we don't need
a real DB at all — they mock the DB session. Only API/integration tests that
need actual DB tables use conftest.db. Those are decorated with
@pytest.mark.skipif to skip if PostgreSQL is not available.
"""
import os
import pytest
import uuid
from unittest.mock import MagicMock

# ─── Environment guard ────────────────────────────────────────────────────────
# If PostgreSQL is not available (e.g., CI without Docker), skip API tests
POSTGRES_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://enterprise_user:enterprise_password@localhost:5433/enterprise_db"
)

def _postgres_available():
    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(POSTGRES_URL, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

POSTGRES_UP = _postgres_available()


# ─── API test fixtures (need real Postgres) ───────────────────────────────────
if POSTGRES_UP:
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import create_engine
    from app.main import app
    from app.db.database import get_db

    engine_test = create_engine(POSTGRES_URL)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture()
    def db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.rollback()
            session.close()

    @pytest.fixture()
    def client(db):
        from fastapi.testclient import TestClient
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
        app.dependency_overrides.clear()

    @pytest.fixture()
    def auth_headers(client):
        email = f"test_{uuid.uuid4().hex[:6]}@test.local"
        password = "testpassword123"
        client.post("/auth/register", json={"name": "Test User", "email": email, "password": password})
        resp = client.post("/auth/login", json={"email": email, "password": password})
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

else:
    # Stub fixtures so the file can still be collected without Postgres
    @pytest.fixture()
    def db():
        pytest.skip("PostgreSQL not available")

    @pytest.fixture()
    def client():
        pytest.skip("PostgreSQL not available")

    @pytest.fixture()
    def auth_headers():
        pytest.skip("PostgreSQL not available")


# ─── Shared marker for postgres-required tests ────────────────────────────────
requires_postgres = pytest.mark.skipif(
    not POSTGRES_UP,
    reason="PostgreSQL not running — start Docker Compose to run API tests"
)
