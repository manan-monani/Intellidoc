"""
Auth Service
============
Authentication and authorization business logic.

Handles:
- Password hashing using bcrypt
- JWT token creation and verification
- User registration and login
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import User
from app.schemas.user import UserCreate

import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Password Hashing ────────────────────────────────────────
# bcrypt is a one-way hash — you can verify a password against
# its hash but never recover the original password.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    Handles user authentication.

    Usage:
        auth = AuthService(db_session)
        user = await auth.register(user_data)
        token = await auth.login("username", "password")
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Password Utilities ───────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.

        How it works:
        1. Generates a random salt
        2. Combines salt + password and runs bcrypt algorithm
        3. Returns the hash (which includes the salt)
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    # ── JWT Token ────────────────────────────────────────────

    @staticmethod
    def create_access_token(
        user_id: str,
        username: str,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Create a JWT access token.

        How JWT works:
        1. Header: algorithm and token type (set automatically)
        2. Payload: your data (user_id, username, expiry)
        3. Signature: Header + Payload encrypted with SECRET_KEY
        The client sends this token with every request.
        Server verifies the signature to trust the payload.
        """
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.jwt_access_token_expire_minutes
            )

        payload = {
            "sub": user_id,          # Subject (who the token is for)
            "username": username,
            "exp": expire,           # Expiration time
            "iat": datetime.now(timezone.utc),  # Issued at
        }

        return jwt.encode(
            payload,
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """
        Verify and decode a JWT token.

        Returns the payload if valid, None if expired or tampered.
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
            return payload
        except JWTError as e:
            logger.warning(f"JWT verification failed: {e}")
            return None

    # ── User Operations ──────────────────────────────────────

    async def register(self, user_data: UserCreate) -> User:
        """
        Register a new user.

        Steps:
        1. Check if username/email already exists
        2. Hash the password
        3. Create the user record
        """
        # Check for existing user
        existing = await self.db.execute(
            select(User).where(
                (User.email == user_data.email) |
                (User.username == user_data.username)
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError("Username or email already registered")

        # Create user with hashed password
        user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=self.hash_password(user_data.password),
            full_name=user_data.full_name,
        )
        self.db.add(user)
        await self.db.flush()

        logger.info(f"Registered new user: {user.username}")
        return user

    async def login(
        self,
        username: str,
        password: str,
    ) -> Optional[tuple]:
        """
        Authenticate a user and return (user, token).

        Returns None if credentials are invalid.
        """
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user or not self.verify_password(password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        token = self.create_access_token(
            user_id=str(user.id),
            username=user.username,
        )

        logger.info(f"User logged in: {user.username}")
        return user, token

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get a user by their ID."""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
