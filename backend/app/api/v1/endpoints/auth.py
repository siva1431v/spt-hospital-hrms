"""
SPT Hospital HRMS — Authentication API Endpoints
"""
from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.deps import get_current_active_user, CurrentUser
from app.models.user import User
from app.schemas.auth import TokenResponse, LoginRequest, UserResponse, RefreshTokenRequest
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Login with email/username and password. Returns JWT access + refresh tokens."""
    # Find user by email or username
    result = await db.execute(
        select(User).where(
            (User.email == login_data.username) | (User.username == login_data.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact administrator.",
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    access_token = create_access_token(user.id, user.role.value)
    refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Exchange a refresh token for a new access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    try:
        payload = decode_token(refresh_data.refresh_token)
        if payload.get("type") != "refresh":
            raise credentials_exception
        user_id = payload.get("sub")
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception

    access_token = create_access_token(user.id, user.role.value)
    new_refresh_token = create_refresh_token(user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUser):
    """Get current authenticated user profile."""
    return current_user


from app.schemas.auth import TokenResponse, LoginRequest, UserResponse, ChangePasswordRequest
from app.core.security import get_password_hash

@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Change current user's password."""
    if not verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password",
        )
    if len(data.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters long",
        )
    current_user.hashed_password = get_password_hash(data.new_password)
    current_user.must_change_password = False
    await db.commit()
    return {"message": "Password changed successfully"}


@router.post("/logout")
async def logout(current_user: CurrentUser):
    """Logout (client should discard token)."""
    # JWT is stateless; client must delete the token.
    # Future: add token to blocklist in Redis.
    return {"message": "Logged out successfully"}
