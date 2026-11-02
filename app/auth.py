"""Authentication helpers: password hashing, JWT tokens, and the current user."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

logger = logging.getLogger(__name__)

# The algorithm used to sign tokens. HS256 uses the single SECRET_KEY.
ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Reads the "Authorization: Bearer <token>" header and also adds the Authorize
# button to the /docs page. auto_error=False means a missing header gives us
# None, so get_current_user can answer every auth failure the same way.
bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    """Turn a plain password into a bcrypt hash that is safe to store."""
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a login attempt against the stored hash."""
    try:
        return pwd_context.verify(password, hashed_password)
    except ValueError:
        # passlib raises this for input bcrypt cannot process, such as a
        # password with a null character. It can't be correct, so it's a no.
        return False


def create_access_token(user_id: int) -> str:
    """Create a signed JWT that says who the user is and when it expires."""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    # "sub" (subject) and "exp" (expiry) are standard JWT field names.
    payload = {"sub": str(user_id), "exp": expires_at}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Reusable dependency: read the JWT and load the logged-in user.

    Any route that declares Depends(get_current_user) is protected. If the
    token is missing, invalid, or expired, the route never runs and the client
    gets a 401.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        # decode() checks both the signature and the expiry time.
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        logger.warning("Rejected an invalid authentication token")
        raise unauthorized

    # The token may be valid while the user no longer exists.
    user = db.get(User, user_id)
    if user is None:
        logger.warning("Rejected a token for unknown user id=%s", user_id)
        raise unauthorized

    return user
