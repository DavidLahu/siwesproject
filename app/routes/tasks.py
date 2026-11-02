"""CRUD routes for tasks. Every route requires a valid token and only ever acts
on the logged-in user's own tasks."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Task, User
from app.schemas import TaskCreate, TaskResponse, TaskUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

# The {id} path parameter. The limits match what an Integer column can hold, so
# a huge number gets a 422 here instead of causing a database error.
TaskId = Annotated[int, Path(gt=0, le=2_147_483_647)]


def get_owned_task(task_id: int, db: Session, current_user: User) -> Task:
    """Load a task, enforcing ownership. Used by every route that takes an id.

    Someone else's task gets the same 404 as a missing task, so users can't
    discover which task ids exist.
    """
    task = db.get(Task, task_id)
    if task is None or task.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    task_in: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    """Create a task owned by the logged-in user."""
    task = Task(title=task_in.title, description=task_in.description, owner_id=current_user.id)
    db.add(task)
    db.commit()
    db.refresh(task)

    logger.info("Task created: id=%s owner_id=%s", task.id, current_user.id)
    return task


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    is_done: bool | None = Query(default=None, description="Only return tasks with this status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Task]:
    """List the logged-in user's tasks, optionally filtered by ?is_done=true/false."""
    query = select(Task).where(Task.owner_id == current_user.id).order_by(Task.id)
    if is_done is not None:
        query = query.where(Task.is_done == is_done)
    return list(db.scalars(query))


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: TaskId,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    """Get one task."""
    return get_owned_task(task_id, db, current_user)


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: TaskId,
    task_in: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    """Replace a task's title, description, and is_done status."""
    task = get_owned_task(task_id, db, current_user)
    task.title = task_in.title
    task.description = task_in.description
    task.is_done = task_in.is_done
    db.commit()
    db.refresh(task)

    logger.info("Task updated: id=%s owner_id=%s", task.id, current_user.id)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: TaskId,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a task. A 204 response has no body."""
    task = get_owned_task(task_id, db, current_user)
    db.delete(task)
    db.commit()

    logger.info("Task deleted: id=%s owner_id=%s", task_id, current_user.id)
