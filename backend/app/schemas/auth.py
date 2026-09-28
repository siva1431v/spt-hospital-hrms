"""
SPT Hospital HRMS — Pydantic Schemas for Auth
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class LoginRequest(BaseModel):
    username: str  # Accepts email or username
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    full_name: str
    role: str
    is_active: bool
    must_change_password: bool = False
    employee_id: Optional[int] = None
    last_login: Optional[datetime] = None
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str

