"""
Regression tests for FIX 4 (Auth) and FIX 5 (Input Validation).
Verifies:
- FIX 4:
  1. Requests with missing Authorization header return HTTP 401 with WWW-Authenticate: Bearer header.
  2. POST /api/v1/auth/refresh accepts JSON body {"refresh_token": "..."} and returns fresh tokens.
  3. POST /api/v1/auth/refresh with invalid token returns 401.
- FIX 5:
  1. GET /api/v1/attendance with month=13 returns HTTP 422.
  2. GET /api/v1/attendance with year=1999 returns HTTP 422.
  3. GET /api/v1/attendance/monthly with month=13 returns HTTP 422.
  4. GET /api/v1/attendance/lateness with month=13 returns HTTP 422.
  5. GET /api/v1/payroll/periods/lookup with month=13 returns HTTP 422.
  6. GET /api/v1/reports/salary-register with month=13 returns HTTP 422.
  7. GET /api/v1/dashboard/stats with month=13 returns HTTP 422.
"""
import pytest
import httpx
from app.main import app


@pytest.mark.asyncio
async def test_auth_missing_header_returns_401():
    """Verify that requests with no Authorization header return 401 (not 403) with WWW-Authenticate header."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/employees")
        assert res.status_code == 401
        assert "bearer" in res.headers.get("www-authenticate", "").lower()


@pytest.mark.asyncio
async def test_auth_refresh_json_body():
    """Verify that POST /auth/refresh accepts JSON body {"refresh_token": "..."}."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Login to obtain a valid refresh token
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert login_res.status_code == 200
        data = login_res.json()
        refresh_token = data["refresh_token"]

        # 2. Call /auth/refresh with JSON payload
        refresh_res = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert refresh_res.status_code == 200
        new_data = refresh_res.json()
        assert "access_token" in new_data
        assert "refresh_token" in new_data
        assert new_data["token_type"].lower() == "bearer"

        # 3. Invalid refresh token returns 401
        bad_res = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.jwt.token"}
        )
        assert bad_res.status_code == 401


@pytest.mark.asyncio
async def test_input_validation_month_and_year_bounds():
    """Verify that endpoints with month/year bounds reject invalid values with 422."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. GET /api/v1/attendance?month=13 -> 422
        res1 = await client.get("/api/v1/attendance?month=13", headers=headers)
        assert res1.status_code == 422

        # 2. GET /api/v1/attendance?year=1999 -> 422
        res2 = await client.get("/api/v1/attendance?year=1999", headers=headers)
        assert res2.status_code == 422

        # 3. GET /api/v1/attendance/monthly?year=2026&month=13 -> 422
        res3 = await client.get("/api/v1/attendance/monthly?year=2026&month=13", headers=headers)
        assert res3.status_code == 422

        # 4. GET /api/v1/attendance/lateness?year=2026&month=0 -> 422
        res4 = await client.get("/api/v1/attendance/lateness?year=2026&month=0", headers=headers)
        assert res4.status_code == 422

        # 5. GET /api/v1/payroll/periods/lookup?year=2026&month=13 -> 422
        res5 = await client.get("/api/v1/payroll/periods/lookup?year=2026&month=13", headers=headers)
        assert res5.status_code == 422

        # 6. GET /api/v1/reports/salary-register?month=14 -> 422
        res6 = await client.get("/api/v1/reports/salary-register?month=14", headers=headers)
        assert res6.status_code == 422

        # 7. GET /api/v1/dashboard/stats?month=13 -> 422
        res7 = await client.get("/api/v1/dashboard/stats?month=13", headers=headers)
        assert res7.status_code == 422


@pytest.mark.asyncio
async def test_delete_user_endpoint():
    """Verify DELETE /users/{id} restrictions and successful deletion."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Login as admin
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert login_res.status_code == 200
        admin_data = login_res.json()
        token = admin_data["access_token"]
        admin_id = admin_data["user"]["id"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Self deletion blocked
        self_del = await client.delete(f"/api/v1/users/{admin_id}", headers=headers)
        assert self_del.status_code == 400
        assert "cannot delete your own" in self_del.json()["detail"].lower()

        # 2. Create a temporary user
        create_res = await client.post(
            "/api/v1/users",
            json={
                "username": "temp_user_test",
                "email": "temp_user_test@spthospital.com",
                "full_name": "Temporary Test User",
                "password": "Password@123",
                "role": "EMPLOYEE",
                "is_active": True,
            },
            headers=headers,
        )
        assert create_res.status_code == 200
        new_user_id = create_res.json()["id"]

        # 3. Delete the temporary user
        del_res = await client.delete(f"/api/v1/users/{new_user_id}", headers=headers)
        assert del_res.status_code == 200
        assert "deleted successfully" in del_res.json()["message"]

        # 4. Deleting non-existent user returns 404
        not_found_res = await client.delete(f"/api/v1/users/{new_user_id}", headers=headers)
        assert not_found_res.status_code == 404

