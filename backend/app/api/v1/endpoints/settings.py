"""
SPT Hospital HRMS — Audit Log & Settings Endpoints
"""
from typing import Annotated, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.models.user import UserRole, User
from app.models.audit import AuditLog, SystemSetting
from app.core.security import get_password_hash

router = APIRouter(tags=["Audit & Settings"])


# ─── Audit Logs ────────────────────────────────────────────────────────────────
@router.get("/audit-logs", response_model=dict)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    if action:
        query = query.where(AuditLog.action.ilike(f"%{action}%"))
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if date_from:
        query = query.where(func.date(AuditLog.created_at) >= date_from)
    if date_to:
        query = query.where(func.date(AuditLog.created_at) <= date_to)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    logs = result.scalars().all()

    # Load user names
    user_ids = list({log.user_id for log in logs if log.user_id})
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u.full_name for u in users_result.scalars().all()}

    return {
        "items": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "user_name": users_map.get(log.user_id, "System") if log.user_id else "System",
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "description": log.description,
                "created_at": log.created_at,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ─── System Settings ───────────────────────────────────────────────────────────
@router.get("/settings", response_model=dict)
async def get_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    result = await db.execute(select(SystemSetting).order_by(SystemSetting.category, SystemSetting.key))
    settings_list = result.scalars().all()

    grouped: dict = {}
    for s in settings_list:
        cat = s.category or "GENERAL"
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append({"key": s.key, "value": s.value, "description": s.description})

    return {"settings": grouped}


@router.put("/settings", response_model=dict)
async def update_settings(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """Batch update system settings."""
    updates = data.get("updates", {})
    for key, value in updates.items():
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = str(value) if value is not None else None
            setting.updated_by_id = current_user.id
        else:
            new_setting = SystemSetting(key=key, value=str(value), updated_by_id=current_user.id)
            db.add(new_setting)
    await db.commit()
    return {"message": f"Updated {len(updates)} settings"}


# ─── User Management ───────────────────────────────────────────────────────────
@router.get("/users", response_model=dict)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN))],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = select(User).order_by(User.created_at.desc())
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    users = result.scalars().all()
    return {
        "items": [
            {
                "id": u.id, "username": u.username, "email": u.email,
                "full_name": u.full_name, "role": u.role.value,
                "is_active": u.is_active, "last_login": u.last_login,
                "created_at": u.created_at,
            }
            for u in users
        ],
        "total": total, "page": page, "page_size": page_size,
    }


@router.post("/users", response_model=dict)
async def create_user(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN))],
):
    existing = await db.execute(
        select(User).where((User.email == data["email"]) | (User.username == data["username"]))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already exists.")

    user = User(
        username=data["username"],
        email=data["email"],
        full_name=data["full_name"],
        hashed_password=get_password_hash(data["password"]),
        role=UserRole(data.get("role", UserRole.EMPLOYEE.value)),
        is_active=data.get("is_active", True),
        employee_id=data.get("employee_id"),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role.value}


@router.put("/users/{user_id}", response_model=dict)
async def update_user(
    user_id: int,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN))],
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for field in ["full_name", "email", "is_active", "employee_id"]:
        if field in data:
            setattr(user, field, data[field])
    if "role" in data:
        user.role = UserRole(data["role"])
    if "password" in data and data["password"]:
        user.hashed_password = get_password_hash(data["password"])

    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "username": user.username, "role": user.role.value, "is_active": user.is_active}


@router.delete("/users/{user_id}", response_model=dict)
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN))],
):
    """Delete a user account (Super Admin only)."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own user account.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.username == "admin":
        raise HTTPException(status_code=400, detail="The root 'admin' user cannot be deleted.")

    try:
        await db.delete(user)
        await db.commit()
        return {"message": f"User '{user.username}' deleted successfully."}
    except Exception:
        await db.rollback()
        # Fallback: if foreign keys exist (e.g. created imports or payroll), soft-deactivate
        user.is_active = False
        await db.commit()
        return {
            "message": f"User '{user.username}' is referenced by historical records, so the account has been deactivated instead of deleted."
        }
