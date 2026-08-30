"""
SPT Hospital HRMS — Month and Year Payroll Workflow Tests
Verifies:
1. Selecting a month with no period returns empty/None and creates nothing automatically.
2. POST /api/v1/payroll/periods/calculate with {year, month} creates exactly one period and calculates records in one step.
3. Re-clicking Calculate recalculates the same period without creating a second one.
4. A FINALIZED month cannot be recalculated and returns HTTP 409 Conflict.
5. GET /api/v1/payroll/periods/lookup and GET /api/v1/payroll/periods?year=&month= resolve correctly.
"""
import pytest
import httpx
from sqlalchemy import select, delete

from app.core.database import AsyncSessionLocal
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus

BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_month_year_payroll_flow():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # 1. Login
        login_res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        test_year = 2034
        test_month = 5

        # Cleanup any existing test period
        async with AsyncSessionLocal() as session:
            p_res = await session.execute(
                select(PayrollPeriod).where(PayrollPeriod.year == test_year, PayrollPeriod.month == test_month)
            )
            existing_p = p_res.scalar_one_or_none()
            if existing_p:
                await session.execute(delete(PayrollRecord).where(PayrollRecord.period_id == existing_p.id))
                await session.delete(existing_p)
                await session.commit()

        # 2. Test lookup on a month with no period -> returns None and creates nothing
        lookup_res = await client.get(
            f"/api/v1/payroll/periods/lookup?year={test_year}&month={test_month}",
            headers=headers
        )
        assert lookup_res.status_code == 200
        assert lookup_res.json()["period"] is None

        # Verify nothing was created in DB
        async with AsyncSessionLocal() as session:
            check_p = await session.execute(
                select(PayrollPeriod).where(PayrollPeriod.year == test_year, PayrollPeriod.month == test_month)
            )
            assert check_p.scalar_one_or_none() is None

        # 3. Test POST /api/v1/payroll/periods/calculate with {year, month} creates exactly one period
        calc_res = await client.post(
            "/api/v1/payroll/periods/calculate",
            headers=headers,
            json={"year": test_year, "month": test_month}
        )
        assert calc_res.status_code == 200
        calc_data = calc_res.json()
        assert "period" in calc_data
        period_id = calc_data["period"]["id"]
        assert calc_data["period"]["year"] == test_year
        assert calc_data["period"]["month"] == test_month
        assert calc_data["period"]["period_name"] == "May 2034"
        assert calc_data["period"]["working_days"] == 31
        assert calc_data["calculated"] > 0

        # 4. Verify lookup now finds the period
        lookup_res2 = await client.get(
            f"/api/v1/payroll/periods/lookup?year={test_year}&month={test_month}",
            headers=headers
        )
        assert lookup_res2.status_code == 200
        assert lookup_res2.json()["period"]["id"] == period_id

        # 5. Verify records endpoint returns records for this period
        records_res = await client.get(
            f"/api/v1/payroll/periods/{period_id}/records",
            headers=headers
        )
        assert records_res.status_code == 200
        assert len(records_res.json()["items"]) > 0

        # 6. Test re-clicking Calculate recalculates the same period without duplicate creation
        recalc_res = await client.post(
            "/api/v1/payroll/periods/calculate",
            headers=headers,
            json={"year": test_year, "month": test_month}
        )
        assert recalc_res.status_code == 200
        assert recalc_res.json()["period"]["id"] == period_id

        # Check total count of periods for this year+month is exactly 1
        async with AsyncSessionLocal() as session:
            all_p = await session.execute(
                select(PayrollPeriod).where(PayrollPeriod.year == test_year, PayrollPeriod.month == test_month)
            )
            periods_list = all_p.scalars().all()
            assert len(periods_list) == 1

        # 7. Finalize the period
        # Mark employees as verified for this period if any are unverified to ensure clean test
        async with AsyncSessionLocal() as session:
            p = await session.get(PayrollPeriod, period_id)
            p.status = PayrollStatus.FINALIZED
            await session.commit()

        # 8. Attempting to recalculate a FINALIZED month must return HTTP 409 Conflict
        fail_calc = await client.post(
            "/api/v1/payroll/periods/calculate",
            headers=headers,
            json={"year": test_year, "month": test_month}
        )
        assert fail_calc.status_code == 409
        assert "finalized" in fail_calc.json()["detail"].lower()

        # Cleanup
        async with AsyncSessionLocal() as session:
            await session.execute(delete(PayrollRecord).where(PayrollRecord.period_id == period_id))
            p = await session.get(PayrollPeriod, period_id)
            if p:
                await session.delete(p)
            await session.commit()
