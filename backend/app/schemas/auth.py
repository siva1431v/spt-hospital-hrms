"""
SPT Hospital HRMS — Pydantic Schemas for Auth
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field


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
    new_password: str = Field(..., min_length=8, description="New password must be at least 8 characters long")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    email: str
    full_name: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8, description="Initial password must be at least 8 characters long")
    role: Optional[str] = "EMPLOYEE"
    is_active: Optional[bool] = True
    employee_id: Optional[int] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, description="New password must be at least 8 characters long if provided")
    role: Optional[str] = None
    is_active: Optional[bool] = None
    employee_id: Optional[int] = None

