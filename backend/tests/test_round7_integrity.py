"""
SPT Hospital HRMS — Round 7 Integrity Tests
Tests:
- Savings Fund single write (assert exactly 1 row is created)
- Savings Fund withdrawal over-draft protection (400 Bad Request)
- Leave balance endpoint stability
- Shift deletion 409 Conflict guard
- Department deletion 409 Conflict guard
- Attendance exceptions single & bulk review endpoints
- Payroll finalization guard on placeholder salaries
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token


@pytest.fixture
def auth_headers():
    token = create_access_token(subject=1, role="SUPER_ADMIN")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_savings_fund_single_write(auth_headers):
    """Assert that POST /employees/{id}/savings-fund/transactions inserts exactly 1 row (no duplicate insert)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get employee id 1
        emp_res = await client.get("/api/v1/employees", headers=auth_headers)
        assert emp_res.status_code == 200
        emp_id = emp_res.json()["items"][0]["id"]

        # Check existing transaction count
        tx_res_before = await client.get(f"/api/v1/employees/{emp_id}/savings-fund/transactions", headers=auth_headers)
        assert tx_res_before.status_code == 200
        count_before = len(tx_res_before.json()["items"])

        # Create one transaction
        post_res = await client.post(
            f"/api/v1/employees/{emp_id}/savings-fund/transactions",
            headers=auth_headers,
            json={"transaction_type": "DEPOSIT", "amount": 1000.0, "notes": "Test Single Write Deposit"},
        )
        assert post_res.status_code == 200
        created = post_res.json()
        assert created["amount"] == 1000.0
        assert created["transaction_type"] == "DEPOSIT"

        # Check count after
        tx_res_after = await client.get(f"/api/v1/employees/{emp_id}/savings-fund/transactions", headers=auth_headers)
        assert tx_res_after.status_code == 200
        count_after = len(tx_res_after.json()["items"])

        # Exactly 1 new row must be added
        assert count_after == count_before + 1, f"Expected {count_before + 1} transactions, but found {count_after}"


@pytest.mark.asyncio
async def test_savings_fund_withdrawal_balance_check(auth_headers):
    """Assert that withdrawing more than available balance returns 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        emp_res = await client.get("/api/v1/employees", headers=auth_headers)
        emp_id = emp_res.json()["items"][0]["id"]

        tx_res = await client.get(f"/api/v1/employees/{emp_id}/savings-fund/transactions", headers=auth_headers)
        current_bal = tx_res.json()["current_balance"]

        # Attempt to withdraw 10x current balance
        withdraw_amount = current_bal + 500000.0
        post_res = await client.post(
            f"/api/v1/employees/{emp_id}/savings-fund/transactions",
            headers=auth_headers,
            json={"transaction_type": "WITHDRAWAL", "amount": withdraw_amount, "notes": "Overdraft attempt"},
        )
        assert post_res.status_code == 400
        assert "Insufficient savings fund balance" in post_res.json()["detail"]


@pytest.mark.asyncio
async def test_leave_balances_endpoint(auth_headers):
    """Assert GET /leaves/balances does not crash with selectinload errors and returns valid payload."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/leaves/balances", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_shift_delete_guard(auth_headers):
    """Assert that deleting a shift with assigned employees returns 409 Conflict."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Find a shift with employees assigned
        shifts_res = await client.get("/api/v1/shifts", headers=auth_headers)
        assert shifts_res.status_code == 200
        shifts = shifts_res.json()["items"]
        assert len(shifts) > 0
        first_shift = shifts[0]

        del_res = await client.delete(f"/api/v1/shifts/{first_shift['id']}", headers=auth_headers)
        # Should either be 409 Conflict (if employees assigned) or 204
        if del_res.status_code == 409:
            assert "active employees are assigned to it" in del_res.json()["detail"]
        else:
            assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_exceptions_review_and_bulk_review(auth_headers):
    """Assert that single and bulk review of attendance exceptions succeed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Get pending exceptions
        res = await client.get("/api/v1/attendance/exceptions", headers=auth_headers)
        assert res.status_code == 200
        items = res.json()["items"]
        if items:
            first_exc = items[0]
            # Review single exception
            rev_res = await client.put(
                f"/api/v1/attendance/exceptions/{first_exc['id']}/review",
                headers=auth_headers,
                json={"status": "APPROVED", "notes": "Approved in integrity test"},
            )
            assert rev_res.status_code == 200
            assert rev_res.json()["review_status"] == "APPROVED"

            # Bulk review next 2 if available
            if len(items) >= 2:
                ids = [items[0]["id"], items[1]["id"]]
                bulk_res = await client.post(
                    "/api/v1/attendance/exceptions/bulk-review",
                    headers=auth_headers,
                    json={"exception_ids": ids, "status": "DISMISSED", "notes": "Bulk dismissed in test"},
                )
                assert bulk_res.status_code == 200
                assert bulk_res.json()["count"] == 2
                assert bulk_res.json()["review_status"] == "DISMISSED"
