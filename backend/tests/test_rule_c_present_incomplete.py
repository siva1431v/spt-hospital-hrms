"""
Regression test for Rule (C): PRESENT_INCOMPLETE lateness LOP vs payable days.

Rule (C) specifies:
- Uncorrected PRESENT_INCOMPLETE records are EXCLUDED from present_days (not payable).
- However, they are INCLUDED in qualifying_late_days and contribute to lateness LOP.
"""
import pytest
from datetime import date, time, datetime
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.payroll.engine import PayrollEngine
from app.models.employee import Employee
from app.models.attendance import Attendance, AttendanceStatus
from app.models.payroll import PayrollPeriod


@pytest.mark.asyncio
async def test_dr_manoj_rule_c_behavior():
    """
    Verify Dr. Manoj (employee_id=32) under Rule (C):
    - Has 13 PRESENT and 10 uncorrected PRESENT_INCOMPLETE records in Aug 2026.
    - present_days must be 13.0 (the 10 PRESENT_INCOMPLETE records are excluded).
    - qualifying_late_days is 18 (includes late arrivals from PRESENT_INCOMPLETE days).
    - lop_days is 6.0 (18 // 3 = 6 LOP days).
    """
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)
        rec, items = await engine.calculate_employee_payroll(employee_id=32, year=2026, month=8)

        # 1. present_days must only count verified PRESENT records (13), not uncorrected PRESENT_INCOMPLETE
        assert rec.present_days == 13.0, f"Expected present_days to be 13.0, got {rec.present_days}"

        # 2. qualifying_late_days and lop_days are preserved
        assert rec.qualifying_late_days == 18, f"Expected 18 qualifying late days, got {rec.qualifying_late_days}"
        assert rec.lop_days == 6.0, f"Expected 6.0 LOP days, got {rec.lop_days}"
        assert rec.loss_of_pay_days == 6.0

        # 3. Lateness LOP deduction is applied
        assert rec.lop_deduction > 0.0
        deduction_labels = [item[0] for item in items if "Lateness LOP" in item[0]]
        assert len(deduction_labels) == 1
        assert "6 days from 18 late arrivals" in deduction_labels[0]


@pytest.mark.asyncio
async def test_synthetic_present_incomplete_rule_c_daily_records():
    """
    Verify synthetic daily attendance behavior under Rule (C):
    - 3 uncorrected PRESENT_INCOMPLETE records with is_late=True, late_minutes=25:
      -> present_days == 0.0 (excluded from payable days)
      -> qualifying_late_days == 3 (included in lateness)
      -> lop_days == 1.0 (3 // 3 = 1)
    - If 1 of the 3 is corrected (is_corrected=True):
      -> present_days == 1.0
      -> qualifying_late_days == 3
      -> lop_days == 1.0
    """
    async with AsyncSessionLocal() as session:
        # Create test employee
        emp = Employee(
            first_name="RuleC",
            last_name="TestEmployee",
            full_name="RuleC TestEmployee",
            employee_id="RULE_C_001",
            biometric_code="999888",
            basic_salary=31000.0,
            is_active=True,
        )
        session.add(emp)
        await session.flush()

        # Insert 3 uncorrected PRESENT_INCOMPLETE records in September 2026
        # (September has no monthly aggregates seeded)
        att_dates = [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]
        att_records = []
        for d in att_dates:
            att = Attendance(
                employee_id=emp.id,
                attendance_date=d,
                status=AttendanceStatus.PRESENT_INCOMPLETE,
                is_corrected=False,
                is_late=True,
                late_minutes=25,
                source_in_time="09:25",
                check_in_datetime=datetime(2026, 9, d.day, 9, 25),
            )
            session.add(att)
            att_records.append(att)
        await session.commit()

        engine = PayrollEngine(session)

        # 1. Test uncorrected: present_days == 0.0, qualifying_late_days == 3, lop_days == 1.0
        rec_uncorrected, _ = await engine.calculate_employee_payroll(employee_id=emp.id, year=2026, month=9)
        assert rec_uncorrected.present_days == 0.0, (
            f"Expected present_days == 0.0 for uncorrected PRESENT_INCOMPLETE, got {rec_uncorrected.present_days}"
        )
        assert rec_uncorrected.qualifying_late_days == 3, (
            f"Expected qualifying_late_days == 3, got {rec_uncorrected.qualifying_late_days}"
        )
        assert rec_uncorrected.lop_days == 1.0, (
            f"Expected lop_days == 1.0, got {rec_uncorrected.lop_days}"
        )

        # 2. Correct 1 record
        att_records[0].is_corrected = True
        await session.commit()

        rec_corrected, _ = await engine.calculate_employee_payroll(employee_id=emp.id, year=2026, month=9)
        assert rec_corrected.present_days == 1.0, (
            f"Expected present_days == 1.0 after correcting 1 record, got {rec_corrected.present_days}"
        )
        assert rec_corrected.qualifying_late_days == 3, (
            f"Expected qualifying_late_days == 3, got {rec_corrected.qualifying_late_days}"
        )
        assert rec_corrected.lop_days == 1.0, (
            f"Expected lop_days == 1.0, got {rec_corrected.lop_days}"
        )
