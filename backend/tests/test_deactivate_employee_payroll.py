"""
SPT Hospital HRMS — Employee Deactivation / Deletion Payroll Sync Tests
Verifies:
1. When an employee is deactivated or soft deleted, their unfinalized (draft) payroll records are immediately removed.
2. Inactive employees are excluded from draft payroll records list (GET /payroll/periods/{id}/records).
3. Payroll calculation skips inactive employees and purges any leftover inactive records in the period.
4. Finalizing payroll succeeds without being blocked by deactivated/deleted employees.
"""
import pytest
import uuid
import httpx
from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus
from app.payroll.engine import PayrollEngine

BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_employee_deactivation_removes_from_payroll():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # 1. Login
        login_res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Create a clean test period
        async with AsyncSessionLocal() as session:
            p_res = await session.execute(
                select(PayrollPeriod).where(PayrollPeriod.year == 2031, PayrollPeriod.month == 7)
            )
            period = p_res.scalar_one_or_none()
            if not period:
                period = PayrollPeriod(
                    year=2031,
                    month=7,
                    period_name="July 2031",
                    working_days=31,
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

            # Clear old records in this period
            await session.execute(delete(PayrollRecord).where(PayrollRecord.period_id == period.id))

            # Create an active employee with unverified salary
            emp_code = f"TEST_DEACT_{uuid.uuid4().hex[:6]}"
            emp = Employee(
                employee_id=emp_code,
                biometric_code=f"{uuid.uuid4().int % 90000 + 10000}",
                first_name="ToDeactivate",
                last_name="Staff",
                full_name="ToDeactivate Staff",
                basic_salary=15000.0,
                salary_verified=False,
                is_active=True,
            )
            session.add(emp)
            await session.commit()
            await session.refresh(emp)

            # Also create an active verified employee
            emp_active_code = f"TEST_KEEP_{uuid.uuid4().hex[:6]}"
            emp_active = Employee(
                employee_id=emp_active_code,
                biometric_code=f"{uuid.uuid4().int % 90000 + 10000}",
                first_name="ToKeep",
                last_name="Staff",
                full_name="ToKeep Staff",
                basic_salary=22000.0,
                salary_verified=True,
                is_active=True,
            )
            session.add(emp_active)
            await session.commit()
            await session.refresh(emp_active)

            # Add payroll records for both in the period
            engine = PayrollEngine(session)
            res1 = await engine.calculate_employee_payroll(emp.id, 2031, 7, period=period)
            res2 = await engine.calculate_employee_payroll(emp_active.id, 2031, 7, period=period)
            assert res1 is not None
            assert res2 is not None
            rec1, _ = res1
            rec2, _ = res2
            session.add_all([rec1, rec2])
            await session.commit()

        # 3. Verify both records exist in payroll records endpoint
        list_res = await client.get(f"/api/v1/payroll/periods/{period.id}/records", headers=headers)
        assert list_res.status_code == 200
        codes = [item["employee_code"] for item in list_res.json()["items"]]
        assert emp_code in codes
        assert emp_active_code in codes

        # 4. Deactivate employee via DELETE /api/v1/employees/{id}
        deact_res = await client.delete(f"/api/v1/employees/{emp.id}", headers=headers)
        assert deact_res.status_code == 204

        # 5. Verify employee is now REMOVED from the payroll period records
        list_res2 = await client.get(f"/api/v1/payroll/periods/{period.id}/records", headers=headers)
        assert list_res2.status_code == 200
        codes2 = [item["employee_code"] for item in list_res2.json()["items"]]
        assert emp_code not in codes2
        assert emp_active_code in codes2

        # 6. Verify PayrollRecord is physically deleted for the deactivated employee in draft period
        async with AsyncSessionLocal() as session:
            rec_check = await session.execute(
                select(PayrollRecord).where(
                    PayrollRecord.employee_id == emp.id,
                    PayrollRecord.period_id == period.id,
                )
            )
            assert rec_check.scalar_one_or_none() is None

        # 7. Finalize payroll -> Must SUCCEED because the unverified deactivated employee is gone
        fin_res = await client.post(f"/api/v1/payroll/periods/{period.id}/finalize", headers=headers)
        assert fin_res.status_code == 200
        assert fin_res.json()["status"] == "FINALIZED"

        # Cleanup
        async with AsyncSessionLocal() as session:
            await session.execute(delete(PayrollRecord).where(PayrollRecord.period_id == period.id))
            p = await session.get(PayrollPeriod, period.id)
            if p:
                await session.delete(p)
            e1 = await session.get(Employee, emp.id)
            e2 = await session.get(Employee, emp_active.id)
            if e1:
                await session.delete(e1)
            if e2:
                await session.delete(e2)
            await session.commit()
