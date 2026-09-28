"""
Regression test for FIX 1 (P0): Lateness breakdown endpoint.
Verifies that GET /api/v1/payroll/records/{record_id}/lateness-breakdown
does not crash (500 MissingGreenlet) for any employee, including those with
assigned shifts and those without.
"""
import pytest
import httpx
from sqlalchemy import select
from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus
from app.models.shift import Shift


@pytest.mark.asyncio
async def test_lateness_breakdown_all_records():
    """Verify that lateness-breakdown returns 200 for all calculated payroll records."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login as admin
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Ensure at least one employee has a shift and at least one has no shift
        async with AsyncSessionLocal() as session:
            shifts = (await session.execute(select(Shift))).scalars().all()
            assert len(shifts) > 0, "Expected at least one shift in seeded database"
            test_shift = shifts[0]

            employees = (await session.execute(select(Employee).where(Employee.is_active == True))).scalars().all()
            assert len(employees) >= 2, "Expected at least 2 active employees"

            # Assign shift to first employee
            employees[0].shift_id = test_shift.id
            # Ensure second employee has no shift
            employees[1].shift_id = None
            await session.commit()

        # 3. Calculate payroll for 2026-08
        calc_res = await client.post(
            "/api/v1/payroll/periods/calculate",
            headers=headers,
            json={"year": 2026, "month": 8}
        )
        assert calc_res.status_code == 200
        period_data = calc_res.json()["period"]
        period_id = period_data["id"]

        # 4. Fetch all records for the period
        records_res = await client.get(
            f"/api/v1/payroll/periods/{period_id}/records",
            headers=headers
        )
        assert records_res.status_code == 200
        records = records_res.json()["items"]
        assert len(records) > 0, "Expected payroll records to be generated"

        # 5. Call lateness-breakdown for EVERY record and assert 200
        for rec in records:
            rec_id = rec["id"]
            breakdown_res = await client.get(
                f"/api/v1/payroll/records/{rec_id}/lateness-breakdown",
                headers=headers
            )
            assert breakdown_res.status_code == 200, (
                f"Lateness breakdown failed with status {breakdown_res.status_code}: {breakdown_res.text}"
            )
            data = breakdown_res.json()
            assert "qualifying_late_days" in data
            assert "lop_days" in data
            assert "late_arrivals" in data
            assert "grace_minutes" in data
            assert isinstance(data["late_arrivals"], list)
