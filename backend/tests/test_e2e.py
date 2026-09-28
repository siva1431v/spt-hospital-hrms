import asyncio
import httpx
import pytest

from app.main import app

@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify that the health check endpoint returns 200 OK and healthy status."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["app"] == "SPT Hospital HRMS"

@pytest.mark.asyncio
async def test_invalid_login():
    """Verify login failure with incorrect credentials."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong_password"}
        )
        assert response.status_code == 401
        assert "detail" in response.json()

@pytest.mark.asyncio
async def test_admin_login_and_me():
    """Verify login success and the /me profile retrieval with the generated token."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        assert login_data["user"]["role"] == "SUPER_ADMIN"

        token = login_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get Profile
        me_response = await client.get("/api/v1/auth/me", headers=headers)
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["username"] == "admin"
        assert me_data["role"] == "SUPER_ADMIN"

@pytest.mark.asyncio
async def test_employee_crud():
    """Verify that a SUPER_ADMIN can create and query employees."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Login
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        import random
        emp_code = f"TEST_EMP_{random.randint(100, 9999)}"
        bio_code = str(random.randint(100, 9999))
        new_employee = {
            "first_name": "Test",
            "last_name": "Nurse",
            "employee_id": emp_code,
            "biometric_code": bio_code,
            "gender": "FEMALE",
            "phone": "9999999999",
            "email": "testnurse@spthospital.com",
            "employment_type": "FULL_TIME",
            "basic_salary": 30000,
        }
        create_res = await client.post("/api/v1/employees", json=new_employee, headers=headers)
        assert create_res.status_code == 201
        created_data = create_res.json()
        assert created_data["first_name"] == "Test"
        emp_id = created_data["id"]

        # Get Employee Detail
        get_res = await client.get(f"/api/v1/employees/{emp_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["employee_id"] == emp_code

        # List Employees with search filter
        list_res = await client.get(f"/api/v1/employees?search={emp_code}", headers=headers)
        assert list_res.status_code == 200
        items = list_res.json()["items"]
        assert len(items) >= 1
        assert any(i["employee_id"] == emp_code for i in items)

        # Clean up (Soft Delete)
        del_res = await client.delete(f"/api/v1/employees/{emp_id}", headers=headers)
        assert del_res.status_code == 204

@pytest.mark.asyncio
async def test_departments_and_shifts():
    """Verify querying list of departments and shifts."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        login_response = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"}
        )
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Check Departments
        dept_res = await client.get("/api/v1/departments", headers=headers)
        assert dept_res.status_code == 200
        assert len(dept_res.json()["items"]) > 0

        # Check Shifts
        shift_res = await client.get("/api/v1/shifts", headers=headers)
        assert shift_res.status_code == 200
        assert len(shift_res.json()["items"]) > 0
