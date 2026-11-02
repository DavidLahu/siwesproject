"""Routes for creating an account and logging in.

The route functions here and in tasks.py use plain "def", not "async def".
FastAPI runs these in a worker thread, so slow work like bcrypt hashing and
database queries doesn't block other requests.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import Token, UserCreate, UserLogin, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(user_in: UserCreate, db: Session = Depends(get_db)) -> User:
    """Create a new user, storing only the hash of their password."""
    user = User(email=user_in.email, hashed_password=hash_password(user_in.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint on email rejected this insert. Relying on the
        # database also covers two signups with the same email at the same time.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")
    db.refresh(user)

    logger.info("New user signed up: id=%s", user.id)
    return user


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)) -> Token:
    """Check an email and password, and return a JWT access token."""
    user = db.scalar(select(User).where(User.email == credentials.email))

    # The same message for both failures, so it doesn't reveal which part was wrong.
    if user is None or not verify_password(credentials.password, user.hashed_password):
        logger.warning("Failed login attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info("User logged in: id=%s", user.id)
    return Token(access_token=create_access_token(user.id))
