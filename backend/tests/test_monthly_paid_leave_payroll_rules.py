"""
SPT Hospital HRMS — Monthly Paid Leave and Dynamic Month Length Payroll Tests

Verifies all rules:
1. First 3 leave days in any month are 100% PAID (generate ZERO salary deduction).
2. Any leave days taken beyond 3 are UNPAID / LOP (deducted as: (leave_days - 3) * per_day_salary).
3. Per-day salary is dynamically computed based on days in the selected month:
   - 28-day months (e.g. February 2027)
   - 29-day leap February (e.g. February 2028)
   - 30-day months (e.g. April 2026, September 2026, November 2026)
   - 31-day months (e.g. January 2026, August 2026, October 2026)
4. Lateness LOP (floor(qualifying_late / 3)) combines with unpaid leave without double-counting.
5. Savings fund and collection apply correctly.
6. Manual edit override recalculates consistently.
"""
import calendar
import pytest
import uuid
import random
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.employee import Employee, EmploymentType
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus
from app.payroll.engine import PayrollEngine


@pytest.mark.parametrize(
    "year,month,days_in_month,base_salary,present,leave,expected_paid_leave,expected_unpaid_leave,expected_payable,expected_salary_part,expected_net",
    [
        # 30-day month, ₹30,000 base salary (per_day = ₹1,000)
        (2026, 9, 30, 30000.0, 30.0, 0.0, 0.0, 0.0, 30.0, 30000.0, 30000.0), # 0 leave -> full salary
        (2026, 9, 30, 30000.0, 29.0, 1.0, 1.0, 0.0, 30.0, 30000.0, 30000.0), # 1 leave -> full salary
        (2026, 9, 30, 30000.0, 28.0, 2.0, 2.0, 0.0, 30.0, 30000.0, 30000.0), # 2 leave -> full salary
        (2026, 9, 30, 30000.0, 27.0, 3.0, 3.0, 0.0, 30.0, 30000.0, 30000.0), # 3 leave -> full salary
        (2026, 9, 30, 30000.0, 26.0, 4.0, 3.0, 1.0, 29.0, 29000.0, 29000.0), # 4 leave -> 1 unpaid day deducted (₹1,000)
        (2026, 9, 30, 30000.0, 25.0, 5.0, 3.0, 2.0, 28.0, 28000.0, 28000.0), # 5 leave -> 2 unpaid days deducted (₹2,000)
        (2026, 9, 30, 30000.0, 20.0, 10.0, 3.0, 7.0, 23.0, 23000.0, 23000.0), # 10 leave -> 7 unpaid days deducted (₹7,000)

        # 31-day month, ₹31,000 base salary (per_day = ₹1,000)
        (2026, 1, 31, 31000.0, 31.0, 0.0, 0.0, 0.0, 31.0, 31000.0, 31000.0), # 0 leave -> full salary
        (2026, 1, 31, 31000.0, 30.0, 1.0, 1.0, 0.0, 31.0, 31000.0, 31000.0), # 1 leave -> full salary
        (2026, 1, 31, 31000.0, 29.0, 2.0, 2.0, 0.0, 31.0, 31000.0, 31000.0), # 2 leave -> full salary
        (2026, 1, 31, 31000.0, 28.0, 3.0, 3.0, 0.0, 31.0, 31000.0, 31000.0), # 3 leave -> full salary
        (2026, 1, 31, 31000.0, 27.0, 4.0, 3.0, 1.0, 30.0, 30000.0, 30000.0), # 4 leave -> 1 unpaid day deducted (₹1,000)
        (2026, 1, 31, 31000.0, 26.0, 5.0, 3.0, 2.0, 29.0, 29000.0, 29000.0), # 5 leave -> 2 unpaid days deducted (₹2,000)

        # 28-day month (Feb 2027), ₹28,000 base salary (per_day = ₹1,000)
        (2027, 2, 28, 28000.0, 28.0, 0.0, 0.0, 0.0, 28.0, 28000.0, 28000.0), # 0 leave -> full salary
        (2027, 2, 28, 28000.0, 25.0, 3.0, 3.0, 0.0, 28.0, 28000.0, 28000.0), # 3 leave -> full salary
        (2027, 2, 28, 28000.0, 24.0, 4.0, 3.0, 1.0, 27.0, 27000.0, 27000.0), # 4 leave -> 1 unpaid day deducted (₹1,000)
        (2027, 2, 28, 28000.0, 23.0, 5.0, 3.0, 2.0, 26.0, 26000.0, 26000.0), # 5 leave -> 2 unpaid days deducted (₹2,000)

        # 29-day leap year month (Feb 2028), ₹29,000 base salary (per_day = ₹1,000)
        (2028, 2, 29, 29000.0, 29.0, 0.0, 0.0, 0.0, 29.0, 29000.0, 29000.0), # 0 leave -> full salary
        (2028, 2, 29, 29000.0, 26.0, 3.0, 3.0, 0.0, 29.0, 29000.0, 29000.0), # 3 leave -> full salary
        (2028, 2, 29, 29000.0, 25.0, 4.0, 3.0, 1.0, 28.0, 28000.0, 28000.0), # 4 leave -> 1 unpaid day deducted (₹1,000)
        (2028, 2, 29, 29000.0, 24.0, 5.0, 3.0, 2.0, 27.0, 27000.0, 27000.0), # 5 leave -> 2 unpaid days deducted (₹2,000)
    ]
)
@pytest.mark.asyncio
async def test_paid_leave_and_dynamic_month_lengths(
    year, month, days_in_month, base_salary, present, leave,
    expected_paid_leave, expected_unpaid_leave, expected_payable, expected_salary_part, expected_net
):
    """Test all leave edge cases (0, 1, 2, 3, 4, 5, 10) across 28, 29, 30, and 31 day months."""
    assert calendar.monthrange(year, month)[1] == days_in_month

    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)

        # Create or find period
        p_res = await session.execute(
            select(PayrollPeriod).where(PayrollPeriod.year == year, PayrollPeriod.month == month)
        )
        period = p_res.scalar_one_or_none()
        if not period:
            period = PayrollPeriod(
                year=year,
                month=month,
                period_name=f"{calendar.month_name[month]} {year}",
                working_days=days_in_month,
                status=PayrollStatus.DRAFT,
                created_by_id=1,
            )
            session.add(period)
            await session.flush()

        rand_code = f"TEST_LV_{uuid.uuid4().hex[:6]}"
        emp = Employee(
            employee_id=rand_code,
            biometric_code=f"{random.randint(10000, 99999)}",
            first_name="LeaveTest",
            last_name="Staff",
            full_name="LeaveTest Staff",
            email=f"{rand_code.lower()}@spthospital.com",
            employment_type=EmploymentType.FULL_TIME,
            basic_salary=base_salary,
            security_fund_deduction=0.0,
            is_active=True
        )
        session.add(emp)
        await session.flush()

        override_inputs = {
            "present_days": present,
            "half_days": 0.0,
            "leave_days": leave,
            "off_duty_days": 0.0,
            "qualifying_late_days": 0,
            "lop_days": 0.0,
            "collection": 0.0,
        }

        calc_res = await engine.calculate_employee_payroll(
            employee_id=emp.id, year=year, month=month, period=period, override_inputs=override_inputs
        )
        assert calc_res is not None
        record, items = calc_res

        assert record.total_working_days == days_in_month
        assert record.paid_leave_days == expected_paid_leave
        assert record.payable_days == expected_payable
        assert record.salary_part == expected_salary_part
        assert record.net_salary == expected_net

        # Clean up
        await session.delete(emp)
        await session.commit()


