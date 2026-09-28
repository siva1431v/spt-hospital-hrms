"""
Tests for month and year filtering in reports endpoints:
- GET /api/v1/reports/attendance
- GET /api/v1/reports/missing-punch
- GET /api/v1/reports/overtime

Verifies:
1. When year=2026&month=7 is requested, reports contain 0 rows from August 2026 (all rows are July 2026 or empty).
2. When year=2026&month=8 is requested, returned rows are strictly in August 2026.
3. Explicit date_from and date_to take priority over month/year.
4. Validation constraints on month (1-12) and year (2020-2050).
"""
import pytest
import httpx
from app.main import app


@pytest.mark.asyncio
async def test_reports_july_2026_contains_no_august_rows():
    """Export July 2026 for attendance, missing-punch, and overtime; assert no August rows exist."""
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

        # 2. Query August 2026 attendance to confirm August data exists in DB
        res_aug = await client.get("/api/v1/reports/attendance?year=2026&month=8", headers=headers)
        assert res_aug.status_code == 200
        aug_data = res_aug.json().get("data", [])
        # Confirm that August records actually exist in the test DB
        assert len(aug_data) > 0, "Expected August 2026 attendance records to exist in the database"
        for rec in aug_data:
            assert rec["date"].startswith("2026-08")

        # 3. Query July 2026 attendance
        res_att_july = await client.get("/api/v1/reports/attendance?year=2026&month=7", headers=headers)
        assert res_att_july.status_code == 200
        july_att_data = res_att_july.json().get("data", [])
        # Assert contains NO August rows
        for rec in july_att_data:
            assert not rec["date"].startswith("2026-08"), f"Found August row in July export: {rec}"
            assert rec["date"].startswith("2026-07")

        # 4. Query July 2026 missing-punch
        res_mp_july = await client.get("/api/v1/reports/missing-punch?year=2026&month=7", headers=headers)
        assert res_mp_july.status_code == 200
        july_mp_data = res_mp_july.json().get("data", [])
        for rec in july_mp_data:
            assert not rec["date"].startswith("2026-08"), f"Found August row in July missing-punch export: {rec}"
            assert rec["date"].startswith("2026-07")

        # 5. Query July 2026 overtime
        res_ot_july = await client.get("/api/v1/reports/overtime?year=2026&month=7", headers=headers)
        assert res_ot_july.status_code == 200
        july_ot_data = res_ot_july.json().get("data", [])
        for rec in july_ot_data:
            assert not rec["date"].startswith("2026-08"), f"Found August row in July overtime export: {rec}"
            assert rec["date"].startswith("2026-07")


@pytest.mark.asyncio
async def test_reports_explicit_date_range_takes_priority_over_month_year():
    """Explicit date_from / date_to override the month/year bounds."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Request August 2026 (month=8, year=2026) but with explicit 3-day window: 2026-08-05 to 2026-08-07
        res = await client.get(
            "/api/v1/reports/attendance?year=2026&month=8&date_from=2026-08-05&date_to=2026-08-07",
            headers=headers
        )
        assert res.status_code == 200
        data = res.json().get("data", [])
        for rec in data:
            assert "2026-08-05" <= rec["date"] <= "2026-08-07"


@pytest.mark.asyncio
async def test_reports_month_year_validation():
    """Verify validation on month (1-12) and year (2020-2050)."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # month=13 -> 422
        res = await client.get("/api/v1/reports/attendance?year=2026&month=13", headers=headers)
        assert res.status_code == 422

        # month=0 -> 422
        res = await client.get("/api/v1/reports/attendance?year=2026&month=0", headers=headers)
        assert res.status_code == 422

        # year=1999 -> 422
        res = await client.get("/api/v1/reports/attendance?year=1999&month=8", headers=headers)
        assert res.status_code == 422

        # year=2051 -> 422
        res = await client.get("/api/v1/reports/attendance?year=2051&month=8", headers=headers)
        assert res.status_code == 422
