"""
SPT Hospital HRMS — Shift Endpoints
"""
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.models.user import UserRole
from app.models.shift import Shift
from app.utils.audit import log_audit
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/shifts", tags=["Shifts"])

@router.get("/aliases", response_model=dict)
@router.get("/shift-aliases", response_model=dict)
async def list_shift_aliases(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    from app.models.shift import ShiftCodeAlias
    result = await db.execute(
        select(ShiftCodeAlias).options(selectinload(ShiftCodeAlias.shift))
    )
    aliases = result.scalars().all()
    return {
        "items": [
            {
                "id": a.id,
                "device_code": a.device_code,
                "shift_id": a.shift_id,
                "shift_name": a.shift.name if a.shift else None,
                "shift_code": a.shift.code if a.shift else None,
            }
            for a in aliases
        ]
    }

@router.post("/aliases", response_model=dict)
@router.post("/shift-aliases", response_model=dict)
async def create_shift_alias(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    from app.models.shift import ShiftCodeAlias
    alias = ShiftCodeAlias(
        device_code=data["device_code"].upper().strip(),
        shift_id=data["shift_id"],
    )
    db.add(alias)
    await db.commit()
    return {"id": alias.id, "message": f"Alias '{alias.device_code}' created"}

@router.delete("/aliases/{alias_id}", response_model=dict)
@router.delete("/shift-aliases/{alias_id}", response_model=dict)
async def delete_shift_alias(
    alias_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    from app.models.shift import ShiftCodeAlias
    result = await db.execute(select(ShiftCodeAlias).where(ShiftCodeAlias.id == alias_id))
    alias = result.scalar_one_or_none()
    if not alias:
        raise HTTPException(status_code=404, detail="Alias not found")
    await db.delete(alias)
    await db.commit()
    return {"message": "Alias deleted"}


def _shift_dict(s: Shift) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "code": s.code,
        "description": s.description,
        "start_time": s.start_time.strftime("%H:%M") if s.start_time else None,
        "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
        "is_overnight": s.is_overnight,
        "is_split": s.is_split,
        "start_time_2": s.start_time_2.strftime("%H:%M") if s.start_time_2 else None,
        "end_time_2": s.end_time_2.strftime("%H:%M") if s.end_time_2 else None,
        "is_overnight_2": s.is_overnight_2,
        "grace_period_minutes": s.grace_period_minutes,
        "expected_working_minutes": s.expected_working_minutes,
        "ot_threshold_minutes": s.ot_threshold_minutes,
        "is_active": s.is_active,
    }


@router.get("", response_model=dict)
async def list_shifts(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    include_inactive: bool = False,
):
    query = select(Shift)
    if not include_inactive:
        query = query.where(Shift.is_active == True)
    query = query.order_by(Shift.id)
    result = await db.execute(query)
    shifts = result.scalars().all()
    return {"items": [_shift_dict(s) for s in shifts], "total": len(shifts)}


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_shift(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    from datetime import time as dt_time
    existing = await db.execute(select(Shift).where(Shift.code == data["code"].upper()))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Shift code '{data['code']}' already exists.")

    def parse_time(t_str: str) -> dt_time:
        h, m = map(int, t_str.strip().split(":"))
        return dt_time(h, m)

    shift = Shift(
        name=data["name"],
        code=data["code"].upper(),
        description=data.get("description"),
        start_time=parse_time(data["start_time"]),
        end_time=parse_time(data["end_time"]),
        is_overnight=data.get("is_overnight", False),
        grace_period_minutes=data.get("grace_period_minutes", 0),
        expected_working_minutes=data.get("expected_working_minutes", 480),
        ot_threshold_minutes=data.get("ot_threshold_minutes", 480),
    )
    db.add(shift)
    await db.flush()
    await log_audit(db, current_user.id, "CREATE", "Shift", str(shift.id), f"Created shift {shift.code}: {shift.name}")
    await db.commit()
    await db.refresh(shift)
    return _shift_dict(shift)


@router.get("/{shift_id}", response_model=dict)
async def get_shift(shift_id: int, db: Annotated[AsyncSession, Depends(get_db)], current_user: CurrentUser):
    result = await db.execute(select(Shift).where(Shift.id == shift_id))
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    return _shift_dict(shift)


@router.put("/{shift_id}", response_model=dict)
async def update_shift(
    shift_id: int,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    from datetime import time as dt_time
    result = await db.execute(select(Shift).where(Shift.id == shift_id))
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    for field in ["name", "description", "is_overnight", "grace_period_minutes",
                  "expected_working_minutes", "ot_threshold_minutes", "is_active"]:
        if field in data:
            setattr(shift, field, data[field])
    if "start_time" in data:
        h, m = map(int, data["start_time"].split(":"))
        shift.start_time = dt_time(h, m)
    if "end_time" in data:
        h, m = map(int, data["end_time"].split(":"))
        shift.end_time = dt_time(h, m)
    await log_audit(db, current_user.id, "UPDATE", "Shift", str(shift.id), f"Updated shift {shift.code}")
    await db.commit()
    await db.refresh(shift)
    return _shift_dict(shift)


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(
    shift_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN))],
    reassign_to_id: Optional[int] = Query(None),
):
    from app.models.employee import Employee
    from sqlalchemy import update, func

    result = await db.execute(select(Shift).where(Shift.id == shift_id))
    shift = result.scalar_one_or_none()
    if not shift:
        raise HTTPException(status_code=404, detail="Shift not found")

    # Check for active employees referencing this shift
    emp_count_res = await db.execute(
        select(func.count()).select_from(Employee).where(Employee.shift_id == shift_id, Employee.is_active == True)
    )
    emp_count = emp_count_res.scalar() or 0

    if emp_count > 0:
        if not reassign_to_id:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot delete shift '{shift.code}': {emp_count} active employees are assigned to it. Reassign employees first or specify ?reassign_to_id={shift_id}."
            )
        # Verify target shift exists and is active
        target_res = await db.execute(select(Shift).where(Shift.id == reassign_to_id, Shift.is_active == True))
        target_shift = target_res.scalar_one_or_none()
        if not target_shift:
            raise HTTPException(status_code=400, detail="Target reassign shift not found or inactive")
        if target_shift.id == shift.id:
            raise HTTPException(status_code=400, detail="Cannot reassign to the shift being deleted")

        await db.execute(
            update(Employee)
            .where(Employee.shift_id == shift_id)
            .values(shift_id=reassign_to_id)
        )

    shift.is_active = False
    await log_audit(db, current_user.id, "DELETE", "Shift", str(shift.id), f"Deactivated shift {shift.code} (Reassigned {emp_count} staff)")
    await db.commit()
