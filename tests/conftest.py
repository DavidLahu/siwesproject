"""Shared test setup. pytest loads this file automatically before the tests."""

import os

# These must be set before anything imports the app, because app/config.py reads
# the settings on import. They also take priority over any local .env file, so
# running the tests never touches your development database.
os.environ["SECRET_KEY"] = "test-secret-key-used-only-by-the-automated-tests"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """A test client backed by a brand new, empty in-memory database.

    Each test gets its own database, so tests can't affect each other.
    """
    # StaticPool keeps one connection open. An in-memory SQLite database only
    # exists inside its connection, so a second connection would find it empty.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db() -> Generator[Session, None, None]:
        with TestSession() as db:
            yield db

    # Routes that ask for get_db now receive the test database instead.
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def auth_headers(client: TestClient):
    """A helper that signs up and logs in a user, returning their auth headers."""

    def _auth_headers(email: str = "ann@example.com") -> dict[str, str]:
        credentials = {"email": email, "password": "correct-password"}
        assert client.post("/auth/signup", json=credentials).status_code == 201
        token = client.post("/auth/login", json=credentials).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers
