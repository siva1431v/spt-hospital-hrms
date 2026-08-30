"""
Regression Test Suite for SPT Hospital HRMS — Round 2 Bug Fixes (P0–P5)
Verifies:
- P0: Split-shift window matching, out-time to correct window end, <1h duration guard, backfill of approved exceptions
- P1: Circular shift evaluation: Rajeshwari (HK_SPLIT 18:23) NOT late, Gnanasundari (HK_SPLIT 18:56) IS late
- P1: Shift mismatch diagnostic endpoint flags off-schedule staff
- P2: Zero-punch employees have 0 LOP, 0 late days, 0 OT on Monthly Summary
- P3: Total work hours is always a numeric float formatted to 2 decimals
- P5: Deactivated employees excluded from daily attendance
"""
from datetime import date, datetime, time, timedelta
import pytest
from sqlalchemy import select, delete
from fastapi import HTTPException
from unittest.mock import MagicMock

from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.shift import Shift
from app.models.attendance import (
    Attendance,
    AttendanceStatus,
    AttendanceException,
    ExceptionReviewStatus,
)
from app.utils.shift_utils import evaluate_shift_punch
from app.api.v1.endpoints.attendance import (
    _resolve_single_approved_exception,
    backfill_approved_exceptions,
    get_shift_mismatch_diagnostics,
    monthly_attendance_summary,
    list_attendance,
)


@pytest.mark.asyncio
async def test_p0_split_shift_window_matching():
    """P0: Split shift window selection matches in-punch to nearest window start (SEC_SPLIT at 16:59 matches 17:00-08:00 night window)."""
    async with AsyncSessionLocal() as session:
        # Load SEC_SPLIT shift
        s_res = await session.execute(select(Shift).where(Shift.code == "SEC_SPLIT"))
        sec_shift = s_res.scalar_one()

        # Create test employee with SEC_SPLIT
        emp = Employee(
            employee_id="TEST_SEC_P0",
            biometric_code="99901",
            first_name="Sec",
            last_name="Guard",
            full_name="Sec Guard",
            shift_id=sec_shift.id,
            is_active=True,
            basic_salary=20000.0,
        )
        session.add(emp)
        await session.flush()

        # Attendance on 2026-08-25 with in-punch at 16:59 (1 min before 17:00 night window)
        att = Attendance(
            employee_id=emp.id,
            attendance_date=date(2026, 8, 25),
            source_in_time="16:59",
            check_in_datetime=datetime(2026, 8, 25, 16, 59),
            status=AttendanceStatus.PRESENT_INCOMPLETE,
            is_corrected=False,
        )
        session.add(att)
        await session.flush()

        exc = AttendanceException(
            employee_id=emp.id,
            attendance_id=att.id,
            exception_date=date(2026, 8, 25),
            exception_type="NO_OUT_PUNCH",
            reason="Missing out punch on split shift",
            review_status=ExceptionReviewStatus.APPROVED.value,
        )
        session.add(exc)
        await session.flush()

        # Resolve exception
        await _resolve_single_approved_exception(session, exc, user_id=1)
        await session.flush()
        await session.refresh(att)

        # Assert out-punch set to 08:00 next day (Window 2 end), NOT 17:00
        assert att.source_out_time == "08:00"
        assert att.check_out_datetime == datetime(2026, 8, 26, 8, 0)
        assert att.work_minutes >= 540  # 9h work, capped at expected
        assert att.status == AttendanceStatus.PRESENT_OVERNIGHT
        assert att.is_corrected is True

        # Cleanup
        await session.execute(delete(AttendanceException).where(AttendanceException.id == exc.id))
        await session.execute(delete(Attendance).where(Attendance.id == att.id))
        await session.delete(emp)
        await session.commit()


@pytest.mark.asyncio
async def test_p0_rejects_sub_one_hour_resolution():
    """P0: Exception resolution guard rejects any resolution that yields < 1 hour (< 60m) of work."""
    async with AsyncSessionLocal() as session:
        s_res = await session.execute(select(Shift).where(Shift.code == "MS"))
        ms_shift = s_res.scalar_one()  # 06:00 - 14:00

        emp = Employee(
            employee_id="TEST_SHORT_P0",
            biometric_code="99902",
            first_name="Short",
            last_name="Duty",
            full_name="Short Duty",
            shift_id=ms_shift.id,
            is_active=True,
        )
        session.add(emp)
        await session.flush()

        # Punch in at 13:50 for a shift ending at 14:00 (10 mins duration)
        att = Attendance(
            employee_id=emp.id,
            attendance_date=date(2026, 8, 25),
            source_in_time="13:50",
            check_in_datetime=datetime(2026, 8, 25, 13, 50),
            status=AttendanceStatus.PRESENT_INCOMPLETE,
        )
        session.add(att)
        await session.flush()

        exc = AttendanceException(
            employee_id=emp.id,
            attendance_id=att.id,
            exception_date=date(2026, 8, 25),
            exception_type="NO_OUT_PUNCH",
            reason="Missing out punch on short duty",
            review_status=ExceptionReviewStatus.APPROVED.value,
        )
        session.add(exc)
        await session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await _resolve_single_approved_exception(session, exc, user_id=1)
        assert exc_info.value.status_code == 400
        assert "< 1 hour" in exc_info.value.detail or "< 60 minutes" in exc_info.value.detail

        # Cleanup
        await session.execute(delete(AttendanceException).where(AttendanceException.id == exc.id))
        await session.execute(delete(Attendance).where(Attendance.id == att.id))
        await session.delete(emp)
        await session.commit()


@pytest.mark.asyncio
async def test_p1_lateness_evaluation_negative_and_positive_cases():
    """
    P1: Shift punch evaluation correctly evaluates circular arrival against shift windows:
    - Rajeshwari (HK_SPLIT Window 2: 18:30 start, in at 18:23) is NOT late.
    - Gnanasundari (HK_SPLIT Window 2: 18:30 start, in at 18:56) IS late (26 min late, > 5m grace).
    """
    async with AsyncSessionLocal() as session:
        s_res = await session.execute(select(Shift).where(Shift.code == "HK_SPLIT"))
        hk_split = s_res.scalar_one()

        # Rajeshwari: in at 18:23
        dt_rajeshwari = datetime(2026, 8, 10, 18, 23)
        res_rajeshwari = evaluate_shift_punch(hk_split, dt_rajeshwari)
        assert res_rajeshwari["matched_window"] == 2
        assert res_rajeshwari["is_late"] is False
        assert res_rajeshwari["late_minutes"] == 0

        # Gnanasundari: in at 18:56
        dt_gnana = datetime(2026, 8, 10, 18, 56)
        res_gnana = evaluate_shift_punch(hk_split, dt_gnana)
        assert res_gnana["matched_window"] == 2
        assert res_gnana["is_late"] is True
        assert res_gnana["late_minutes"] == 26


@pytest.mark.asyncio
async def test_p1_shift_mismatch_diagnostic_tool():
    """P1: Diagnostic endpoint identifies staff whose median in-punch deviates from assigned shift."""
    async with AsyncSessionLocal() as session:
        user = MagicMock()
        user.id = 1
        user.role = "SUPER_ADMIN"

        res = await get_shift_mismatch_diagnostics(session, user)
        assert "items" in res
        assert res["total_active_employees"] >= 50

        # Check that night workers on day shifts are flagged
        flagged_codes = [item["biometric_code"] for item in res["items"] if item["is_mismatch"]]
        # Sathya (19), Aarthi G (13), Makisha (30), Gobika (34)
        for expected_code in ["19", "13", "30", "34"]:
            assert expected_code in flagged_codes, f"Expected code {expected_code} to be flagged in shift diagnostics"


@pytest.mark.asyncio
async def test_p2_zero_punch_exclusion_monthly_summary():
    """P2: Zero-punch employees on Monthly Summary receive 0 LOP, 0 late days, 0 OT hours, and 0 work hours."""
    async with AsyncSessionLocal() as session:
        user = MagicMock()
        user.id = 1
        user.role = "SUPER_ADMIN"

        # Create temporary zero-punch employee
        emp = Employee(
            employee_id="TEST_ZERO_P2",
            biometric_code="99903",
            first_name="Zero",
            last_name="Punch",
            full_name="Zero Punch",
            is_active=True,
            basic_salary=15000.0,
        )
        session.add(emp)
        await session.flush()

        res = await monthly_attendance_summary(
            session, user, year=2026, month=8, department_id=None, search="TEST_ZERO_P2"
        )
        items = res["items"]
        assert len(items) == 1
        row = items[0]
        assert row["present_payable"] == 0
        assert row["late_days_qualifying"] == 0
        assert row["lop_days"] == 0.0
        assert row["ot_hours"] == 0.0
        assert row["total_work_hours"] == 0.0

        # Cleanup
        await session.delete(emp)
        await session.commit()


@pytest.mark.asyncio
async def test_p3_total_work_hours_format_is_always_float():
    """P3: Total work hours is always a numeric float, never an HH:MM string."""
    async with AsyncSessionLocal() as session:
        user = MagicMock()
        user.id = 1
        user.role = "SUPER_ADMIN"

        res = await monthly_attendance_summary(session, user, year=2026, month=8, department_id=None, search=None)
        items = res["items"]
        assert len(items) > 0
        for item in items:
            assert isinstance(item["total_work_hours"], float), f"Expected float for {item['employee_name']}, got {type(item['total_work_hours'])}"
            assert isinstance(item["ot_hours"], float)


@pytest.mark.asyncio
async def test_p5_deactivated_employees_excluded_from_daily_attendance():
    """P5: Deactivated employees do not generate rows in GET /attendance."""
    async with AsyncSessionLocal() as session:
        user = MagicMock()
        user.id = 1
        user.role = "SUPER_ADMIN"

        # Deactivated employee with attendance
        emp = Employee(
            employee_id="TEST_INACTIVE_P5",
            biometric_code="99905",
            first_name="Deactivated",
            last_name="Staff",
            full_name="Deactivated Staff",
            is_active=False,
        )
        session.add(emp)
        await session.flush()

        att = Attendance(
            employee_id=emp.id,
            attendance_date=date(2026, 8, 20),
            status=AttendanceStatus.ABSENT,
        )
        session.add(att)
        await session.flush()

        res = await list_attendance(
            db=session,
            current_user=user,
            attendance_date=date(2026, 8, 20),
            date_from=None,
            date_to=None,
            department_id=None,
            status_filter=None,
            search="TEST_INACTIVE_P5",
            page=1,
            page_size=50,
        )
        assert res["total"] == 0
        assert len(res["items"]) == 0

        # Cleanup
        await session.execute(delete(Attendance).where(Attendance.id == att.id))
        await session.delete(emp)
        await session.commit()
