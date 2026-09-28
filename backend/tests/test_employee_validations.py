"""
Tests for employee validations: phone numbers, basic_salary, security_fund_deduction
"""
import pytest
import httpx

from app.main import app
 
@pytest.mark.asyncio
async def test_employee_phone_and_salary_validation():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. Login as admin
        login_res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Test Invalid Phone (less than 10 digits)
        bad_phone_res = await client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "first_name": "Test",
                "last_name": "User",
                "employee_id": "TEST_VAL_1",
                "phone": "12345"
            }
        )
        assert bad_phone_res.status_code == 422

        # 3. Test Invalid Phone (letters)
        bad_phone_res2 = await client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "first_name": "Test",
                "last_name": "User",
                "employee_id": "TEST_VAL_2",
                "phone": "invalid_phone"
            }
        )
        assert bad_phone_res2.status_code == 422

        # 4. Test Negative Salary
        bad_sal_res = await client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "first_name": "Test",
                "last_name": "User",
                "employee_id": "TEST_VAL_3",
                "basic_salary": -5000
            }
        )
        assert bad_sal_res.status_code == 422

        # 5. Test Negative Security Fund Deduction
        bad_fund_res = await client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "first_name": "Test",
                "last_name": "User",
                "employee_id": "TEST_VAL_4",
                "security_fund_deduction": -100
            }
        )
        assert bad_fund_res.status_code == 422

        # 6. Test Valid Indian Mobile Numbers (with +91 and without)
        import uuid
        test_uid = f"TEST_VAL_{uuid.uuid4().hex[:6]}"
        good_emp_res = await client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "first_name": "Valid",
                "last_name": "User",
                "employee_id": test_uid,
                "phone": "+91 9876543210",
                "basic_salary": 25000,
                "security_fund_deduction": 500
            }
        )
        assert good_emp_res.status_code == 201
        created_id = good_emp_res.json()["id"]

        # 7. Test Creating Employee WITHOUT last_name (last_name is optional)
        test_uid_no_last = f"TEST_NOLAST_{uuid.uuid4().hex[:6]}"
        no_last_res = await client.post(
            "/api/v1/employees",
            headers=headers,
            json={
                "first_name": "SingleName",
                "employee_id": test_uid_no_last,
                "basic_salary": 20000,
            }
        )
        assert no_last_res.status_code == 201
        data = no_last_res.json()
        assert data["first_name"] == "SingleName"
        assert data["full_name"] == "SingleName"
        assert data["last_name"] in [None, ""]

        # Clean up test employees
        await client.delete(f"/api/v1/employees/{created_id}", headers=headers)
        await client.delete(f"/api/v1/employees/{data['id']}", headers=headers)