@pytest.mark.asyncio
async def test_combined_lateness_lop_and_leave_deductions():
    """
    Test an employee who has:
    - Base Salary: ₹30,000 (30-day month -> ₹1,000/day)
    - 25 Present Days, 5 Leave Days (3 paid, 2 unpaid leave -> ₹2,000 deduction)
    - 6 Late Arrivals -> 2 Lateness LOP Days (floor(6/3) = 2 -> ₹2,000 deduction)
    - Collection: +₹500
    - Savings Fund: -₹1,000
    Total expected Net Salary:
      Salary Part: 28 * 1,000 = ₹28,000
      Collection: +₹500 -> Gross = ₹28,500
      LOP Ded: 2 * 1,000 = ₹2,000
      Savings Fund: ₹1,000
      Total Deductions = ₹3,000
      Net Salary = 28,500 - 3,000 = ₹25,500
    """
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)

        rand_code = f"TEST_COMB_{uuid.uuid4().hex[:6]}"
        emp = Employee(
            employee_id=rand_code,
            biometric_code=f"{random.randint(10000, 99999)}",
            first_name="Combined",
            last_name="Test",
            full_name="Combined Test",
            email=f"{rand_code.lower()}@spthospital.com",
            employment_type=EmploymentType.FULL_TIME,
            basic_salary=30000.0,
            security_fund_deduction=1000.0,
            is_active=True
        )
        session.add(emp)
        await session.flush()

        p_res = await session.execute(
            select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 9)
        )
        period = p_res.scalar_one_or_none()
        if not period:
            period = PayrollPeriod(year=2026, month=9, period_name="September 2026", working_days=30, status=PayrollStatus.DRAFT, created_by_id=1)
            session.add(period)
            await session.flush()

        override_inputs = {
            "present_days": 25.0,
            "half_days": 0.0,
            "leave_days": 5.0,
            "off_duty_days": 0.0,
            "qualifying_late_days": 6,
            "lop_days": 2.0,
            "collection": 500.0,
        }

        calc_res = await engine.calculate_employee_payroll(
            employee_id=emp.id, year=2026, month=9, period=period, override_inputs=override_inputs
        )
        assert calc_res is not None
        record, items = calc_res

        assert record.paid_leave_days == 3.0
        assert record.payable_days == 28.0
        assert record.salary_part == 28000.0
        assert record.gross_salary == 28500.0
        assert record.lop_days == 2.0
        assert record.lop_deduction == 2000.0
        assert record.security_fund_deduction == 1000.0
        assert record.total_deductions == 3000.0
        assert record.net_salary == 25500.0

        await session.delete(emp)
        await session.commit()
