"""
SPT Hospital HRMS — Dashboard API Endpoints
Returns real data from the database for the frontend dashboard.
"""
from datetime import date, timedelta
from typing import Annotated
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.employee import Employee
from app.models.attendance import Attendance, AttendanceStatus
from app.models.audit import AuditLog
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=dict)
async def get_dashboard_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Get KPI stats for the dashboard. All data is live from the database."""
    today = date.today()
    current_month = today.month
    current_year = today.year

    # Total active employees
    total_employees_result = await db.execute(
        select(func.count(Employee.id)).where(Employee.is_active == True)
    )
    total_employees = total_employees_result.scalar() or 0

    # Today's attendance stats (active employees only)
    today_att_result = await db.execute(
        select(Attendance.status, func.count(Attendance.id))
        .join(Attendance.employee)
        .where(Attendance.attendance_date == today, Employee.is_active == True)
        .group_by(Attendance.status)
    )
    today_stats = {row[0]: row[1] for row in today_att_result.all()}

    present_today = (
        (today_stats.get(AttendanceStatus.PRESENT) or 0) +
        (today_stats.get(AttendanceStatus.PRESENT_OVERNIGHT) or 0)
    )
    absent_today = today_stats.get(AttendanceStatus.ABSENT) or 0
    incomplete_today = today_stats.get(AttendanceStatus.PRESENT_INCOMPLETE) or 0

    # On leave today: check BOTH attendance records with LEAVE status
    # AND approved leave requests whose date range covers today
    on_leave_from_attendance = today_stats.get(AttendanceStatus.LEAVE) or 0

    from app.models.leave import LeaveRequest, LeaveRequestStatus
    leave_count_result = await db.execute(
        select(func.count(func.distinct(LeaveRequest.employee_id)))
        .where(
            LeaveRequest.status == LeaveRequestStatus.APPROVED,
            LeaveRequest.start_date <= today,
            LeaveRequest.end_date >= today,
        )
    )
    on_leave_from_requests = leave_count_result.scalar() or 0

    # Use the higher of the two to avoid double-counting
    on_leave_today = max(on_leave_from_attendance, on_leave_from_requests)

    # Late employees today
    late_result = await db.execute(
        select(func.count(Attendance.id))
        .where(Attendance.attendance_date == today, Attendance.is_late == True)
    )
    late_today = late_result.scalar() or 0

    # OT hours today
    ot_result = await db.execute(
        select(func.sum(Attendance.ot_minutes))
        .where(Attendance.attendance_date == today)
    )
    ot_minutes_today = ot_result.scalar() or 0
    ot_hours_today = round(ot_minutes_today / 60, 1)

    # Current month payroll total
    payroll_result = await db.execute(
        select(func.sum(PayrollRecord.net_salary))
        .join(PayrollPeriod)
        .where(
            PayrollPeriod.year == current_year,
            PayrollPeriod.month == current_month,
        )
    )
    monthly_payroll = payroll_result.scalar() or 0

    return {
        "total_employees": total_employees,
        "present_today": present_today,
        "absent_today": absent_today,
        "incomplete_today": incomplete_today,
        "late_today": late_today,
        "on_leave_today": on_leave_today,
        "ot_hours_today": ot_hours_today,
        "monthly_payroll": float(monthly_payroll),
        "as_of": today.isoformat(),
    }


@router.get("/attendance-trend", response_model=dict)
async def attendance_trend(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    days: int = 30,
):
    """Attendance trend for the last N days."""
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    result = await db.execute(
        select(
            Attendance.attendance_date,
            Attendance.status,
            func.count(Attendance.id).label("count"),
        )
        .where(
            Attendance.attendance_date >= start_date,
            Attendance.attendance_date <= end_date,
        )
        .group_by(Attendance.attendance_date, Attendance.status)
        .order_by(Attendance.attendance_date)
    )
    rows = result.all()

    # Build a dict: date -> {present, absent, incomplete}
    trend: dict[str, dict] = {}
    for row in rows:
        d = row.attendance_date.isoformat()
        if d not in trend:
            trend[d] = {"date": d, "present": 0, "absent": 0, "incomplete": 0}
        status = row.status
        if status in (AttendanceStatus.PRESENT, AttendanceStatus.PRESENT_OVERNIGHT):
            trend[d]["present"] += row.count
        elif status == AttendanceStatus.ABSENT:
            trend[d]["absent"] += row.count
        elif status == AttendanceStatus.PRESENT_INCOMPLETE:
            trend[d]["incomplete"] += row.count

    return {"data": list(trend.values()), "start_date": start_date.isoformat(), "end_date": end_date.isoformat()}


@router.get("/dept-attendance", response_model=dict)
async def dept_attendance(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Department-wise attendance for current month."""
    today = date.today()
    from app.models.department import Department

    result = await db.execute(
        select(
            Department.name,
            Attendance.status,
            func.count(Attendance.id).label("count"),
        )
        .join(Department, Attendance.department_id == Department.id)
        .where(
            extract("year", Attendance.attendance_date) == today.year,
            extract("month", Attendance.attendance_date) == today.month,
        )
        .group_by(Department.name, Attendance.status)
    )
    rows = result.all()

    dept_data: dict[str, dict] = {}
    for row in rows:
        dept = row.name
        if dept not in dept_data:
            dept_data[dept] = {"department": dept, "present": 0, "absent": 0}
        if row.status in (AttendanceStatus.PRESENT, AttendanceStatus.PRESENT_OVERNIGHT):
            dept_data[dept]["present"] += row.count
        elif row.status == AttendanceStatus.ABSENT:
            dept_data[dept]["absent"] += row.count

    return {"data": list(dept_data.values())}


@router.get("/ot-by-dept", response_model=dict)
async def ot_by_dept(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """OT hours by department for current month."""
    today = date.today()
    from app.models.department import Department

    result = await db.execute(
        select(
            Department.name,
            func.sum(Attendance.ot_minutes).label("total_ot_minutes"),
        )
        .join(Department, Attendance.department_id == Department.id)
        .where(
            extract("year", Attendance.attendance_date) == today.year,
            extract("month", Attendance.attendance_date) == today.month,
            Attendance.ot_minutes > 0,
        )
        .group_by(Department.name)
        .order_by(func.sum(Attendance.ot_minutes).desc())
    )
    rows = result.all()

    return {
        "data": [
            {"department": row.name, "ot_hours": round((row.total_ot_minutes or 0) / 60, 1)}
            for row in rows
        ]
    }


@router.get("/recent-activity", response_model=dict)
async def recent_activity(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    limit: int = 20,
):
    """Recent audit log entries for the dashboard activity feed."""
    from app.models.user import User
    result = await db.execute(
        select(AuditLog, User.full_name.label("user_name"))
        .outerjoin(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    rows = result.all()

    return {
        "items": [
            {
                "id": row.AuditLog.id,
                "action": row.AuditLog.action,
                "entity_type": row.AuditLog.entity_type,
                "description": row.AuditLog.description,
                "user_name": row.user_name or "System",
                "created_at": row.AuditLog.created_at,
            }
            for row in rows
        ]
    }
