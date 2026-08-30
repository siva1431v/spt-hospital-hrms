"""
SPT Hospital HRMS — Employee API Endpoints
"""
from typing import Annotated, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.models.user import UserRole
from app.models.employee import Employee
from app.models.department import Department, Designation
from app.models.shift import Shift
from app.schemas.employee import (
    EmployeeCreate, EmployeeUpdate, EmployeeResponse, EmployeeListResponse,
    SavingsFundTransactionCreate, SavingsFundTransactionResponse, BulkSetSavingsRequest
)
from app.utils.audit import log_audit
import json

router = APIRouter(prefix="/employees", tags=["Employees"])


def _build_employee_response(emp: Employee) -> dict:
    """Build a complete employee response dict including nested names."""
    return {
        "id": emp.id,
        "employee_id": emp.employee_id,
        "biometric_code": emp.biometric_code,
        "first_name": emp.first_name,
        "last_name": emp.last_name,
        "full_name": emp.full_name,
        "gender": emp.gender,
        "date_of_birth": emp.date_of_birth,
        "phone": emp.phone,
        "email": emp.email,
        "address": emp.address,
        "department_id": emp.department_id,
        "department_name": emp.department.name if emp.department else None,
        "designation_id": emp.designation_id,
        "designation_name": emp.designation.name if emp.designation else None,
        "shift_id": emp.shift_id,
        "shift_code": emp.shift.code if emp.shift else None,
        "shift_name": emp.shift.name if emp.shift else None,
        "joining_date": emp.joining_date or date(2026, 8, 1),
        "employment_type": emp.employment_type,
        "is_active": emp.is_active,
        "basic_salary": emp.basic_salary,
        "salary_verified": getattr(emp, "salary_verified", False),
        "security_fund_deduction": float(emp.security_fund_deduction) if emp.security_fund_deduction is not None else 0.0,
        "bank_name": emp.bank_name,
        "bank_account_number": emp.bank_account_number,
        "bank_ifsc": emp.bank_ifsc,
        "pan_number": emp.pan_number,
        "pf_number": emp.pf_number,
        "esi_number": emp.esi_number,
        "created_at": emp.created_at,
        "updated_at": emp.updated_at,
    }


@router.get("", response_model=dict)
async def list_employees(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    search: Optional[str] = Query(None),
    department_id: Optional[int] = Query(None),
    is_active: Optional[bool] = Query(None),
    employment_type: Optional[str] = Query(None),
):
    """List all employees with pagination and filters."""
    query = (
        select(Employee)
        .options(
            selectinload(Employee.department),
            selectinload(Employee.designation),
            selectinload(Employee.shift),
        )
    )

    # Apply filters
    if search:
        query = query.where(
            or_(
                Employee.full_name.ilike(f"%{search}%"),
                Employee.employee_id.ilike(f"%{search}%"),
                Employee.biometric_code.ilike(f"%{search}%"),
                Employee.email.ilike(f"%{search}%"),
            )
        )
    if department_id:
        query = query.where(Employee.department_id == department_id)
    if is_active is not None:
        query = query.where(Employee.is_active == is_active)
    if employment_type:
        query = query.where(Employee.employment_type == employment_type)

    # For DEPT_MANAGER: only show employees in their department
    if current_user.role == UserRole.DEPT_MANAGER and current_user.employee:
        query = query.where(Employee.department_id == current_user.employee.department_id)

    # Count total
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    # Paginate
    offset = (page - 1) * page_size
    query = query.order_by(Employee.full_name).offset(offset).limit(page_size)
    result = await db.execute(query)
    employees = result.scalars().all()

    return {
        "items": [_build_employee_response(emp) for emp in employees],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_employee(
    data: EmployeeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))
    ],
):
    """Create a new employee."""
    # Check if employee_id already exists
    existing = await db.execute(
        select(Employee).where(Employee.employee_id == data.employee_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail=f"Employee ID '{data.employee_id}' already exists.",
        )

    # Check biometric_code uniqueness
    if data.biometric_code:
        bio_check = await db.execute(
            select(Employee).where(Employee.biometric_code == data.biometric_code)
        )
        if bio_check.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail=f"Biometric code '{data.biometric_code}' is already assigned to another employee.",
            )

    full_name = f"{data.first_name} {data.last_name or ''}".strip()
    emp_dict = data.model_dump(exclude={"first_name", "last_name"})

    if data.security_fund_deduction is not None:
        fund_amt = round(float(data.security_fund_deduction), 2)
        if data.basic_salary is not None and float(data.basic_salary) > 0 and fund_amt > float(data.basic_salary):
            raise HTTPException(
                status_code=400,
                detail=f"Savings fund deduction (₹{fund_amt:,.2f}) cannot exceed basic salary (₹{float(data.basic_salary):,.2f}).",
            )
        emp_dict["security_fund_deduction"] = fund_amt
    else:
        emp_dict["security_fund_deduction"] = 0.0

    if data.basic_salary is not None and float(data.basic_salary) > 0:
        if data.salary_verified is None:
            emp_dict["salary_verified"] = True
        emp_dict["salary_source"] = "MANUAL"
    elif data.salary_verified is None:
        emp_dict["salary_verified"] = False

    employee = Employee(
        **emp_dict,
        first_name=data.first_name,
        last_name=data.last_name or "",
        full_name=full_name,
    )
    db.add(employee)
    await db.flush()
    await db.refresh(employee, ["department", "designation", "shift"])

    await log_audit(
        db, current_user.id, "CREATE", "Employee", str(employee.id),
        f"Created employee {employee.employee_id} - {employee.full_name}",
        new_value=json.dumps({"employee_id": employee.employee_id, "name": employee.full_name}, default=str),
    )
    await db.commit()
    await db.refresh(employee, ["department", "designation", "shift"])
    return _build_employee_response(employee)


