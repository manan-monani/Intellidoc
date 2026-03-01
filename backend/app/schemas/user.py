"""
User Schemas
============
Pydantic models for authentication and user management.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime


class UserCreate(BaseModel):
    """Registration schema."""
    email: str = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8, description="Plain text password")
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    """Login schema."""
    username: str
    password: str


class UserResponse(BaseModel):
    """User data returned to client (no password!)."""
    id: UUID
    email: str
    username: str
    full_name: Optional[str] = None
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """JWT token returned after login."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
