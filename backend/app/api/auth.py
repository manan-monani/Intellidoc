"""
Auth API Routes
===============
Endpoints for user registration and login.

Endpoints:
    POST /api/auth/register  — Create a new user account
    POST /api/auth/login     — Login and get JWT token
    GET  /api/auth/me        — Get current user info
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.auth_service import AuthService
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
security = HTTPBearer()


# ── Register ─────────────────────────────────────────────────

@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.

    Flow:
    1. Validate email and username are unique
    2. Hash the password with bcrypt
    3. Create user in database
    4. Generate JWT token
    5. Return token + user data
    """
    auth = AuthService(db)

    try:
        user = await auth.register(user_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    token = auth.create_access_token(
        user_id=str(user.id),
        username=user.username,
    )

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ── Login ────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with username and password.

    Returns a JWT token that must be sent in the Authorization header
    for all authenticated requests: `Authorization: Bearer <token>`
    """
    auth = AuthService(db)
    result = await auth.login(credentials.username, credentials.password)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    user, token = result

    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ── Get Current User ────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """
    FastAPI dependency that extracts and verifies the JWT token.

    Usage in any route:
        @router.get("/protected")
        async def protected_route(user = Depends(get_current_user)):
            return {"message": f"Hello, {user.username}!"}
    """
    token = credentials.credentials
    payload = AuthService.verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    auth = AuthService(db)
    user = await auth.get_user_by_id(UUID(payload["sub"]))

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


@router.get("/me", response_model=UserResponse)
async def get_me(user=Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return user
