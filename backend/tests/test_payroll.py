"""
SPT Hospital HRMS — Integration Tests for Payroll Engine (Manual Salary Calculator Formula)
"""
import pytest
import random
from datetime import date
from sqlalchemy import select
from app.payroll.engine import PayrollEngine
from app.models.employee import Employee, EmploymentType
from app.models.payroll import SalaryComponent, SalaryStructure, SalaryStructureItem, ComponentType, PayrollStatus, PayrollPeriod
from app.models.attendance import Attendance, AttendanceStatus
from app.core.database import AsyncSessionLocal

import uuid

@pytest.mark.asyncio
async def test_payroll_calculations():
    """Verify that the payroll engine computes manual calculator formula correctly with DB objects."""
    async with AsyncSessionLocal() as session:
        rand_code = f"TEST_EMP_{uuid.uuid4().hex[:6]}"
        rand_bio = f"{random.randint(10000, 99999)}"
        # 1. Create a dummy employee
        employee = Employee(
            employee_id=rand_code,
            biometric_code=rand_bio,
            first_name="John",
            last_name="Doe",
            full_name="John Doe",
            email=f"{rand_code.lower()}@spthospital.com",
            employment_type=EmploymentType.FULL_TIME,
            basic_salary=20000.0,
            security_fund_deduction=0.0,
            is_active=True
        )
        session.add(employee)
        await session.flush()
        emp_id = employee.id

        # 2. Get or create payroll period
        res = await session.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 8))
        period = res.scalar_one_or_none()
        if not period:
            period = PayrollPeriod(year=2026, month=8, period_name="August 2026", working_days=31, status=PayrollStatus.DRAFT, created_by_id=1)
            session.add(period)
            await session.flush()

        engine = PayrollEngine(session)

        # Scenario 1: 20 present days, 2 half days in August (31 days)
        # Payable = 20 + 2*0.5 = 21 days → 21 * 20000 / 31 = 13,548.39
        override_1 = {
            'present_days': 20.0,
            'half_days': 2.0,
            'leave_days': 0.0,
            'off_duty_days': 0.0,
            'collection': 0.0,
        }
        res1 = await engine.calculate_employee_payroll(
            employee_id=emp_id, year=2026, month=8, period=period, override_inputs=override_1
        )
        assert res1 is not None
        rec1, _ = res1
        assert rec1.payable_days == 21.0
        assert rec1.salary_part == 13548.39
        assert rec1.net_salary == 13548.39

        # Scenario 2: 25 present days, 3 half days, 5 leave days (capped @ 3), 2 off duty, 500 collection
        # Payable = 25 + 1.5 + 3 + 2 = 31.5 days → salary_part capped @ 20000.0 → total = 20500.0
        override_2 = {
            'present_days': 25.0,
            'half_days': 3.0,
            'leave_days': 5.0,
            'off_duty_days': 2.0,
            'collection': 500.0,
        }
        res2 = await engine.calculate_employee_payroll(
            employee_id=emp_id, year=2026, month=8, period=period, override_inputs=override_2
        )
        assert res2 is not None
        rec2, _ = res2
        assert rec2.payable_days == 31.5
        assert rec2.salary_part == 20000.0
        assert rec2.net_salary == 20500.0

        # Clean up test employee so DB remains clean
        await session.delete(employee)
        await session.rollback()
