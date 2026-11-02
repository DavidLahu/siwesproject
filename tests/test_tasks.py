"""Tests for task CRUD, input validation, and ownership."""

import pytest
from fastapi.testclient import TestClient


def test_create_task(client: TestClient, auth_headers):
    response = client.post(
        "/tasks",
        json={"title": "Write report", "description": "SIWES chapter 3"},
        headers=auth_headers(),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Write report"
    assert body["description"] == "SIWES chapter 3"
    assert body["is_done"] is False


@pytest.mark.parametrize(
    "bad_body",
    [
        {},  # no title
        {"title": ""},
        {"title": "   "},
        {"title": "x" * 201},
        {"title": "null\x00character"},  # Postgres can't store these
        {"title": "Valid", "description": "null\x00character"},
    ],
)
def test_create_task_rejects_invalid_input(client: TestClient, auth_headers, bad_body: dict):
    response = client.post("/tasks", json=bad_body, headers=auth_headers())

    assert response.status_code == 422


def test_list_tasks_filters_by_is_done(client: TestClient, auth_headers):
    headers = auth_headers()
    client.post("/tasks", json={"title": "Still to do"}, headers=headers)
    finished = client.post("/tasks", json={"title": "Finished"}, headers=headers).json()
    client.put(f"/tasks/{finished['id']}", json={"title": "Finished", "is_done": True}, headers=headers)

    all_tasks = client.get("/tasks", headers=headers).json()
    done_tasks = client.get("/tasks", params={"is_done": True}, headers=headers).json()
    open_tasks = client.get("/tasks", params={"is_done": False}, headers=headers).json()

    assert [task["title"] for task in all_tasks] == ["Still to do", "Finished"]
    assert [task["title"] for task in done_tasks] == ["Finished"]
    assert [task["title"] for task in open_tasks] == ["Still to do"]


def test_list_tasks_rejects_invalid_filter(client: TestClient, auth_headers):
    response = client.get("/tasks", params={"is_done": "maybe"}, headers=auth_headers())

    assert response.status_code == 422


def test_get_update_and_delete_task(client: TestClient, auth_headers):
    headers = auth_headers()
    task_id = client.post("/tasks", json={"title": "Old title"}, headers=headers).json()["id"]

    assert client.get(f"/tasks/{task_id}", headers=headers).json()["title"] == "Old title"

    updated = client.put(
        f"/tasks/{task_id}",
        json={"title": "New title", "description": "Added", "is_done": True},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "New title"
    assert updated.json()["description"] == "Added"
    assert updated.json()["is_done"] is True

    assert client.delete(f"/tasks/{task_id}", headers=headers).status_code == 204
    assert client.get(f"/tasks/{task_id}", headers=headers).status_code == 404


@pytest.mark.parametrize(
    ("task_id", "expected_status"),
    [
        (999, 404),  # a valid id with no task
        (99_999_999_999_999_999_999, 422),  # too large for the database
        ("abc", 422),  # not a number
    ],
)
def test_get_task_with_bad_id(client: TestClient, auth_headers, task_id, expected_status: int):
    response = client.get(f"/tasks/{task_id}", headers=auth_headers())

    assert response.status_code == expected_status


def test_user_cannot_access_another_users_task(client: TestClient, auth_headers):
    ann = auth_headers("ann@example.com")
    ben = auth_headers("ben@example.com")
    task_id = client.post("/tasks", json={"title": "Ann's task"}, headers=ann).json()["id"]

    # Ben can't read, change, or delete Ann's task, or see it in his list.
    assert client.get(f"/tasks/{task_id}", headers=ben).status_code == 404
    assert client.put(f"/tasks/{task_id}", json={"title": "Hacked", "is_done": True}, headers=ben).status_code == 404
    assert client.delete(f"/tasks/{task_id}", headers=ben).status_code == 404
    assert client.get("/tasks", headers=ben).json() == []

    # And Ann's task is unchanged.
    assert client.get(f"/tasks/{task_id}", headers=ann).json()["title"] == "Ann's task"
