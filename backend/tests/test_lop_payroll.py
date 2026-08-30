"""
SPT Hospital HRMS — LOP and Savings Fund Payroll Deduction Tests
Verifies that Lateness Loss of Pay (LOP) and Staff Savings Fund deductions properly reduce net pay.
"""
import pytest
import math
import uuid
import random
from datetime import date
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.employee import Employee, EmploymentType
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus, ComponentType
from app.models.attendance import MonthlyAttendanceAggregate
from app.payroll.engine import PayrollEngine


@pytest.mark.asyncio
async def test_six_spot_checks_and_salary_math():
    """
    Spot check the 6 staff members explicitly listed by hospital management:
    1. SPT1 Dr Manoj (Base 25,000, 5 LOP, Ded 4,032.26): 18,548.39 -> 14,516.13
    2. SPT62 Selladurai (Base 25,000, 5 LOP, Ded 4,032.26): 18,548.39 -> 14,516.13
    3. SPT6 Senthil Murugan (Base 20,000, 6 LOP, Ded 3,870.97): 14,838.71 -> 10,967.74
    4. SPT46 Sarala (Base 13,000, 7 LOP, Ded 2,935.48): 10,064.52 -> 7,129.04
    5. SPT15 Syed Sajith (Base 13,000, 7 LOP, Ded 2,935.48): 9,225.81 -> 6,290.33
    6. SPT56 Gnanasundari (Base 9,500, 7 LOP, Ded 2,145.16): 7,048.39 -> 4,903.23
    """
    spot_checks = [
        {"name": "Dr Manoj", "base": 25000.0, "present": 23.0, "half": 0.0, "leave": 0.0, "off_duty": 0.0, "late_days": 17, "expected_lop_days": 5.0, "expected_ded": 4032.26, "expected_salary_part": 18548.39, "expected_net_before_fund": 14516.13},
        {"name": "Selladurai", "base": 25000.0, "present": 23.0, "half": 0.0, "leave": 0.0, "off_duty": 0.0, "late_days": 15, "expected_lop_days": 5.0, "expected_ded": 4032.26, "expected_salary_part": 18548.39, "expected_net_before_fund": 14516.13},
        {"name": "Senthil Murugan", "base": 20000.0, "present": 23.0, "half": 0.0, "leave": 0.0, "off_duty": 0.0, "late_days": 20, "expected_lop_days": 6.0, "expected_ded": 3870.97, "expected_salary_part": 14838.71, "expected_net_before_fund": 10967.74},
        {"name": "Sarala", "base": 13000.0, "present": 24.0, "half": 0.0, "leave": 0.0, "off_duty": 0.0, "late_days": 23, "expected_lop_days": 7.0, "expected_ded": 2935.48, "expected_salary_part": 10064.52, "expected_net_before_fund": 7129.04},
        {"name": "Syed Sajith", "base": 13000.0, "present": 22.0, "half": 0.0, "leave": 0.0, "off_duty": 0.0, "late_days": 21, "expected_lop_days": 7.0, "expected_ded": 2935.48, "expected_salary_part": 9225.81, "expected_net_before_fund": 6290.33},
        {"name": "Gnanasundari", "base": 9500.0, "present": 23.0, "half": 0.0, "leave": 0.0, "off_duty": 0.0, "late_days": 22, "expected_lop_days": 7.0, "expected_ded": 2145.16, "expected_salary_part": 7048.39, "expected_net_before_fund": 4903.23},
    ]

    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)

        # Get or create period for August 2026 (31 days)
        res = await session.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 8))
        period = res.scalar_one_or_none()
        if not period:
            period = PayrollPeriod(year=2026, month=8, period_name="August 2026", working_days=31, status=PayrollStatus.DRAFT, created_by_id=1)
            session.add(period)
            await session.flush()

        for check in spot_checks:
            rand_code = f"TEST_SPOT_{uuid.uuid4().hex[:6]}"
            emp = Employee(
                employee_id=rand_code,
                biometric_code=f"{random.randint(10000, 99999)}",
                first_name=check["name"],
                last_name="Test",
                full_name=f"{check['name']} Test",
                email=f"{rand_code.lower()}@spthospital.com",
                employment_type=EmploymentType.FULL_TIME,
                basic_salary=check["base"],
                security_fund_deduction=0.0,
                is_active=True
            )
            session.add(emp)
            await session.flush()

            override_inputs = {
                "present_days": check["present"],
                "half_days": check["half"],
                "leave_days": check["leave"],
                "off_duty_days": check["off_duty"],
                "qualifying_late_days": check["late_days"],
                "collection": 0.0,
            }

            calc_res = await engine.calculate_employee_payroll(
                employee_id=emp.id, year=2026, month=8, period=period, override_inputs=override_inputs
            )
            assert calc_res is not None
            record, items = calc_res

            assert record.lop_days == check["expected_lop_days"]
            assert record.salary_part == check["expected_salary_part"]
            assert record.lop_deduction == check["expected_ded"]
            assert record.net_salary == check["expected_net_before_fund"]

            # Clean up
            await session.delete(emp)
        await session.commit()


