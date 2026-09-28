"""
SPT Hospital HRMS — FastAPI Dependencies
Reusable dependency functions for authentication and authorization.
"""
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate the current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated" if not credentials else "Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not credentials or not credentials.credentials:
        raise credentials_exception

    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise credentials_exception
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure the user account is active."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account")
    return current_user


def require_roles(*roles: UserRole):
    """Dependency factory — restricts endpoint access to specific roles."""
    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return role_checker


# Convenience dependency aliases
RequireSuperAdmin = Depends(require_roles(UserRole.SUPER_ADMIN))
RequireHRAdmin = Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))
RequireManager = Depends(
    require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN, UserRole.DEPT_MANAGER)
)
CurrentUser = Annotated[User, Depends(get_current_active_user)]
