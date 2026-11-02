"""Database connection setup, shared by the whole app."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# SQLite normally only allows the thread that opened a connection to use it,
# but FastAPI may handle a request across different threads. This option is
# SQLite-specific, so other databases such as Postgres must not receive it.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

# The engine manages the actual connections to the database.
# pool_pre_ping tests a connection before using it, so one the database server
# closed while idle gets replaced instead of causing an error.
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=True)

# A factory that creates a new Session (a unit of work with the database).
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """Parent class of all ORM models (see models.py)."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: give each request its own session, then close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
