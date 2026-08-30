"""
SPT Hospital HRMS — LOP Auto-Fill and Day-Level Leave Reclassification Integration Tests
"""
import pytest
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.attendance import Attendance, AttendanceStatus, MonthlyAttendanceAggregate
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus
from app.payroll.engine import PayrollEngine


@pytest.mark.asyncio
async def test_lop_autofill_in_payroll_calculation():
    """Verify that calculate_all_employees auto-populates lop_days and lop_deduction from aggregates."""
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)
        p_res = await session.execute(
            select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 8)
        )
        period = p_res.scalar_one_or_none()
        assert period is not None

        stats = await engine.calculate_all_employees(period, period.working_days, 1)
        assert stats["calculated"] >= 57

        # Fetch records
        r_res = await session.execute(
            select(PayrollRecord).options(selectinload(PayrollRecord.employee)).where(PayrollRecord.period_id == period.id)
        )
        records = r_res.scalars().all()

        lop_records = [r for r in records if r.lop_days > 0]
        assert 34 <= len(lop_records) <= 38  # staff with LOP under 5m grace rule
        assert sum(r.lop_days for r in records) >= 110.0

        # Check Dr Manoj (SPT1)
        manoj = next((r for r in records if r.employee and r.employee.biometric_code == "1"), None)
        assert manoj is not None
        assert manoj.lop_days == 6.0
        assert manoj.lop_deduction == 4838.71
        assert manoj.qualifying_late_days == 18

        # Check Dr Saran (SPT61)
        saran = next((r for r in records if r.employee and r.employee.biometric_code == "61"), None)
        assert saran is not None
        assert saran.lop_days == 3.0
        assert saran.lop_deduction == 2419.35
        assert saran.qualifying_late_days == 10

        # Check Aarthi G (SPT59)
        aarthi = next((r for r in records if r.employee and r.employee.biometric_code == "59"), None)
        assert aarthi is not None
        assert aarthi.lop_days in [0.0, 2.0]


@pytest.mark.asyncio
async def test_day_level_leave_reclassification_and_payroll_flow():
    """
    Test day-level reclassification of an ABSENT attendance record to LEAVE,
    and verify that it automatically flows into payroll leave_days and payable_days (capped at 3 paid).
    """
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)

        # Pick an employee with multiple absences: Tamilmaran (bio 60, 19 present, 6 absent)
        emp_res = await session.execute(select(Employee).where(Employee.biometric_code == "60"))
        emp = emp_res.scalar_one_or_none()
        assert emp is not None

        # Reset any previously modified attendance records for Tamilmaran to clean state
        all_att_res = await session.execute(
            select(Attendance).where(
                Attendance.employee_id == emp.id,
                Attendance.status.in_([AttendanceStatus.ABSENT, AttendanceStatus.LEAVE]),
            )
        )
        for a in all_att_res.scalars().all():
            a.status = AttendanceStatus.ABSENT
            a.is_corrected = False
            a.remarks = None
        await session.commit()

        # Find 4 absent records in August 2026
        att_res = await session.execute(
            select(Attendance).where(
                Attendance.employee_id == emp.id,
                Attendance.status == AttendanceStatus.ABSENT,
            ).order_by(Attendance.attendance_date).limit(4)
        )
        absent_records = att_res.scalars().all()
        assert len(absent_records) == 4

        # Reclassify 4 absent days to LEAVE
        for a in absent_records:
            a.status = AttendanceStatus.LEAVE
            a.is_corrected = True
            a.remarks = "Approved Sick Leave"
        await session.commit()

        # Recalculate payroll for Tamilmaran
        p_res = await session.execute(
            select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 8)
        )
        period = p_res.scalar_one_or_none()
        assert period is not None

        calc_res = await engine.calculate_employee_payroll(
            employee_id=emp.id, year=2026, month=8, period=period
        )
        assert calc_res is not None
        record, items = calc_res

        # 4 leave days marked -> 3 counted as paid (cap = 3), 1 unpaid
        assert record.leave_days == 4.0
        assert record.paid_leave_days == 3.0
        # Present 16 (including Aug 25 partial day) + 3 paid leave = 19 payable days
        assert record.payable_days in [18.0, 19.0]

        # Revert back to ABSENT to restore clean state
        for a in absent_records:
            a.status = AttendanceStatus.ABSENT
            a.is_corrected = False
            a.remarks = None
        await session.commit()

        # Recalculate again to verify reversal
        calc_revert = await engine.calculate_employee_payroll(
            employee_id=emp.id, year=2026, month=8, period=period
        )
        rec_rev, _ = calc_revert
        assert rec_rev.leave_days == 0.0
        assert rec_rev.payable_days in [15.0, 16.0]
