"""The application's entry point: creates the FastAPI app and wires it together.

Run it with:  uvicorn app.main:app --reload
"""

import logging
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from app import models  # noqa: F401 - registers the tables on Base.metadata before create_all runs
from app.database import Base, engine
from app.routes.auth import router as auth_router
from app.routes.tasks import router as tasks_router

# Set up logging once for the whole app. Modules get their own logger with
# logging.getLogger(__name__), and their messages all end up here. Logs go to
# the console, which is also where hosting platforms usually collect them.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Code that runs when the server starts, before it accepts any requests."""
    # Creates any tables that don't exist yet. It leaves existing tables alone.
    Base.metadata.create_all(bind=engine)
    logger.info("Application started, database tables are ready")
    yield


app = FastAPI(title="Task Manager API", lifespan=lifespan)


@app.middleware("http")
async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log every request with its status code and how long it took.

    Only the method and path are logged, never the headers or body, because
    those contain passwords and tokens.
    """
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Client errors (4xx) are logged as warnings so they stand out from normal traffic.
    level = logging.WARNING if response.status_code >= 400 else logging.INFO
    logger.log(level, "%s %s -> %s (%.1f ms)", request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Last line of defence for bugs and outages, such as the database being down.

    The full details go to the log for the developer. The client only gets a
    generic message, so internal details and stack traces never reach them.
    """
    logger.error("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


app.include_router(auth_router)
app.include_router(tasks_router)