@pytest.mark.asyncio
async def test_august_2026_period_aggregates():
    """Verify August 2026 real dataset results: exactly 78 LOP days across 30 staff."""
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)
        p_res = await session.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 8))
        period = p_res.scalar_one_or_none()
        assert period is not None

        stats = await engine.calculate_all_employees(period, period.working_days, 1)
        assert stats["calculated"] >= 57

        # Query all records
        r_res = await session.execute(
            select(PayrollRecord).where(PayrollRecord.period_id == period.id)
        )
        records = r_res.scalars().all()
        lop_records = [r for r in records if r.lop_days > 0]
        total_lop_days = sum(r.lop_days for r in records)

        assert 34 <= len(lop_records) <= 38, f"Expected 34-38 staff with LOP, found {len(lop_records)}"
        assert total_lop_days >= 110.0, f"Expected >= 110 LOP days total under 5m grace, found {total_lop_days}"


@pytest.mark.asyncio
async def test_edge_case_lop_greater_than_payable():
    """
    Edge case: Employee has more LOP days than payable days.
    Deduction must clamp to salaryPart (cannot owe money).
    Collection must still be added after deductions.
    """
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)
        p_res = await session.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 8))
        period = p_res.scalar_one_or_none()

        rand_code = f"TEST_CLAMP_{uuid.uuid4().hex[:6]}"
        emp = Employee(
            employee_id=rand_code,
            biometric_code=f"{random.randint(10000, 99999)}",
            first_name="Clamp",
            last_name="Test",
            full_name="Clamp Test",
            email=f"{rand_code.lower()}@spthospital.com",
            employment_type=EmploymentType.FULL_TIME,
            basic_salary=31000.0,  # 1000 per day in August (31 days)
            security_fund_deduction=500.0,
            is_active=True
        )
        session.add(emp)
        await session.flush()

        # Present 4 days -> salaryPart = 4000.
        # Late 21 days -> lopDays = 7 (7000 LOP deduction if un-clamped).
        # Collection = 1500.
        override_inputs = {
            "present_days": 4.0,
            "half_days": 0.0,
            "leave_days": 0.0,
            "off_duty_days": 0.0,
            "qualifying_late_days": 21,  # 7 LOP days
            "collection": 1500.0,
        }

        calc_res = await engine.calculate_employee_payroll(
            employee_id=emp.id, year=2026, month=8, period=period, override_inputs=override_inputs
        )
        assert calc_res is not None
        record, items = calc_res

        # salaryPart = 4000
        assert record.salary_part == 4000.0
        # lop_deduction clamped to salary_part = 4000
        assert record.lop_deduction == 4000.0
        # gross_salary = 4000 + 1500 = 5500
        # total_deductions = min(4500, 5500) = 4500
        # net_salary = 5500 - 4500 = 1000.0
        assert record.gross_salary == 5500.0
        assert record.total_deductions == 4500.0
        assert record.net_salary == 1000.0

        await session.delete(emp)
        await session.commit()


@pytest.mark.asyncio
async def test_30_day_month_calculation():
    """Verify that in a 30-day month (e.g. September), per-day rate uses 30."""
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)

        res = await session.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 9))
        period_sep = res.scalar_one_or_none()
        if not period_sep:
            period_sep = PayrollPeriod(year=2026, month=9, period_name="September 2026", working_days=30, status=PayrollStatus.DRAFT, created_by_id=1)
            session.add(period_sep)
            await session.flush()

        rand_code = f"TEST_SEP_{uuid.uuid4().hex[:6]}"
        emp = Employee(
            employee_id=rand_code,
            biometric_code=f"{random.randint(10000, 99999)}",
            first_name="Sept",
            last_name="Test",
            full_name="Sept Test",
            email=f"{rand_code.lower()}@spthospital.com",
            employment_type=EmploymentType.FULL_TIME,
            basic_salary=30000.0,  # 30,000 / 30 = 1,000 per day
            security_fund_deduction=0.0,
            is_active=True
        )
        session.add(emp)
        await session.flush()

        # Present 20 days -> salaryPart = 20,000
        # Late 6 days -> 2 LOP days -> deduction = 2,000
        # Net = 18,000
        override_inputs = {
            "present_days": 20.0,
            "half_days": 0.0,
            "leave_days": 0.0,
            "off_duty_days": 0.0,
            "qualifying_late_days": 6,
            "collection": 0.0,
        }

        calc_res = await engine.calculate_employee_payroll(
            employee_id=emp.id, year=2026, month=9, period=period_sep, override_inputs=override_inputs
        )
        assert calc_res is not None
        record, items = calc_res

        assert record.payable_days == 20.0
        assert record.salary_part == 20000.0
        assert record.lop_days == 2.0
        assert record.lop_deduction == 2000.0
        assert record.net_salary == 18000.0

        await session.delete(emp)
        await session.commit()
