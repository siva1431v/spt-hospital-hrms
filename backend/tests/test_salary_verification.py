"""
SPT Hospital HRMS — Salary Verification & Finalize Tests
Covers:
- finalize fails with HTTP 400 and full unverified_employees list when any active employee in period is unverified (salary_verified=False)
- finalize succeeds (HTTP 200) once all employees are verified (salary_verified=True)
- an employee with genuine ₹25,000 verified salary does NOT block finalization
"""
import pytest
import uuid
from datetime import date
import httpx
from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.payroll import (
    PayrollPeriod, PayrollRecord, PayrollStatus
)
from app.payroll.engine import PayrollEngine

from app.main import app


@pytest.mark.asyncio
async def test_salary_verification_finalize_flow():
    """
    Test that finalize fails with detailed unverified employees list when salary_verified=False,
    and succeeds once verified, even with basic_salary=25000.
    """
    async with AsyncSessionLocal() as session:
        # 1. Create a clean test period
        p_res = await session.execute(
            select(PayrollPeriod).where(PayrollPeriod.year == 2030, PayrollPeriod.month == 6)
        )
        period = p_res.scalar_one_or_none()
        if not period:
            period = PayrollPeriod(
                year=2030,
                month=6,
                period_name="June 2030",
                working_days=30,
                status=PayrollStatus.DRAFT,
                created_by_id=1,
            )
            session.add(period)
            await session.commit()
            await session.refresh(period)
        else:
            period.status = PayrollStatus.DRAFT
            await session.commit()
            await session.refresh(period)

        # 2. Create Employee A (genuine 25,000 verified salary)
        emp_a_code = f"TEST_VER_{uuid.uuid4().hex[:6]}"
        emp_a = Employee(
            employee_id=emp_a_code,
            biometric_code=f"{uuid.uuid4().int % 90000 + 10000}",
            first_name="Doctor",
            last_name="Verified",
            full_name="Doctor Verified",
            basic_salary=25000.0,
            salary_verified=True,
            salary_source="MIGRATED",
            is_active=True,
        )

        # 3. Create Employee B (placeholder 25,000 unverified salary)
        emp_b_code = f"TEST_UNVER_{uuid.uuid4().hex[:6]}"
        emp_b = Employee(
            employee_id=emp_b_code,
            biometric_code=f"{uuid.uuid4().int % 90000 + 10000}",
            first_name="Nurse",
            last_name="Unverified",
            full_name="Nurse Unverified",
            basic_salary=25000.0,
            salary_verified=False,
            salary_source="PLACEHOLDER",
            is_active=True,
        )
        session.add_all([emp_a, emp_b])
        await session.commit()
        await session.refresh(emp_a)
        await session.refresh(emp_b)

        # 4. Clear any old records in this test period and create payroll records for Employee A & B
        await session.execute(delete(PayrollRecord).where(PayrollRecord.period_id == period.id))
        engine = PayrollEngine(session)
        calc_a = await engine.calculate_employee_payroll(emp_a.id, 2030, 6, period=period)
        calc_b = await engine.calculate_employee_payroll(emp_b.id, 2030, 6, period=period)
        assert calc_a is not None
        assert calc_b is not None
        rec_a, _ = calc_a
        rec_b, _ = calc_b
        session.add_all([rec_a, rec_b])
        await session.commit()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 5. Attempt finalize -> must fail because Employee B is unverified
        fin_fail = await client.post(f"/api/v1/payroll/periods/{period.id}/finalize", headers=headers)
        assert fin_fail.status_code == 400
        detail = fin_fail.json()["detail"]
        assert "unverified_employees" in detail
        unverified_list = detail["unverified_employees"]
        assert len(unverified_list) == 1
        assert unverified_list[0]["employee_id"] == emp_b_code
        assert unverified_list[0]["name"] == "Nurse Unverified"
        assert unverified_list[0]["basic_salary"] == 25000.0

        # Note: Employee A (Doctor Verified, basic_salary=25000) is NOT in the block list!

        # 6. Verify Employee B via PUT /api/v1/employees/{id} with new salary
        update_res = await client.put(
            f"/api/v1/employees/{emp_b.id}",
            headers=headers,
            json={"basic_salary": 18000.0, "salary_verified": True}
        )
        assert update_res.status_code == 200
        assert update_res.json()["salary_verified"] is True
        assert update_res.json()["basic_salary"] == 18000.0

        # Recalculate employee B in period
        async with AsyncSessionLocal() as session:
            engine = PayrollEngine(session)
            p = await session.get(PayrollPeriod, period.id)
            res_b = await engine.calculate_employee_payroll(emp_b.id, 2030, 6, period=p)
            assert res_b is not None
            rec_b_new, _ = res_b
            res_rec = await session.execute(
                select(PayrollRecord).where(PayrollRecord.employee_id == emp_b.id, PayrollRecord.period_id == p.id)
            )
            existing_rec = res_rec.scalar_one()
            existing_rec.basic_salary = rec_b_new.basic_salary
            existing_rec.salary_part = rec_b_new.salary_part
            existing_rec.gross_salary = rec_b_new.gross_salary
            existing_rec.net_salary = rec_b_new.net_salary
            await session.commit()

        # 7. Finalize again -> must succeed now that all employees in this period are verified
        fin_success = await client.post(f"/api/v1/payroll/periods/{period.id}/finalize", headers=headers)
        assert fin_success.status_code == 200
        assert fin_success.json()["status"] == "FINALIZED"

    # Cleanup
    async with AsyncSessionLocal() as session:
        await session.execute(delete(PayrollRecord).where(PayrollRecord.period_id == period.id))
        p = await session.get(PayrollPeriod, period.id)
        if p:
            await session.delete(p)
        ea = await session.get(Employee, emp_a.id)
        eb = await session.get(Employee, emp_b.id)
        if ea:
            await session.delete(ea)
        if eb:
            await session.delete(eb)
        await session.commit()
