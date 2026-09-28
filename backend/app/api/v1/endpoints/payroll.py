"""
SPT Hospital HRMS — Payroll API Endpoints
"""
from datetime import datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.models.user import UserRole
from app.models.payroll import (
    PayrollPeriod, PayrollRecord, PayrollItem,
    SalaryComponent, SalaryStructure, SalaryStructureItem,
    SalarySlip, PayrollStatus, ComponentType,
)
from app.models.employee import Employee
from app.payroll.engine import PayrollEngine
from app.schemas.payroll import PayrollRecordUpdate
from app.utils.audit import log_audit

router = APIRouter(tags=["Payroll"])


# ─── Payroll Periods ───────────────────────────────────────────────────────────
@router.post("/payroll/periods", response_model=dict)
async def create_payroll_period(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """Create a new payroll period."""
    year = data["year"]
    month = data["month"]

    existing = await db.execute(
        select(PayrollPeriod).where(PayrollPeriod.year == year, PayrollPeriod.month == month)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Payroll period for {year}-{month:02d} already exists.")

    import calendar
    calendar_days = calendar.monthrange(year, month)[1]
    working_days = data.get("working_days") if data.get("working_days") and data.get("working_days") != 26 else calendar_days
    period_name = f"{calendar.month_name[month]} {year}"

    period = PayrollPeriod(
        year=year,
        month=month,
        period_name=period_name,
        working_days=working_days,
        status=PayrollStatus.DRAFT,
        created_by_id=current_user.id,
    )
    db.add(period)
    await db.flush()
    await log_audit(db, current_user.id, "CREATE", "PayrollPeriod", str(period.id),
                    f"Created payroll period: {period_name}")
    await db.commit()
    await db.refresh(period)
    return {"id": period.id, "period_name": period.period_name, "year": period.year,
            "month": period.month, "working_days": period.working_days, "status": period.status.value}


@router.get("/payroll/periods/lookup", response_model=dict)
async def lookup_payroll_period(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    year: int = Query(..., ge=2020, le=2050),
    month: int = Query(..., ge=1, le=12),
):
    """Lookup a payroll period by year and month."""
    result = await db.execute(
        select(PayrollPeriod).where(PayrollPeriod.year == year, PayrollPeriod.month == month)
    )
    period = result.scalar_one_or_none()
    if not period:
        return {"period": None}
    return {
        "period": {
            "id": period.id,
            "period_name": period.period_name,
            "year": period.year,
            "month": period.month,
            "working_days": period.working_days,
            "status": period.status.value,
        }
    }


@router.get("/payroll/periods", response_model=dict)
async def list_payroll_periods(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    year: Annotated[Optional[int], Query(ge=2020, le=2050)] = None,
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
):
    query = select(PayrollPeriod)
    if year is not None and isinstance(year, int):
        query = query.where(PayrollPeriod.year == year)
    if month is not None and isinstance(month, int):
        query = query.where(PayrollPeriod.month == month)
    query = query.order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc())
    result = await db.execute(query)
    periods = result.scalars().all()
    return {
        "items": [
            {"id": p.id, "period_name": p.period_name, "year": p.year, "month": p.month,
             "working_days": p.working_days, "status": p.status.value}
            for p in periods
        ]
    }


@router.post("/payroll/periods/calculate", response_model=dict)
async def calculate_payroll_by_month(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """
    Idempotently get-or-create the period for year+month, then run calculation.
    Rejects with 409 if the period is already FINALIZED.
    """
    year = data.get("year")
    month = data.get("month")
    if not year or not month or not (1 <= month <= 12) or not (2020 <= year <= 2050):
        raise HTTPException(status_code=400, detail="Valid year (2020-2050) and month (1-12) are required.")

    import calendar
    result = await db.execute(
        select(PayrollPeriod).where(PayrollPeriod.year == year, PayrollPeriod.month == month)
    )
    period = result.scalar_one_or_none()

    if period:
        if period.status == PayrollStatus.FINALIZED:
            raise HTTPException(
                status_code=409,
                detail=f"Payroll period for {period.period_name} is finalized. Reopen the period before recalculating."
            )
    else:
        calendar_days = calendar.monthrange(year, month)[1]
        working_days = data.get("working_days") or calendar_days
        period_name = f"{calendar.month_name[month]} {year}"
        period = PayrollPeriod(
            year=year,
            month=month,
            period_name=period_name,
            working_days=working_days,
            status=PayrollStatus.DRAFT,
            created_by_id=current_user.id,
        )
        db.add(period)
        await db.flush()
        await log_audit(db, current_user.id, "CREATE", "PayrollPeriod", str(period.id),
                        f"Created payroll period: {period_name}")

    engine = PayrollEngine(db)
    stats = await engine.calculate_all_employees(period, period.working_days, current_user.id)

    period.status = PayrollStatus.UNDER_REVIEW
    await log_audit(db, current_user.id, "CALCULATE", "PayrollPeriod", str(period.id),
                    f"Calculated payroll for {period.period_name}: {stats['calculated']} employees")
    await db.commit()
    await db.refresh(period)

    return {
        "message": f"Payroll calculated for {period.period_name}",
        "period": {
            "id": period.id,
            "period_name": period.period_name,
            "year": period.year,
            "month": period.month,
            "working_days": period.working_days,
            "status": period.status.value,
        },
        **stats,
    }


@router.post("/payroll/periods/{period_id}/calculate", response_model=dict)
async def calculate_payroll(
    period_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """Run payroll calculation for all employees in a period."""
    result = await db.execute(select(PayrollPeriod).where(PayrollPeriod.id == period_id))
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")

    if period.status == PayrollStatus.FINALIZED:
        raise HTTPException(status_code=409, detail=f"Cannot recalculate finalized payroll for {period.period_name}.")

    engine = PayrollEngine(db)
    stats = await engine.calculate_all_employees(period, period.working_days, current_user.id)

    period.status = PayrollStatus.UNDER_REVIEW
    await log_audit(db, current_user.id, "CALCULATE", "PayrollPeriod", str(period.id),
                    f"Calculated payroll for {period.period_name}: {stats['calculated']} employees")
    await db.commit()
    return {"message": f"Payroll calculated for {period.period_name}", **stats}


@router.delete("/payroll/periods/{period_id}", response_model=dict)
async def delete_payroll_period(
    period_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """Delete a draft payroll period."""
    result = await db.execute(select(PayrollPeriod).where(PayrollPeriod.id == period_id))
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    if period.status == PayrollStatus.FINALIZED:
        raise HTTPException(status_code=400, detail="Cannot delete a finalized payroll period")

    name = period.period_name
    await db.delete(period)
    await db.commit()
    await log_audit(db, current_user.id, "DELETE", "PayrollPeriod", str(period_id), f"Deleted payroll period {name}")
    return {"status": "success", "message": f"Payroll period {name} deleted successfully"}


@router.get("/payroll/periods/{period_id}/records", response_model=dict)
async def get_payroll_records(
    period_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    department_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """Get all payroll records for a period."""
    p_res = await db.execute(select(PayrollPeriod).where(PayrollPeriod.id == period_id))
    period = p_res.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")

    query = (
        select(PayrollRecord)
        .where(PayrollRecord.period_id == period_id)
        .options(selectinload(PayrollRecord.employee).selectinload(Employee.department))
        .order_by(PayrollRecord.employee_id)
    )
    if period.status != PayrollStatus.FINALIZED:
        query = query.join(Employee, PayrollRecord.employee_id == Employee.id).where(Employee.is_active == True)
        if department_id:
            query = query.where(Employee.department_id == department_id)
    elif department_id:
        query = query.join(Employee, PayrollRecord.employee_id == Employee.id).where(Employee.department_id == department_id)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()
    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    records = result.scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "payroll_period_id": r.period_id,
                "employee_id": r.employee_id,
                "employee_code": r.employee.employee_id if r.employee else None,
                "biometric_code": r.employee.biometric_code if r.employee else None,
                "employee_name": r.employee.full_name if r.employee else None,
                "department": r.employee.department.name if r.employee and r.employee.department else None,
                "basic_salary": round(r.basic_salary, 2),
                "gross_salary": round(r.gross_salary if r.gross_salary is not None else (r.salary_part + r.collection), 2),
                "present_days": r.present_days,
                "absent_days": r.absent_days,
                "half_days": r.half_days,
                "leave_days": r.leave_days,
                "paid_leave_days": r.paid_leave_days,
                "off_duty_days": r.off_duty_days,
                "qualifying_late_days": r.qualifying_late_days or 0,
                "loss_of_pay_days": r.lop_days if r.lop_days is not None else (r.loss_of_pay_days or 0.0),
                "lop_days": r.lop_days if r.lop_days is not None else (r.loss_of_pay_days or 0.0),
                "payable_days": r.payable_days,
                "salary_part": r.salary_part,
                "collection": r.collection,
                "lifetime_collection": r.lifetime_collection,
                "lop_deduction": round(r.lop_deduction or 0.0, 2),
                "security_fund_deduction": round(r.security_fund_deduction or 0.0, 2),
                "total_deductions": round(r.total_deductions if r.total_deductions is not None else 0.0, 2),
                "deductions": round(r.total_deductions if r.total_deductions is not None else 0.0, 2),
                "total_salary": round(r.net_salary, 2),
                "net_salary": round(r.net_salary, 2),
                "is_manual_override": r.is_manual_override,
                "status": r.status.value,
            }
            for r in records
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.put("/payroll/records/{record_id}", response_model=dict)
async def update_payroll_record(
    record_id: int,
    data: PayrollRecordUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """Manually override payroll inputs for a single employee record."""
    from sqlalchemy import delete
    from app.models.payroll import PayrollItem

    result = await db.execute(
        select(PayrollRecord)
        .options(
            selectinload(PayrollRecord.period),
            selectinload(PayrollRecord.employee).selectinload(Employee.shift),
        )
        .where(PayrollRecord.id == record_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Payroll record not found")

    if rec.period and rec.period.status == PayrollStatus.FINALIZED:
        raise HTTPException(status_code=400, detail="Cannot edit finalized payroll period")

    override_inputs = {}
    if data.present_days is not None:
        override_inputs["present_days"] = data.present_days
    if data.half_days is not None:
        override_inputs["half_days"] = data.half_days
    if data.leave_days is not None:
        override_inputs["leave_days"] = data.leave_days
    if data.off_duty_days is not None:
        override_inputs["off_duty_days"] = data.off_duty_days
    if data.qualifying_late_days is not None:
        override_inputs["qualifying_late_days"] = data.qualifying_late_days
    if data.lop_days is not None:
        override_inputs["lop_days"] = data.lop_days
    elif data.loss_of_pay_days is not None:
        override_inputs["loss_of_pay_days"] = data.loss_of_pay_days
    """
    Allow HR to manually override an employee's inputs for a payroll period.
    Recalculates payable_days, salary_part, and total_salary automatically.
    """
    result = await db.execute(select(PayrollRecord).where(PayrollRecord.id == record_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Payroll record not found")

    p_res = await db.execute(select(PayrollPeriod).where(PayrollPeriod.id == rec.period_id))
    period = p_res.scalar_one_or_none()
    if period and period.status == PayrollStatus.FINALIZED:
        raise HTTPException(status_code=400, detail="Cannot edit records in a finalized payroll period.")

    engine = PayrollEngine(db)
    override_dict = {
        "present_days": data.present_days,
        "half_days": data.half_days,
        "leave_days": data.leave_days,
        "off_duty_days": data.off_duty_days,
        "lop_days": data.lop_days if data.lop_days is not None else 0.0,
        "collection": data.collection if data.collection is not None else 0.0,
    }

    calc_res = await engine.calculate_employee_payroll(
        employee_id=rec.employee_id,
        year=period.year if period else 2026,
        month=period.month if period else 8,
        period=period,
        override_inputs=override_dict,
    )

    if not calc_res:
        raise HTTPException(status_code=400, detail="Failed to recalculate payroll record.")

    updated_rec, updated_items = calc_res

    # Copy fields
    for field in [
        "present_days", "half_days", "leave_days", "paid_leave_days",
        "off_duty_days", "payable_days", "salary_part", "collection",
        "lifetime_collection", "lop_days", "lop_deduction", "security_fund_deduction",
        "total_deductions", "carried_forward_deductions", "gross_salary",
        "net_salary", "is_manual_override", "status"
    ]:
        setattr(rec, field, getattr(updated_rec, field))

    # Replace items
    from sqlalchemy import delete
    from app.models.payroll import PayrollItem
    await db.execute(delete(PayrollItem).where(PayrollItem.payroll_record_id == rec.id))
    for name, comp_type, amount, comp_id in updated_items:
        item = PayrollItem(
            payroll_record_id=rec.id,
            component_id=comp_id,
            component_name=name,
            component_type=comp_type,
            amount=round(amount, 2),
        )
        db.add(item)

    await db.commit()
    await db.refresh(rec)

    return {
        "id": rec.id,
        "payable_days": rec.payable_days,
        "salary_part": rec.salary_part,
        "collection": rec.collection,
        "lifetime_collection": rec.lifetime_collection,
        "lop_days": rec.lop_days,
        "lop_deduction": rec.lop_deduction,
        "security_fund_deduction": rec.security_fund_deduction,
        "total_deductions": rec.total_deductions,
        "carried_forward_deductions": rec.carried_forward_deductions,
        "gross_salary": rec.gross_salary,
        "total_salary": rec.net_salary,
        "net_salary": rec.net_salary,
        "is_manual_override": rec.is_manual_override,
    }


@router.post("/payroll/periods/{period_id}/finalize", response_model=dict)
async def finalize_payroll(
    period_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """Finalize a payroll period. Locks all records and deposits savings fund deductions."""
    from app.models.employee import SecurityFundTransaction
    result = await db.execute(select(PayrollPeriod).where(PayrollPeriod.id == period_id))
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    if period.status == PayrollStatus.FINALIZED:
        raise HTTPException(status_code=400, detail="Payroll already finalized.")

    # Clean up any inactive employee records in this period before locking
    from app.models.payroll import PayrollItem
    inactive_res = await db.execute(
        select(PayrollRecord.id)
        .join(Employee, PayrollRecord.employee_id == Employee.id)
        .where(
            PayrollRecord.period_id == period_id,
            Employee.is_active == False,
        )
    )
    inactive_ids = inactive_res.scalars().all()
    if inactive_ids:
        await db.execute(delete(PayrollItem).where(PayrollItem.payroll_record_id.in_(inactive_ids)))
        await db.execute(delete(PayrollRecord).where(PayrollRecord.id.in_(inactive_ids)))
        await db.flush()

    # 1. Check for unverified salaries (active employees only)
    records_result = await db.execute(
        select(PayrollRecord)
        .where(PayrollRecord.period_id == period_id)
        .options(selectinload(PayrollRecord.employee), selectinload(PayrollRecord.items))
    )
    records = records_result.scalars().all()

    unverified_staff = []
    for r in records:
        emp = r.employee
        if emp and emp.is_active and (not emp.salary_verified or emp.basic_salary is None or float(emp.basic_salary) <= 0):
            unverified_staff.append({
                "id": emp.id,
                "employee_id": emp.employee_id,
                "name": emp.full_name,
                "biometric_code": emp.biometric_code,
                "basic_salary": float(emp.basic_salary or 0.0),
            })

    if unverified_staff:
        names_summary = ", ".join(f"{e['name']} ({e['employee_id']})" for e in unverified_staff)
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Cannot finalize payroll period: {len(unverified_staff)} employees have unverified salaries ({names_summary}). Please configure verified salaries before finalizing.",
                "unverified_employees": unverified_staff,
            }
        )

    from app.models.attendance import AttendanceException, ExceptionReviewStatus
    from sqlalchemy import extract

    # Check for ANY pending exceptions in this period's month
    pending_exc_result = await db.execute(
        select(AttendanceException)
        .options(selectinload(AttendanceException.employee))
        .where(
            AttendanceException.review_status == ExceptionReviewStatus.PENDING,
            extract("year", AttendanceException.exception_date) == period.year,
            extract("month", AttendanceException.exception_date) == period.month,
        )
    )
    pending_exceptions = pending_exc_result.scalars().all()
    if pending_exceptions:
        affected_emps = {}
        for pe in pending_exceptions:
            emp_name = pe.employee.full_name if pe.employee else f"Employee #{pe.employee_id}"
            affected_emps[emp_name] = affected_emps.get(emp_name, 0) + 1

        summary_str = ", ".join(f"{name} ({cnt} pending)" for name, cnt in affected_emps.items())
        raise HTTPException(
            status_code=400,
            detail=f"Cannot finalize: {len(pending_exceptions)} unreviewed attendance exceptions remain for {period.period_name} ({summary_str}). Please review or dismiss them first."
        )

    period.status = PayrollStatus.FINALIZED
    period.finalized_by_id = current_user.id
    period.finalized_at = datetime.now(timezone.utc)

    # 2. Update all records to FINALIZED & deposit savings fund deductions
    note_str = f"Payroll deduction for {period.period_name}"
    for record in records:
        record.status = PayrollStatus.FINALIZED

        # Find any Staff Security Fund deduction item
        fund_amount = 0.0
        for item in record.items:
            if item.component_name in ["Staff Security Fund", "Staff Savings Fund"] and item.amount > 0:
                fund_amount = float(item.amount)
                break

        if fund_amount > 0:
            # Check if already deposited for this employee and period
            existing_tx = await db.execute(
                select(SecurityFundTransaction).where(
                    SecurityFundTransaction.employee_id == record.employee_id,
                    SecurityFundTransaction.transaction_type == "DEPOSIT",
                    SecurityFundTransaction.notes == note_str,
                )
            )
            if not existing_tx.scalar_one_or_none():
                tx = SecurityFundTransaction(
                    employee_id=record.employee_id,
                    transaction_type="DEPOSIT",
                    amount=fund_amount,
                    notes=note_str,
                    created_by_id=current_user.id,
                )
                db.add(tx)

    await log_audit(db, current_user.id, "FINALIZE", "PayrollPeriod", str(period.id),
                    f"Finalized payroll for {period.period_name}")
    await db.commit()
    return {
        "message": f"Payroll for {period.period_name} finalized successfully.",
        "status": "FINALIZED",
    }


@router.post("/payroll/periods/{period_id}/reopen", response_model=dict)
async def reopen_payroll(
    period_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """Reopen a finalized payroll period (SUPER_ADMIN or HR_ADMIN)."""
    result = await db.execute(select(PayrollPeriod).where(PayrollPeriod.id == period_id))
    period = result.scalar_one_or_none()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")

    period.status = PayrollStatus.DRAFT
    period.finalized_by_id = None
    period.finalized_at = None

    # Update associated records to DRAFT
    records_result = await db.execute(
        select(PayrollRecord).where(PayrollRecord.period_id == period_id)
    )
    for record in records_result.scalars().all():
        record.status = PayrollStatus.DRAFT

    await log_audit(db, current_user.id, "REOPEN", "PayrollPeriod", str(period.id),
                    f"Reopened payroll for {period.period_name}")
    await db.commit()
    return {"message": f"Payroll for {period.period_name} reopened."}


@router.get("/payroll/records/{record_id}", response_model=dict)
async def get_payroll_record(
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Get a single payroll record with itemized breakdown."""
    result = await db.execute(
        select(PayrollRecord)
        .where(PayrollRecord.id == record_id)
        .options(
            selectinload(PayrollRecord.items),
            selectinload(PayrollRecord.employee).selectinload(Employee.department),
            selectinload(PayrollRecord.period),
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")

    return {
        "id": record.id,
        "employee": {
            "id": record.employee.id,
            "employee_id": record.employee.employee_id,
            "full_name": record.employee.full_name,
            "department": record.employee.department.name if record.employee.department else None,
        } if record.employee else None,
        "period": {
            "id": record.period.id,
            "period_name": record.period.period_name,
            "year": record.period.year,
            "month": record.period.month,
        } if record.period else None,
        "attendance": {
            "working_days": record.total_working_days,
            "present": record.present_days,
            "absent": record.absent_days,
            "half_days": record.half_days,
            "leave": record.leave_days,
            "paid_leave": record.paid_leave_days,
            "off_duty_days": record.off_duty_days,
            "qualifying_late_days": record.qualifying_late_days or 0,
            "loss_of_pay": record.lop_days if record.lop_days is not None else (record.loss_of_pay_days or 0.0),
            "lop_days": record.lop_days if record.lop_days is not None else (record.loss_of_pay_days or 0.0),
            "payable_days": record.payable_days,
            "salary_part": record.salary_part,
            "collection": record.collection,
            "ot_hours": record.ot_hours,
        },
        "earnings": [
            {"name": i.component_name, "amount": round(i.amount, 2)}
            for i in record.items if i.component_type == ComponentType.EARNING
        ],
        "deductions": [
            {"name": i.component_name, "amount": round(i.amount, 2)}
            for i in record.items if i.component_type == ComponentType.DEDUCTION
        ],
        "gross_salary": round(record.gross_salary, 2),
        "total_deductions": round(record.total_deductions, 2),
        "net_salary": round(record.net_salary, 2),
        "status": record.status.value,
    }


@router.get("/payroll/records/{record_id}/lateness-breakdown", response_model=dict)
async def get_record_lateness_breakdown(
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """
    Get detailed breakdown of all qualifying late arrivals for a payroll record.
    Explains exactly which dates and minutes late produced the LOP days.
    """
    from app.models.attendance import Attendance
    from app.models.audit import SystemSetting
    from sqlalchemy import extract

    result = await db.execute(
        select(PayrollRecord)
        .where(PayrollRecord.id == record_id)
        .options(
            selectinload(PayrollRecord.period),
            selectinload(PayrollRecord.employee).selectinload(Employee.shift),
        )
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Payroll record not found")

    year = rec.period.year if rec.period else 2026
    month = rec.period.month if rec.period else 8

    # Grace period
    grace_period = 5
    try:
        s_res = await db.execute(select(SystemSetting).where(SystemSetting.key == "attendance_grace_period"))
        s = s_res.scalar_one_or_none()
        if s and s.value:
            grace_period = int(s.value)
    except Exception:
        pass

    att_res = await db.execute(
        select(Attendance)
        .where(
            Attendance.employee_id == rec.employee_id,
            extract("year", Attendance.attendance_date) == year,
            extract("month", Attendance.attendance_date) == month,
            Attendance.is_late == True,
        )
        .order_by(Attendance.attendance_date)
    )
    late_records = att_res.scalars().all()

    # Determine employee's shift grace period if configured
    emp_shift_grace = grace_period
    if rec.employee and rec.employee.shift and rec.employee.shift.grace_period_minutes is not None:
        emp_shift_grace = rec.employee.shift.grace_period_minutes

    items = []
    for a in late_records:
        late_min = getattr(a, "late_minutes", 0) or 0
        in_t = str(a.source_in_time) if a.source_in_time else (a.check_in_datetime.strftime("%H:%M") if a.check_in_datetime else "—")
        shift = a.source_shift_code or "—"
        items.append({
            "date": a.attendance_date.strftime("%d %b %Y (%a)"),
            "in_time": in_t,
            "shift": shift,
            "late_minutes": late_min,
            "grace_minutes": emp_shift_grace,
            "excess_minutes": max(0, late_min - emp_shift_grace),
            "status": a.status.value,
        })

    return {
        "employee_id": rec.employee_id,
        "employee_name": rec.employee.full_name if rec.employee else "Staff",
        "grace_minutes": emp_shift_grace,
        "qualifying_late_days": rec.qualifying_late_days or len(items),
        "lop_days": rec.lop_days or rec.loss_of_pay_days or 0.0,
        "lop_deduction": rec.lop_deduction or 0.0,
        "late_arrivals": items,
    }


# ─── Salary Components (configurable) ─────────────────────────────────────────
@router.get("/salary-components", response_model=dict)
async def list_salary_components(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(select(SalaryComponent).where(SalaryComponent.is_active == True))
    components = result.scalars().all()
    return {
        "items": [
            {
                "id": c.id, "name": c.name, "code": c.code,
                "component_type": c.component_type.value,
                "is_percentage": c.is_percentage,
                "default_value": c.default_value,
                "is_taxable": c.is_taxable,
            }
            for c in components
        ]
    }


# ─── Salary Structure ──────────────────────────────────────────────────────────
@router.get("/salary-structures/{employee_id}", response_model=dict)
async def get_salary_structure(
    employee_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    result = await db.execute(
        select(SalaryStructure)
        .where(SalaryStructure.employee_id == employee_id)
        .options(selectinload(SalaryStructure.items).selectinload(SalaryStructureItem.component))
    )
    structure = result.scalar_one_or_none()
    if not structure:
        raise HTTPException(status_code=404, detail="No salary structure found for this employee.")

    return {
        "id": structure.id,
        "employee_id": structure.employee_id,
        "basic_salary": structure.basic_salary,
        "ot_rate_per_hour": structure.ot_rate_per_hour,
        "effective_from": structure.effective_from,
        "items": [
            {
                "id": item.id,
                "component_id": item.component_id,
                "component_name": item.component.name if item.component else None,
                "component_type": item.component.component_type.value if item.component else None,
                "amount": item.amount,
                "is_percentage": item.is_percentage,
            }
            for item in structure.items
        ],
    }


@router.post("/salary-structures", response_model=dict)
async def create_salary_structure(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """Create or replace salary structure for an employee."""
    from datetime import date as dt_date

    employee_id = data["employee_id"]

    # Deactivate existing structure
    existing_result = await db.execute(
        select(SalaryStructure).where(SalaryStructure.employee_id == employee_id)
    )
    for existing in existing_result.scalars().all():
        existing.is_active = False

    structure = SalaryStructure(
        employee_id=employee_id,
        basic_salary=data["basic_salary"],
        ot_rate_per_hour=data.get("ot_rate_per_hour", 0.0),
        effective_from=dt_date.fromisoformat(data.get("effective_from", dt_date.today().isoformat())),
    )
    db.add(structure)
    await db.flush()

    for item_data in data.get("items", []):
        item = SalaryStructureItem(
            salary_structure_id=structure.id,
            component_id=item_data["component_id"],
            amount=item_data["amount"],
            is_percentage=item_data.get("is_percentage", False),
        )
        db.add(item)

    await log_audit(db, current_user.id, "CREATE", "SalaryStructure", str(structure.id),
                    f"Created salary structure for employee {employee_id}")
    await db.commit()
    return {"id": structure.id, "message": "Salary structure created"}


@router.get("/salary-slips/{record_id}")
async def download_salary_slip(
    record_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Download or generate a PDF salary slip for a payroll record."""
    from app.services.salary_slip import generate_salary_slip
    import os

    result = await db.execute(
        select(PayrollRecord)
        .where(PayrollRecord.id == record_id)
        .options(selectinload(PayrollRecord.salary_slip))
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")

    # Check access (EMPLOYEE can only download their own slip)
    if current_user.role == UserRole.EMPLOYEE:
        if current_user.employee_id != record.employee_id:
            raise HTTPException(status_code=403, detail="Access denied")

    # Generate if not exists
    slip_path = None
    if record.salary_slip and os.path.exists(record.salary_slip.file_path):
        slip_path = record.salary_slip.file_path
    else:
        slip_path = await generate_salary_slip(record_id, db, current_user.id)

    if not slip_path or not os.path.exists(slip_path):
        raise HTTPException(status_code=500, detail="Failed to generate salary slip.")

    with open(slip_path, "rb") as f:
        content = f.read()

    filename = os.path.basename(slip_path)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
