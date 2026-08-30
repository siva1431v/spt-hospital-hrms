"""
SPT Hospital HRMS — Leave API Endpoints
"""
from typing import Annotated, Optional
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.models.user import UserRole
from app.models.leave import LeaveType, LeaveRequest, LeaveBalance, LeaveRequestStatus
from app.models.employee import Employee
from app.utils.audit import log_audit

router = APIRouter(tags=["Leave Management"])


# ─── Leave Types ───────────────────────────────────────────────────────────────
@router.get("/leave-types", response_model=dict)
async def list_leave_types(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(select(LeaveType).where(LeaveType.is_active == True))
    leave_types = result.scalars().all()
    return {
        "items": [
            {
                "id": lt.id, "name": lt.name, "code": lt.code,
                "is_paid": lt.is_paid, "max_days_per_year": lt.max_days_per_year,
            }
            for lt in leave_types
        ]
    }


@router.post("/leave-types", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_leave_type(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    lt = LeaveType(
        name=data["name"],
        code=data["code"].upper(),
        is_paid=data.get("is_paid", True),
        max_days_per_year=data.get("max_days_per_year"),
        description=data.get("description"),
    )
    db.add(lt)
    await db.flush()
    await log_audit(db, current_user.id, "CREATE", "LeaveType", str(lt.id), f"Created leave type {lt.name}")
    await db.commit()
    await db.refresh(lt)
    return {"id": lt.id, "name": lt.name, "code": lt.code}


# ─── Leave Requests ────────────────────────────────────────────────────────────
@router.get("/leaves", response_model=dict)
async def list_leave_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    status_filter: Optional[str] = Query(None),
    employee_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    query = (
        select(LeaveRequest)
        .options(
            selectinload(LeaveRequest.employee),
            selectinload(LeaveRequest.leave_type),
        )
        .order_by(LeaveRequest.applied_at.desc())
    )

    # EMPLOYEE role: only own leaves
    if current_user.role == UserRole.EMPLOYEE and current_user.employee_id:
        query = query.where(LeaveRequest.employee_id == current_user.employee_id)
    elif employee_id:
        query = query.where(LeaveRequest.employee_id == employee_id)

    if status_filter:
        try:
            query = query.where(LeaveRequest.status == LeaveRequestStatus(status_filter))
        except ValueError:
            pass

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    requests = result.scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "employee_name": r.employee.full_name if r.employee else None,
                "employee_code": r.employee.employee_id if r.employee else None,
                "leave_type": r.leave_type.name if r.leave_type else None,
                "leave_code": r.leave_type.code if r.leave_type else None,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "days_count": r.days_count,
                "status": r.status.value,
                "reason": r.reason,
                "applied_at": r.applied_at,
                "review_comment": r.review_comment,
            }
            for r in requests
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/leaves", response_model=dict, status_code=status.HTTP_201_CREATED)
async def apply_leave(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Apply for leave."""
    from datetime import date as dt_date

    start_date = dt_date.fromisoformat(data["start_date"])
    end_date = dt_date.fromisoformat(data["end_date"])

    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date cannot be before start date.")

    # Calculate days (simple: end - start + 1, weekends not excluded automatically)
    days = (end_date - start_date).days + 1

    # Determine employee
    if current_user.role == UserRole.EMPLOYEE and current_user.employee_id:
        emp_id = current_user.employee_id
    else:
        emp_id = data.get("employee_id")
        if not emp_id:
            raise HTTPException(status_code=400, detail="employee_id is required.")

    # Check for overlapping leave requests for the same employee
    existing_overlap = await db.execute(
        select(LeaveRequest).where(
            LeaveRequest.employee_id == emp_id,
            LeaveRequest.status != LeaveRequestStatus.REJECTED,
            LeaveRequest.start_date <= end_date,
            LeaveRequest.end_date >= start_date,
        )
    )
    if existing_overlap.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Employee already has an active or pending leave request overlapping with this date range."
        )

    leave_request = LeaveRequest(
        employee_id=emp_id,
        leave_type_id=data["leave_type_id"],
        start_date=start_date,
        end_date=end_date,
        days_count=days,
        reason=data.get("reason"),
        status=LeaveRequestStatus.PENDING,
    )
    db.add(leave_request)
    await db.flush()
    await log_audit(db, current_user.id, "CREATE", "LeaveRequest", str(leave_request.id),
                    f"Leave request applied for employee {emp_id}: {start_date} to {end_date}")
    await db.commit()
    return {"id": leave_request.id, "status": leave_request.status.value, "days": days}


@router.put("/leaves/{leave_id}/approve", response_model=dict)
async def approve_leave(
    leave_id: int,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN, UserRole.DEPT_MANAGER))],
):
    result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == leave_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if req.status != LeaveRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Leave is already {req.status.value}.")

    req.status = LeaveRequestStatus.APPROVED
    req.reviewed_by_id = current_user.id
    req.review_comment = data.get("comment")
    req.reviewed_at = datetime.now(timezone.utc)

    await log_audit(db, current_user.id, "APPROVE", "LeaveRequest", str(leave_id),
                    f"Approved leave request {leave_id}")
    await db.commit()
    return {"message": "Leave approved", "leave_id": leave_id}


@router.put("/leaves/{leave_id}/reject", response_model=dict)
async def reject_leave(
    leave_id: int,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == leave_id))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Leave request not found")
    if req.status != LeaveRequestStatus.PENDING:
        raise HTTPException(status_code=400, detail=f"Leave is already {req.status.value}.")

    req.status = LeaveRequestStatus.REJECTED
    req.reviewed_by_id = current_user.id
    req.review_comment = data.get("comment")
    req.reviewed_at = datetime.now(timezone.utc)
    await log_audit(db, current_user.id, "REJECT", "LeaveRequest", str(leave_id),
                    f"Rejected leave request {leave_id}")
    await db.commit()
    return {"message": "Leave rejected", "leave_id": leave_id}


@router.get("/leaves/balances", response_model=dict)
async def leave_balances(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    employee_id: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
):
    """Get leave balances for employees."""
    from datetime import date as dt_date
    if not year:
        year = dt_date.today().year

    query = select(LeaveBalance).options(
        selectinload(LeaveBalance.employee),
        selectinload(LeaveBalance.leave_type),
    ).where(LeaveBalance.year == year)

    if current_user.role == UserRole.EMPLOYEE and current_user.employee_id:
        query = query.where(LeaveBalance.employee_id == current_user.employee_id)
    elif employee_id:
        query = query.where(LeaveBalance.employee_id == employee_id)

    result = await db.execute(query)
    balances = result.scalars().all()

    return {
        "items": [
            {
                "id": b.id,
                "employee_id": b.employee_id,
                "employee_name": b.employee.full_name if b.employee else None,
                "leave_type_id": b.leave_type_id,
                "leave_type_name": b.leave_type.name if b.leave_type else None,
                "leave_type_code": b.leave_type.code if b.leave_type else None,
                "year": b.year,
                "allocated_days": b.allocated_days,
                "used_days": b.used_days,
                "remaining_days": b.remaining_days,
            }
            for b in balances
        ],
        "total": len(balances),
    }
