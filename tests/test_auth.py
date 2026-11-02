"""Tests for signup, login, and rejecting bad tokens."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from jose import jwt

from app.auth import ALGORITHM
from app.config import settings
from app.database import get_db
from app.main import app

CREDENTIALS = {"email": "ann@example.com", "password": "correct-password"}


def test_signup_creates_user_without_exposing_password(client: TestClient):
    response = client.post("/auth/signup", json=CREDENTIALS)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == CREDENTIALS["email"]
    assert "password" not in body
    assert "hashed_password" not in body


def test_signup_rejects_duplicate_email_in_any_letter_case(client: TestClient):
    client.post("/auth/signup", json=CREDENTIALS)

    response = client.post("/auth/signup", json={**CREDENTIALS, "email": "ANN@example.com"})

    assert response.status_code == 409


@pytest.mark.parametrize(
    "bad_body",
    [
        {"email": "not-an-email", "password": "correct-password"},
        {"email": "ann@example.com", "password": "short"},
        {"email": "ann@example.com", "password": "x" * 73},  # over bcrypt's limit
        {"email": "ann@example.com", "password": "null\x00character"},
    ],
)
def test_signup_rejects_invalid_input(client: TestClient, bad_body: dict):
    assert client.post("/auth/signup", json=bad_body).status_code == 422


def test_login_returns_a_token(client: TestClient):
    client.post("/auth/signup", json=CREDENTIALS)

    response = client.post("/auth/login", json=CREDENTIALS)

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


@pytest.mark.parametrize(
    "bad_password",
    [
        "wrong-password",
        "null\x00character",  # bcrypt can't process this, so it must not crash
        "x" * 5000,  # neither can passlib process this
    ],
)
def test_login_rejects_wrong_password(client: TestClient, bad_password: str):
    client.post("/auth/signup", json=CREDENTIALS)

    response = client.post("/auth/login", json={**CREDENTIALS, "password": bad_password})

    assert response.status_code == 401


def test_login_rejects_unknown_email(client: TestClient):
    assert client.post("/auth/login", json=CREDENTIALS).status_code == 401


def test_task_routes_reject_missing_token(client: TestClient):
    assert client.get("/tasks").status_code == 401


def test_task_routes_reject_invalid_token(client: TestClient):
    response = client.get("/tasks", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_task_routes_reject_expired_token(client: TestClient):
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = jwt.encode({"sub": "1", "exp": expired}, settings.secret_key, algorithm=ALGORITHM)

    response = client.get("/tasks", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_unexpected_errors_do_not_leak_details_to_the_client(client: TestClient):
    def broken_database():
        raise RuntimeError("secret internal detail")

    app.dependency_overrides[get_db] = broken_database
    # By default TestClient re-raises server errors; here we want to see the
    # response a real client would get.
    no_raise_client = TestClient(app, raise_server_exceptions=False)

    response = no_raise_client.post("/auth/login", json=CREDENTIALS)

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