@router.get("/name-collisions", response_model=dict)
async def get_employee_name_collisions(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """
    Find active employees who share identical or similar names across different biometric codes/IDs.
    Helps HR review and decide whether pairs represent a re-enrolled person or two different people.
    """
    import re
    result = await db.execute(
        select(Employee)
        .where(Employee.is_active == True)
        .options(selectinload(Employee.department), selectinload(Employee.shift))
        .order_by(Employee.id)
    )
    employees = result.scalars().all()

    # Group by normalized full name (alphanumeric only, lowercase)
    grouped: dict[str, list[Employee]] = {}
    for emp in employees:
        norm = re.sub(r"[^a-zA-Z0-9]", "", (emp.full_name or "").lower().strip())
        if not norm:
            continue
        grouped.setdefault(norm, []).append(emp)

    collisions = []
    for norm_name, emps in grouped.items():
        if len(emps) > 1:
            collisions.append({
                "normalized_name": norm_name,
                "count": len(emps),
                "employees": [
                    {
                        "id": e.id,
                        "employee_id": e.employee_id,
                        "biometric_code": e.biometric_code,
                        "full_name": e.full_name,
                        "department": e.department.name if e.department else None,
                        "shift": e.shift.code if e.shift else None,
                        "joining_date": str(e.joining_date) if e.joining_date else None,
                    }
                    for e in emps
                ],
            })

    return {
        "total_collisions": len(collisions),
        "collisions": collisions,
    }


@router.get("/{employee_id}", response_model=dict)
async def get_employee(
    employee_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Get a single employee by ID."""
    result = await db.execute(
        select(Employee)
        .where(Employee.id == employee_id)
        .options(
            selectinload(Employee.department),
            selectinload(Employee.designation),
            selectinload(Employee.shift),
        )
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # EMPLOYEE role can only see their own record
    if current_user.role == UserRole.EMPLOYEE and current_user.employee_id != employee_id:
        raise HTTPException(status_code=403, detail="Access denied")

    from app.models.payroll import PayrollItem, PayrollRecord
    from app.models.employee import SecurityFundTransaction

    res_tx = await db.execute(
        select(SecurityFundTransaction).where(SecurityFundTransaction.employee_id == employee_id)
    )
    txs = res_tx.scalars().all()
    if txs:
        total_deposits = sum(float(t.amount) for t in txs if t.transaction_type.upper() in ["DEPOSIT", "ADDITION", "DEDUCTION", "CREDIT"])
        total_withdrawals = sum(float(t.amount) for t in txs if t.transaction_type.upper() in ["WITHDRAWAL", "REFUND", "SETTLEMENT", "DEBIT"])
        accumulated_fund = max(0.0, total_deposits - total_withdrawals)
    else:
        res_fund = await db.execute(
            select(func.sum(PayrollItem.amount))
            .join(PayrollRecord, PayrollItem.payroll_record_id == PayrollRecord.id)
            .where(
                PayrollRecord.employee_id == employee_id,
                PayrollItem.component_name.in_(["Staff Savings Fund", "Staff Security Fund"]),
            )
        )
        accumulated_fund = float(res_fund.scalar() or 0.0)

    resp = _build_employee_response(emp)
    resp["accumulated_security_fund"] = round(accumulated_fund, 2)
    return resp


@router.get("/{employee_id}/savings-fund/transactions", response_model=dict)
async def list_savings_fund_transactions(
    employee_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """List all savings fund transactions and running balance for an employee."""
    from app.models.employee import SecurityFundTransaction
    from app.models.payroll import PayrollItem, PayrollRecord

    emp_res = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = emp_res.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    result = await db.execute(
        select(SecurityFundTransaction)
        .where(SecurityFundTransaction.employee_id == employee_id)
        .order_by(SecurityFundTransaction.created_at.desc())
    )
    txs = result.scalars().all()

    # Calculate running balance
    total_deposits = 0.0
    total_withdrawals = 0.0
    for t in txs:
        amt = float(t.amount)
        if t.transaction_type.upper() in ["DEPOSIT", "ADDITION", "DEDUCTION"]:
            total_deposits += amt
        elif t.transaction_type.upper() in ["WITHDRAWAL", "REFUND", "SETTLEMENT"]:
            total_withdrawals += amt

    current_balance = max(0.0, round(total_deposits - total_withdrawals, 2))

    return {
        "items": [
            {
                "id": t.id,
                "transaction_type": t.transaction_type,
                "amount": round(float(t.amount), 2),
                "notes": t.notes,
                "created_at": str(t.created_at),
            }
            for t in txs
        ],
        "current_balance": current_balance,
        "total_deposits": round(total_deposits, 2),
        "total_withdrawals": round(total_withdrawals, 2),
    }


@router.post("/{employee_id}/savings-fund/transactions", response_model=dict)
async def create_savings_fund_transaction(
    employee_id: int,
    data: SavingsFundTransactionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """Add a deposit, addition, withdrawal, refund, or resignation settlement for an employee's savings fund."""
    from app.models.employee import SecurityFundTransaction
    emp_res = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = emp_res.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    valid_types = ["DEPOSIT", "ADDITION", "DEDUCTION", "WITHDRAWAL", "REFUND", "SETTLEMENT"]
    tx_type = data.transaction_type.upper().strip()
    if tx_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid transaction_type '{data.transaction_type}'. Must be one of: {', '.join(valid_types)}")

    amount = float(data.amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero.")

    # Calculate current balance before withdrawal/refund/settlement
    res_tx = await db.execute(
        select(SecurityFundTransaction).where(SecurityFundTransaction.employee_id == employee_id)
    )
    existing_txs = res_tx.scalars().all()
    cur_deposits = sum(float(t.amount) for t in existing_txs if t.transaction_type.upper() in ["DEPOSIT", "ADDITION", "DEDUCTION"])
    cur_withdrawals = sum(float(t.amount) for t in existing_txs if t.transaction_type.upper() in ["WITHDRAWAL", "REFUND", "SETTLEMENT"])
    current_balance = max(0.0, round(cur_deposits - cur_withdrawals, 2))

    if tx_type in ["WITHDRAWAL", "REFUND", "SETTLEMENT"]:
        if amount > current_balance:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient savings fund balance. Requested: ₹{amount:,.2f}, Available: ₹{current_balance:,.2f}."
            )

    tx = SecurityFundTransaction(
        employee_id=employee_id,
        transaction_type=tx_type,
        amount=amount,
        notes=data.notes,
        created_by_id=current_user.id,
    )
    db.add(tx)
    await db.flush()

    new_balance = round(current_balance - amount if tx_type in ["WITHDRAWAL", "REFUND", "SETTLEMENT"] else current_balance + amount, 2)

    await log_audit(
        db, current_user.id, "CREATE", "SecurityFundTransaction", str(tx.id),
        f"Savings fund {tx_type}: ₹{amount} for employee {emp.full_name} (New Balance: ₹{new_balance})"
    )
    await db.commit()
    return {
        "status": "success",
        "id": tx.id,
        "transaction_type": tx.transaction_type,
        "amount": round(float(tx.amount), 2),
        "notes": tx.notes,
        "current_balance": new_balance,
    }


@router.put("/{employee_id}", response_model=dict)
async def update_employee(
    employee_id: int,
    data: EmployeeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))
    ],
):
    """Update an employee."""
    result = await db.execute(
        select(Employee).where(Employee.id == employee_id)
        .options(selectinload(Employee.department), selectinload(Employee.designation), selectinload(Employee.shift))
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    old_data = {
        "employee_id": emp.employee_id,
        "name": emp.full_name,
        "security_fund_deduction": float(emp.security_fund_deduction) if emp.security_fund_deduction is not None else 0.0,
    }

    update_data = data.model_dump(exclude_unset=True)

    if "security_fund_deduction" in update_data and update_data["security_fund_deduction"] is not None:
        fund_amt = round(float(update_data["security_fund_deduction"]), 2)
        target_basic = update_data.get("basic_salary") if update_data.get("basic_salary") is not None else emp.basic_salary
        if target_basic is not None and float(target_basic) > 0 and fund_amt > float(target_basic):
            raise HTTPException(
                status_code=400,
                detail=f"Savings fund deduction (₹{fund_amt:,.2f}) cannot exceed basic salary (₹{float(target_basic):,.2f}).",
            )
        update_data["security_fund_deduction"] = fund_amt

    if "basic_salary" in update_data and update_data["basic_salary"] is not None:
        if "salary_verified" not in update_data:
            update_data["salary_verified"] = True
        update_data["salary_source"] = "MANUAL"

    for field, value in update_data.items():
        setattr(emp, field, value)

    # Update full_name if first or last name changed
    if "first_name" in update_data or "last_name" in update_data:
        emp.full_name = f"{emp.first_name} {emp.last_name or ''}".strip()

    # If deactivated, clean up unfinalized payroll records
    if update_data.get("is_active") is False:
        from app.models.payroll import PayrollRecord, PayrollItem, PayrollPeriod, PayrollStatus
        from sqlalchemy import delete
        draft_rec_res = await db.execute(
            select(PayrollRecord.id)
            .join(PayrollPeriod, PayrollRecord.period_id == PayrollPeriod.id)
            .where(
                PayrollRecord.employee_id == emp.id,
                PayrollPeriod.status != PayrollStatus.FINALIZED,
            )
        )
        draft_rec_ids = draft_rec_res.scalars().all()
        if draft_rec_ids:
            await db.execute(delete(PayrollItem).where(PayrollItem.payroll_record_id.in_(draft_rec_ids)))
            await db.execute(delete(PayrollRecord).where(PayrollRecord.id.in_(draft_rec_ids)))

    await log_audit(
        db, current_user.id, "UPDATE", "Employee", str(emp.id),
        f"Updated employee {emp.employee_id}",
        old_value=json.dumps(old_data, default=str),
        new_value=json.dumps(update_data, default=str),
    )
    await db.commit()
    await db.refresh(emp, ["department", "designation", "shift"])
    return _build_employee_response(emp)


@router.post("/bulk-set-savings", response_model=dict)
async def bulk_set_savings(
    data: BulkSetSavingsRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))
    ],
):
    """Bulk update monthly savings fund deduction for selected employees."""
    amt = round(float(data.amount), 2)
    if amt < 0:
        raise HTTPException(status_code=400, detail="Savings fund deduction cannot be negative.")

    result = await db.execute(select(Employee).where(Employee.id.in_(data.employee_ids)))
    employees = result.scalars().all()
    if not employees:
        raise HTTPException(status_code=404, detail="No matching employees found.")

    # Validation: cannot exceed basic salary
    for emp in employees:
        if emp.basic_salary is not None and float(emp.basic_salary) > 0 and amt > float(emp.basic_salary):
            raise HTTPException(
                status_code=400,
                detail=f"Savings fund deduction (₹{amt:,.2f}) cannot exceed basic salary (₹{float(emp.basic_salary):,.2f}) for {emp.full_name} ({emp.employee_id})."
            )

    updated_count = 0
    for emp in employees:
        old_val = float(emp.security_fund_deduction) if emp.security_fund_deduction is not None else 0.0
        emp.security_fund_deduction = amt
        updated_count += 1
        await log_audit(
            db, current_user.id, "UPDATE", "Employee", str(emp.id),
            f"Bulk updated monthly savings fund deduction for {emp.full_name} from ₹{old_val} to ₹{amt}",
            old_value=str(old_val),
            new_value=str(amt),
        )

    await db.commit()
    return {
        "status": "success",
        "updated_count": updated_count,
        "amount": amt,
    }


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))
    ],
):
    """Soft delete / deactivate an employee (sets is_active=False and cleans unfinalized payroll)."""
    result = await db.execute(select(Employee).where(Employee.id == employee_id))
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    emp.is_active = False

    # Clean up unfinalized payroll records for this deactivated employee
    from app.models.payroll import PayrollRecord, PayrollItem, PayrollPeriod, PayrollStatus
    from sqlalchemy import delete
    draft_rec_res = await db.execute(
        select(PayrollRecord.id)
        .join(PayrollPeriod, PayrollRecord.period_id == PayrollPeriod.id)
        .where(
            PayrollRecord.employee_id == emp.id,
            PayrollPeriod.status != PayrollStatus.FINALIZED,
        )
    )
    draft_rec_ids = draft_rec_res.scalars().all()
    if draft_rec_ids:
        await db.execute(delete(PayrollItem).where(PayrollItem.payroll_record_id.in_(draft_rec_ids)))
        await db.execute(delete(PayrollRecord).where(PayrollRecord.id.in_(draft_rec_ids)))

    await log_audit(
        db, current_user.id, "DELETE", "Employee", str(emp.id),
        f"Deactivated employee {emp.employee_id} - {emp.full_name}",
    )
    await db.commit()
