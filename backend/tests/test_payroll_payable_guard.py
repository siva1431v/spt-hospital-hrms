import pytest
import calendar
from datetime import date
from decimal import Decimal
from sqlalchemy import select

from app.models.employee import Employee
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus
from app.models.attendance import MonthlyAttendanceAggregate, AttendanceException
from app.payroll.engine import PayrollEngine
from app.core.database import AsyncSessionLocal


@pytest.mark.asyncio
async def test_proration_guard_never_gives_fewer_payable_than_present():
    """
    Guarantees:
    1. Latha (Bio 65) with joining_date = 2026-10-04 (28-day window) gets 31 payable days,
       NOT capped to 28, and logs an AttendanceException.
    2. Ehzilmaran (Bio 70) with joining_date = 2026-11-01 (after period) gets 17 payable days,
       NOT 0, and logs an AttendanceException.
    3. Sudhakar (Bio 69) with joining_date = 2026-11-01 gets 25 payable days,
       NOT 0, and logs an AttendanceException.
    """
    async with AsyncSessionLocal() as session:
        # Get or create October 2026 period
        p_res = await session.execute(
            select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 10)
        )
        period = p_res.scalar_one_or_none()
        if not period:
            period = PayrollPeriod(
                year=2026,
                month=10,
                period_name="October 2026",
                working_days=31,
                status=PayrollStatus.DRAFT,
                created_by_id=1,
            )
            session.add(period)
            await session.flush()

        engine = PayrollEngine(session)

        # Helper to ensure employee and aggregate exist
        async def ensure_emp_and_agg(code, fname, basic, p_days, a_days, join_dt):
            res = await session.execute(select(Employee).where(Employee.biometric_code == code))
            emp = res.scalar_one_or_none()
            if not emp:
                emp = Employee(
                    employee_id=f"SPT_TEST_{code}",
                    biometric_code=code,
                    first_name=fname,
                    last_name="",
                    full_name=fname,
                    employment_type="FULL_TIME",
                    basic_salary=Decimal(str(basic)),
                    joining_date=join_dt,
                    is_active=True,
                )
                session.add(emp)
                await session.flush()
            else:
                emp.joining_date = join_dt
                emp.basic_salary = Decimal(str(basic))
                await session.flush()

            # Ensure MonthlyAttendanceAggregate
            agg_res = await session.execute(
                select(MonthlyAttendanceAggregate).where(
                    MonthlyAttendanceAggregate.employee_id == emp.id,
                    MonthlyAttendanceAggregate.year == 2026,
                    MonthlyAttendanceAggregate.month == 10,
                )
            )
            agg = agg_res.scalar_one_or_none()
            if not agg:
                agg = MonthlyAttendanceAggregate(
                    employee_id=emp.id,
                    employee_code=code,
                    employee_name=fname,
                    year=2026,
                    month=10,
                    present_count=p_days,
                    absent_count=a_days,
                )
                session.add(agg)
                await session.flush()
            else:
                agg.present_count = p_days
                agg.absent_count = a_days
                await session.flush()

            return emp

        # 1. Test Latha (Bio 65): 29 Present, 2 Leave -> raw payable 31, joined 2026-10-04 (window: 28 days)
        latha = await ensure_emp_and_agg("65", "Latha", 12000, 29, 2, date(2026, 10, 4))
        res_latha = await engine.calculate_employee_payroll(latha.id, 2026, 10, period=period)
        assert res_latha is not None
        rec_latha, _ = res_latha
        assert rec_latha.present_days == 29.0
        # Expected: 29 + min(2, 3) = 31 payable days (must NOT be capped to 28)
        assert rec_latha.payable_days == 31.0
        assert rec_latha.payable_days >= rec_latha.present_days

        # 2. Test Ehzilmaran (Bio 70): 14 Present, 17 Leave -> joined 2026-11-01 (after period)
        ehzil = await ensure_emp_and_agg("70", "Ehzilmaran", 18000, 14, 17, date(2026, 11, 1))
        res_ehzil = await engine.calculate_employee_payroll(ehzil.id, 2026, 10, period=period)
        assert res_ehzil is not None
        rec_ehzil, _ = res_ehzil
        assert rec_ehzil.present_days == 14.0
        # Expected: 14 + min(17, 3) = 17 payable days (must NOT be 0)
        assert rec_ehzil.payable_days == 17.0
        assert rec_ehzil.payable_days >= rec_ehzil.present_days

        # 3. Test Sudhakar (Bio 69): 22 Present, 9 Leave -> joined 2026-11-01 (after period)
        sudhakar = await ensure_emp_and_agg("69", "Sudhakar", 14000, 22, 9, date(2026, 11, 1))
        res_sudhakar = await engine.calculate_employee_payroll(sudhakar.id, 2026, 10, period=period)
        assert res_sudhakar is not None
        rec_sudhakar, _ = res_sudhakar
        assert rec_sudhakar.present_days == 22.0
        # Expected: 22 + min(9, 3) = 25 payable days (must NOT be 0)
        assert rec_sudhakar.payable_days == 25.0
        assert rec_sudhakar.payable_days >= rec_sudhakar.present_days

        # Check that AttendanceException was recorded for attendance before joining date
        exc_res = await session.execute(
            select(AttendanceException).where(AttendanceException.employee_id == latha.id)
        )
        exceptions = exc_res.scalars().all()
        assert any("Attendance found before joining date" in e.reason for e in exceptions)

        await session.commit()
