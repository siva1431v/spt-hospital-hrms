"""
SPT Hospital HRMS — Payroll Engine
Implements the live manual salary calculator formula integrated with 15-minute qualifying lateness LOP rule:
  daysInMonth  = calendar days in the SELECTED month (28 / 29 / 30 / 31)
  perDay       = baseSalary / daysInMonth
  qualifyingLate = late > 15 mins count
  lopDays      = floor(qualifyingLate / 3)   [from lateness or MonthlyAttendanceAggregate]
  rawPayable   = min(presentDays, daysInMonth) + (halfDays * 0.5) + min(leaveDays, 3) + offDutyDays
  payableDays  = max(0.0, rawPayable - lopDays)
  salaryPart   = min(payableDays * perDay, baseSalary)
  totalSalary  = salaryPart + collection
"""
import logging
import calendar
from datetime import date
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract, and_, delete
from sqlalchemy.orm import selectinload

from app.models.employee import Employee
from app.models.attendance import Attendance, AttendanceStatus, MonthlyAttendanceAggregate
from app.models.leave import LeaveRequest, LeaveRequestStatus, LeaveType
from app.models.payroll import (
    SalaryStructure, SalaryStructureItem, SalaryComponent,
    PayrollRecord, PayrollItem, PayrollPeriod, ComponentType, PayrollStatus,
)

logger = logging.getLogger(__name__)


