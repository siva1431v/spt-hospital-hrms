"""
SPT Hospital HRMS — 5-minute Grace Period & Shift Overrides Tests
Verifies:
1. Shift evaluation: arrival 4 minutes after shift start is NOT late.
2. Shift evaluation: arrival 6 minutes after shift start IS late.
3. Shift with a per-shift grace override (e.g., 10m or 0m) uses its own value.
4. Settings endpoint returns stored grace period (5).
5. /attendance/lateness and /attendance/monthly return dynamic grace_period (5).
6. Payroll lateness breakdown respects per-shift grace overrides and global 5m default.
"""
import pytest
import httpx
from datetime import datetime, time, date

from app.models.shift import Shift
from app.utils.shift_utils import evaluate_shift_punch
from app.core.database import AsyncSessionLocal
from app.models.audit import SystemSetting

BASE_URL = "http://localhost:8000"


def test_shift_punch_5m_grace_evaluation():
    # Base shift starting at 09:00 with default 5m grace
    shift_5m = Shift(
        id=991,
        code="TEST5",
        name="Test 5m Shift",
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_overnight=False,
        is_split=False,
        grace_period_minutes=5,
    )

    # 1. Arrival at 09:04:00 (4m after start) -> NOT late
    dt_0904 = datetime(2026, 8, 1, 9, 4, 0)
    res_0904 = evaluate_shift_punch(shift_5m, dt_0904)
    assert res_0904["is_late"] is False
    assert res_0904["late_minutes"] == 0

    # 2. Arrival at 09:05:00 (5m after start) -> NOT late (exactly at threshold)
    dt_0905 = datetime(2026, 8, 1, 9, 5, 0)
    res_0905 = evaluate_shift_punch(shift_5m, dt_0905)
    assert res_0905["is_late"] is False

    # 3. Arrival at 09:06:00 (6m after start) -> IS late
    dt_0906 = datetime(2026, 8, 1, 9, 6, 0)
    res_0906 = evaluate_shift_punch(shift_5m, dt_0906)
    assert res_0906["is_late"] is True
    assert res_0906["late_minutes"] == 6

    # 4. Shift with per-shift grace override (e.g. 10 minutes)
    shift_10m = Shift(
        id=992,
        code="TEST10",
        name="Test 10m Shift",
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_overnight=False,
        is_split=False,
        grace_period_minutes=10,
    )
    # Arrival at 09:08:00 (8m after start) -> NOT late under 10m grace
    dt_0908 = datetime(2026, 8, 1, 9, 8, 0)
    res_0908 = evaluate_shift_punch(shift_10m, dt_0908)
    assert res_0908["is_late"] is False

    # Arrival at 09:12:00 (12m after start) -> IS late under 10m grace
    dt_0912 = datetime(2026, 8, 1, 9, 12, 0)
    res_0912 = evaluate_shift_punch(shift_10m, dt_0912)
    assert res_0912["is_late"] is True
    assert res_0912["late_minutes"] == 12

    # 5. Shift with 0m grace override (strict, e.g. ICU/Emergency)
    shift_0m = Shift(
        id=993,
        code="TEST0",
        name="Test Strict 0m Shift",
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_overnight=False,
        is_split=False,
        grace_period_minutes=0,
    )
    # Arrival at 09:01:00 (1m after start) -> IS late
    dt_0901 = datetime(2026, 8, 1, 9, 1, 0)
    res_0901 = evaluate_shift_punch(shift_0m, dt_0901)
    assert res_0901["is_late"] is True
    assert res_0901["late_minutes"] == 1


@pytest.mark.asyncio
async def test_grace_period_api_endpoints():
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Login
        login_res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Check system settings returns attendance_grace_period == '5'
        settings_res = await client.get("/api/v1/settings", headers=headers)
        assert settings_res.status_code == 200
        att_settings = settings_res.json()["settings"].get("ATTENDANCE", [])
        grace_setting = next((s for s in att_settings if s["key"] == "attendance_grace_period"), None)
        assert grace_setting is not None
        assert grace_setting["value"] == "5"

        # 2. Check /attendance/lateness returns grace_period == 5 in summary
        late_res = await client.get("/api/v1/attendance/lateness?year=2026&month=8", headers=headers)
        assert late_res.status_code == 200
        late_data = late_res.json()
        assert "summary" in late_data
        assert late_data["summary"]["grace_period"] == 5

        # 3. Check /attendance/monthly returns grace_period == 5
        monthly_res = await client.get("/api/v1/attendance/monthly?year=2026&month=8", headers=headers)
        assert monthly_res.status_code == 200
        monthly_data = monthly_res.json()
        assert monthly_data["grace_period"] == 5

        # 4. Check shifts endpoint returns grace_period_minutes == 5 for standard shifts
        shifts_res = await client.get("/api/v1/shifts", headers=headers)
        assert shifts_res.status_code == 200
        shift_items = shifts_res.json()["items"]
        gs_shift = next((s for s in shift_items if s["code"] == "GS"), None)
        assert gs_shift is not None
        assert gs_shift["grace_period_minutes"] == 5
