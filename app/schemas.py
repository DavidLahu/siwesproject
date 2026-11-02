"""Pydantic schemas: the shape of data entering and leaving the API.

These are separate from the ORM models on purpose. For example, UserResponse
has no hashed_password field, so the hash can never appear in a response.
If a request does not match its schema, FastAPI answers 422 automatically.
"""

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

# Lowercased so that Ann@example.com and ann@example.com are the same account.
Email = Annotated[EmailStr, AfterValidator(str.lower)]


def reject_null_characters(value: str) -> str:
    """Reject null characters, which bcrypt and Postgres text columns can't handle."""
    if "\x00" in value:
        raise ValueError("Must not contain null characters")
    return value


# Spaces around the title are removed first, so "   " counts as empty and is
# rejected. The maximum matches the String(200) column in models.py.
Title = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(reject_null_characters),
]

Description = Annotated[str, AfterValidator(reject_null_characters)]


# ----- Users and authentication -----


class UserCreate(BaseModel):
    """Body of POST /auth/signup."""

    email: Email
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def password_must_work_with_bcrypt(cls, value: str) -> str:
        # bcrypt only uses the first 72 bytes of a password, so a longer one is
        # rejected rather than silently cut short.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes long")
        return reject_null_characters(value)


class UserLogin(BaseModel):
    """Body of POST /auth/login. The password rules are not repeated here: a
    password that breaks them simply will not match, giving a normal 401."""

    email: Email
    password: str


class UserResponse(BaseModel):
    """A user as returned to clients. Note: no password or hash."""

    # Allows building this schema from a SQLAlchemy object, not just a dict.
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class Token(BaseModel):
    """Response of POST /auth/login."""

    access_token: str
    token_type: str = "bearer"


# ----- Tasks -----


class TaskCreate(BaseModel):
    """Body of POST /tasks. There is no owner_id field: the owner always comes
    from the login token, so a client cannot create tasks for someone else."""

    title: Title
    description: Description | None = None


class TaskUpdate(BaseModel):
    """Body of PUT /tasks/{id}. PUT replaces the whole task, so the client sends
    its complete new state. Leaving out description clears it."""

    title: Title
    description: Description | None = None
    is_done: bool


class TaskResponse(BaseModel):
    """A task as returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    is_done: bool
    owner_id: int
    created_at: datetime