def _last_day_of_month(year: int, month: int) -> date:
    """Return the last day of the given month."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, last_day)


class PayrollEngine:
    """
    Payroll calculation engine matching the hospital owner's live manual salary calculator
    integrated with lateness LOP (3 qualifying late days -> 1 LOP day).
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_employee_payroll(
        self,
        employee_id: int,
        year: int,
        month: int,
        working_days: int = 0,
        period: Optional[PayrollPeriod] = None,
        override_inputs: Optional[dict] = None,
    ) -> Optional[tuple[PayrollRecord, list]]:
        """
        Calculate payroll for a single employee for the given month.
        """
        emp_result = await self.db.execute(
            select(Employee).options(selectinload(Employee.shift)).where(Employee.id == employee_id)
        )
        employee = emp_result.scalar_one_or_none()
        if not employee or not employee.is_active:
            return None

        # Base salary from employee profile or structure
        base_salary = float(employee.basic_salary or 0.0)
        if base_salary == 0.0:
            struct_result = await self.db.execute(
                select(SalaryStructure).where(SalaryStructure.employee_id == employee_id, SalaryStructure.is_active == True)
            )
            struct = struct_result.scalar_one_or_none()
            if struct:
                base_salary = float(struct.basic_salary)

        # Days in month derived from selected month (28/29/30/31)
        days_in_month = calendar.monthrange(year, month)[1]

        # Effective days in month for this employee (respecting joining/exit dates)
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month)
        emp_start = max(month_start, employee.joining_date) if employee.joining_date else month_start
        emp_end = min(month_end, employee.exit_date) if hasattr(employee, 'exit_date') and employee.exit_date else month_end
        effective_days_in_month = max(0, (emp_end - emp_start).days + 1)

        # Check existing payroll record to respect manual overrides
        existing = None
        if period:
            existing_result = await self.db.execute(
                select(PayrollRecord).where(
                    PayrollRecord.employee_id == employee_id,
                    PayrollRecord.period_id == period.id,
                )
            )
            existing = existing_result.scalar_one_or_none()

        # Load attendance records for the month
        att_query = select(Attendance).where(
            Attendance.employee_id == employee_id,
            extract("year", Attendance.attendance_date) == year,
            extract("month", Attendance.attendance_date) == month,
        )
        # Exclude dates before joining or after exit
        if employee.joining_date:
            att_query = att_query.where(Attendance.attendance_date >= employee.joining_date)
        if hasattr(employee, 'exit_date') and employee.exit_date:
            att_query = att_query.where(Attendance.attendance_date <= employee.exit_date)
        att_result = await self.db.execute(att_query)
        attendance_records = att_result.scalars().all()

        # 1. Load pre-computed monthly aggregate from PDF import (matched by employee_id or biometric/employee code)
        from sqlalchemy import or_
        emp_code_str = str(employee.biometric_code or employee.employee_id or "")
        agg_result = await self.db.execute(
            select(MonthlyAttendanceAggregate).where(
                MonthlyAttendanceAggregate.year == year,
                MonthlyAttendanceAggregate.month == month,
                or_(
                    MonthlyAttendanceAggregate.employee_id == employee_id,
                    MonthlyAttendanceAggregate.employee_code == emp_code_str,
                    MonthlyAttendanceAggregate.employee_code == str(employee.employee_id or ""),
                    MonthlyAttendanceAggregate.employee_code == str(employee.biometric_code or ""),
                )
            )
        )
        monthly_agg = agg_result.scalars().first()

        # Load system settings
        from app.models.audit import SystemSetting
        grace_period = 5
        late_days_per_lop = 3
        paid_leave_cap = 3.0
        try:
            settings_res = await self.db.execute(select(SystemSetting))
            for s in settings_res.scalars().all():
                if s.key == "attendance_grace_period" and s.value:
                    grace_period = int(s.value)
                elif s.key == "lop_late_threshold_days" and s.value:
                    late_days_per_lop = max(1, int(s.value))
                elif s.key == "paid_leave_monthly_cap" and s.value:
                    paid_leave_cap = float(s.value)
        except Exception as e:
            logger.warning(f"Could not load system settings: {e}")

        # Check approved leave requests for the month
        lr_res = await self.db.execute(
            select(func.coalesce(func.sum(LeaveRequest.days_count), 0.0)).where(
                LeaveRequest.employee_id == employee_id,
                LeaveRequest.status == LeaveRequestStatus.APPROVED,
                extract("year", LeaveRequest.start_date) == year,
                extract("month", LeaveRequest.start_date) == month,
            )
        )
        approved_lr_days = float(lr_res.scalar() or 0.0)

        # 2. Extract Attendance Counts (Present, Absent, Leave)
        if override_inputs and "present_days" in override_inputs and override_inputs["present_days"] is not None:
            present_days = float(override_inputs["present_days"])
        elif existing and existing.is_manual_override and existing.present_days is not None:
            present_days = float(existing.present_days)
        else:
            present_days = float(sum(
                1 for a in attendance_records
                if a.status in [AttendanceStatus.PRESENT, AttendanceStatus.PRESENT_OVERNIGHT]
                or (a.status == AttendanceStatus.PRESENT_INCOMPLETE and a.is_corrected)
            ))
            if (present_days == 0 or not attendance_records) and monthly_agg and monthly_agg.present_count is not None:
                present_days = float(monthly_agg.present_count)

        if override_inputs and "leave_days" in override_inputs and override_inputs["leave_days"] is not None:
            leave_days = float(override_inputs["leave_days"])
            absent_days = float(override_inputs.get("absent_days", max(0.0, float(effective_days_in_month) - present_days - leave_days)))
        elif existing and existing.is_manual_override and existing.leave_days is not None:
            leave_days = float(existing.leave_days)
            absent_days = float(existing.absent_days if existing.absent_days is not None else max(0.0, float(effective_days_in_month) - present_days - leave_days))
        else:
            if attendance_records:
                absent_count_att = sum(1 for a in attendance_records if a.status == AttendanceStatus.ABSENT)
                leave_count_att = sum(1 for a in attendance_records if a.status == AttendanceStatus.LEAVE)
                absent_days = float(absent_count_att)
                leave_days = float(leave_count_att + approved_lr_days)
            elif monthly_agg:
                absent_days = float(monthly_agg.absent_count or 0)
                leave_days = float((monthly_agg.leaves_taken or 0) + approved_lr_days)
            else:
                absent_days = max(0.0, float(effective_days_in_month) - present_days)
                leave_days = approved_lr_days

        # First 3 days of absence / leave are paid
        # Paid Leave = MIN(absent_days + leave_days, 3)
        # Unpaid Absence LOP = MAX((absent_days + leave_days) - 3, 0)
        total_absences = absent_days + leave_days
        effective_paid_leave = min(total_absences, paid_leave_cap)
        unpaid_absence_days = max(0.0, total_absences - paid_leave_cap)

        # 3. Lateness LOP: 3 late arrivals = 1 LOP day (Late LOP = floor(late_count / 3))
        if override_inputs and "qualifying_late_days" in override_inputs and override_inputs["qualifying_late_days"] is not None:
            qualifying_late_days = int(override_inputs["qualifying_late_days"])
            late_lop_days = float(override_inputs.get("lop_days", qualifying_late_days // late_days_per_lop))
        elif override_inputs and ("lop_days" in override_inputs or "loss_of_pay_days" in override_inputs):
            late_lop_days = float(override_inputs.get("lop_days", override_inputs.get("loss_of_pay_days", 0.0)))
            qualifying_late_days = int(override_inputs.get("qualifying_late_days", late_lop_days * late_days_per_lop))
        elif existing and existing.is_manual_override and existing.lop_days is not None:
            late_lop_days = float(existing.lop_days)
            qualifying_late_days = int(existing.qualifying_late_days if existing.qualifying_late_days is not None else late_lop_days * late_days_per_lop)
        elif monthly_agg:
            qualifying_late_days = int(monthly_agg.late_by_days if monthly_agg.late_by_days is not None else (monthly_agg.late_days_qualifying or 0))
            late_lop_days = float(qualifying_late_days // late_days_per_lop)
        else:
            att_late_result = await self.db.execute(
                select(Attendance).where(
                    Attendance.employee_id == employee_id,
                    extract("year", Attendance.attendance_date) == year,
                    extract("month", Attendance.attendance_date) == month,
                    Attendance.is_late == True,
                )
            )
            late_records = att_late_result.scalars().all()
            emp_grace = employee.shift.grace_period_minutes if (employee.shift and employee.shift.grace_period_minutes is not None) else grace_period
            qualifying_late_days = sum(
                1 for a in late_records
                if getattr(a, "late_minutes", 0) > emp_grace or getattr(a, "is_late", False)
            )
            late_lop_days = float(qualifying_late_days // late_days_per_lop)

        lop_days = late_lop_days
        loss_of_pay_days = lop_days

        # Additional inputs (override > existing > default)
        half_days = float(
            override_inputs["half_days"] if override_inputs and "half_days" in override_inputs and override_inputs["half_days"] is not None
            else (existing.half_days if existing and existing.is_manual_override and existing.half_days is not None else 0.0)
        )
        off_duty_days = float(
            override_inputs["off_duty_days"] if override_inputs and "off_duty_days" in override_inputs and override_inputs["off_duty_days"] is not None
            else (existing.off_duty_days if existing and existing.is_manual_override and existing.off_duty_days is not None else 0.0)
        )
        collection = float(
            override_inputs["collection"] if override_inputs and "collection" in override_inputs and override_inputs["collection"] is not None
            else (existing.collection if existing and existing.is_manual_override and existing.collection is not None else 0.0)
        )
        is_manual_override = bool(
            override_inputs.get("is_manual_override", True) if override_inputs and override_inputs.get("is_manual_override") is not None
            else (existing.is_manual_override if existing else False)
        )

        # ── 4. FORMULA: PAYABLE DAYS & SALARY PART ──────────────────────────────
        per_day = base_salary / days_in_month if days_in_month > 0 else 0.0
        effective_present = min(present_days, float(days_in_month))

        # Payable Days = Present + (Half * 0.5) + MIN(Total Absences, 3) + Off Duty
        payable_days = round(effective_present + (half_days * 0.5) + effective_paid_leave + off_duty_days, 2)
        salary_part = round(min(payable_days * per_day, base_salary), 2)

        # ── 5. DEDUCTIONS (LATENESS LOP & SAVINGS FUND) ──────────────────────────
        gross_salary = round(salary_part + collection, 2)
        # LOP deduction = Late LOP * per_day (unpaid absence is already excluded from payable_days)
        lop_deduction = round(min(lop_days * per_day, salary_part), 2)

        # Savings fund deduction: ONLY if gross earnings after LOP can fully cover it
        available_for_fund = max(0.0, gross_salary - lop_deduction)
        fund_deduction = 0.0
        fund_requested = float(employee.security_fund_deduction) if employee.security_fund_deduction is not None else 0.0
        if fund_requested > 0:
            if available_for_fund >= fund_requested:
                fund_deduction = round(fund_requested, 2)
            else:
                fund_deduction = 0.0

        raw_total_deductions = round(lop_deduction + fund_deduction, 2)
        total_deductions = round(min(raw_total_deductions, gross_salary), 2)
        carried_forward_deductions = 0.0
        net_salary = round(max(0.0, gross_salary - total_deductions), 2)

        # Compute lifetime collection up to this month
        past_col_result = await self.db.execute(
            select(func.coalesce(func.sum(PayrollRecord.collection), 0.0))
            .join(PayrollPeriod, PayrollRecord.period_id == PayrollPeriod.id)
            .where(
                PayrollRecord.employee_id == employee_id,
                (PayrollPeriod.year < year) | ((PayrollPeriod.year == year) & (PayrollPeriod.month < month)),
            )
        )
        past_lifetime = float(past_col_result.scalar() or 0.0)
        lifetime_collection = round(past_lifetime + collection, 2)

        # Build PayrollRecord
        record = PayrollRecord(
            employee_id=employee_id,
            period_id=period.id if period else None,
            total_working_days=days_in_month,
            present_days=present_days,
            absent_days=absent_days,
            half_days=half_days,
            leave_days=total_absences,
            paid_leave_days=effective_paid_leave,
            off_duty_days=off_duty_days,
            qualifying_late_days=qualifying_late_days,
            loss_of_pay_days=loss_of_pay_days,
            lop_days=lop_days,
            collection=collection,
            payable_days=payable_days,
            salary_part=salary_part,
            lifetime_collection=lifetime_collection,
            is_manual_override=is_manual_override,
            basic_salary=base_salary,
            gross_salary=gross_salary,
            lop_deduction=lop_deduction,
            security_fund_deduction=fund_deduction,
            total_deductions=total_deductions,
            carried_forward_deductions=carried_forward_deductions,
            ot_amount=0.0,
            net_salary=net_salary,
            status=PayrollStatus.DRAFT,
        )

        payroll_items = [
            ("Salary Part", ComponentType.EARNING, salary_part, None),
            ("Collection", ComponentType.EARNING, collection, None),
        ]
        if lop_deduction > 0 or lop_days > 0:
            if qualifying_late_days > 0:
                lop_label = f"Lateness LOP ({lop_days:.0f} days from {qualifying_late_days} late arrivals)"
            else:
                lop_label = f"Lateness LOP ({lop_days:.0f} days)"
            payroll_items.append((lop_label, ComponentType.DEDUCTION, lop_deduction, None))

        if fund_deduction > 0:
            payroll_items.append(("Staff Savings Fund", ComponentType.DEDUCTION, fund_deduction, None))

        return record, payroll_items

    async def calculate_all_employees(
        self,
        period: PayrollPeriod,
        working_days: int = 0,
        user_id: int = 1,
    ) -> dict:
        """Calculate payroll for all active employees for the given period."""
        from sqlalchemy import delete
        from app.models.payroll import PayrollItem

        # Clean up records for any inactive employees in this unfinalized period
        inactive_rec_res = await self.db.execute(
            select(PayrollRecord.id)
            .join(Employee, PayrollRecord.employee_id == Employee.id)
            .where(
                PayrollRecord.period_id == period.id,
                Employee.is_active == False,
            )
        )
        inactive_rec_ids = inactive_rec_res.scalars().all()
        if inactive_rec_ids:
            await self.db.execute(delete(PayrollItem).where(PayrollItem.payroll_record_id.in_(inactive_rec_ids)))
            await self.db.execute(delete(PayrollRecord).where(PayrollRecord.id.in_(inactive_rec_ids)))

        emp_result = await self.db.execute(select(Employee).where(Employee.is_active == True))
        employees = emp_result.scalars().all()

        calculated = 0
        failed = 0

        for employee in employees:
            try:
                result = await self.calculate_employee_payroll(
                    employee.id, period.year, period.month, period=period
                )
                if result:
                    record, items_data = result

                    from sqlalchemy import delete
                    existing_result = await self.db.execute(
                        select(PayrollRecord).where(
                            PayrollRecord.employee_id == employee.id,
                            PayrollRecord.period_id == period.id,
                        )
                    )
                    existing = existing_result.scalar_one_or_none()

                    if existing:
                        for attr in [
                            "total_working_days", "present_days", "absent_days",
                            "half_days", "leave_days", "paid_leave_days", "off_duty_days",
                            "qualifying_late_days", "loss_of_pay_days", "lop_days",
                            "collection", "payable_days", "salary_part", "lifetime_collection",
                            "is_manual_override", "basic_salary", "gross_salary",
                            "lop_deduction", "security_fund_deduction", "total_deductions",
                            "net_salary", "status"
                        ]:
                            setattr(existing, attr, getattr(record, attr))
                        payroll_record = existing
                        await self.db.execute(
                            delete(PayrollItem).where(PayrollItem.payroll_record_id == existing.id)
                        )
                    else:
                        self.db.add(record)
                        await self.db.flush()
                        payroll_record = record

                    for name, comp_type, amount, comp_id in items_data:
                        item = PayrollItem(
                            payroll_record_id=payroll_record.id,
                            component_id=comp_id,
                            component_name=name,
                            component_type=comp_type,
                            amount=round(amount, 2),
                        )
                        self.db.add(item)

                    calculated += 1
            except Exception as e:
                logger.error(f"Failed to calculate payroll for employee {employee.id}: {e}")
                failed += 1

        # Create SecurityFundTransaction for savings fund deductions (idempotent per period)
        from app.models.employee import SecurityFundTransaction
        note_str = f"Payroll deduction for {period.period_name}"

        # Delete existing transactions for this period to prevent double-posting on recalculation
        await self.db.execute(
            delete(SecurityFundTransaction).where(
                SecurityFundTransaction.notes == note_str
            )
        )

        # Re-query all records for this period to get fund deductions
        all_records_result = await self.db.execute(
            select(PayrollRecord).where(PayrollRecord.period_id == period.id)
        )
        for rec in all_records_result.scalars().all():
            fund_amt = float(rec.security_fund_deduction or 0.0)
            if fund_amt > 0:
                tx = SecurityFundTransaction(
                    employee_id=rec.employee_id,
                    transaction_type="DEPOSIT",
                    amount=fund_amt,
                    notes=note_str,
                    created_by_id=user_id,
                )
                self.db.add(tx)

        await self.db.commit()
        return {"calculated": calculated, "failed": failed, "total": len(employees)}
