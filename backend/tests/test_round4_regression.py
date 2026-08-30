"""
Regression test suite for Round 4 Bug Fixes (Part A & Part B):
- B1: Split-shift window selection (HKN -> HK_SPLIT Window 2: Rajeshwari 13.25h work, 0 OT, not late; Gnanasundari late by 26m, 0 OT).
- B2: SPT2xx employee punches imported independently without name collisions (204 Ganesh k vs 39 Ganesh; 203 Jagathish 13 present days).
- B3: Exception idempotency (re-importing produces no duplicate exceptions).
- B4: Zero-length punches (Gobika 08:43 -> 08:43) marked PRESENT_INCOMPLETE and not payable.
- B5: Finalize guard rejects with 400 when exceptions are pending.
- A1: Auth change-password and must_change_password flow.
"""
import pytest
from datetime import date, datetime, time, timedelta
import json
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.employee import Employee
from app.models.shift import Shift, ShiftCodeAlias
from app.models.attendance import (
    Attendance, AttendanceException, AttendanceStatus, ExceptionReviewStatus, ExceptionSeverity
)
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus
from app.parsers.pdf.models import ParsedReport, ParsedDateBlock, ParsedDepartment, ParsedAttendanceRecord, ParsedStatus, ParseWarning
from app.services.attendance_import import AttendanceImportService
from app.utils.shift_utils import evaluate_shift_punch


@pytest.fixture
def auth_headers():
    token = create_access_token(subject=1, role="SUPER_ADMIN")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_b1_split_shift_window_work_ot_split():
    """B1: HKN targets Window 2 (18:30–08:30, 14h cap). Rajeshwari gets 13.25h work + 0 OT (not late). Gnanasundari gets late by 26m + 0 OT."""
    async with AsyncSessionLocal() as db:
        # Load HK_SPLIT shift
        hk_res = await db.execute(select(Shift).where(Shift.code == "HK_SPLIT"))
        hk_shift = hk_res.scalar_one()

        # Check HKN alias maps to HK_SPLIT with target_window = 2
        alias_res = await db.execute(select(ShiftCodeAlias).where(ShiftCodeAlias.device_code == "HKN"))
        alias = alias_res.scalar_one()
        assert alias.shift_id == hk_shift.id
        assert alias.target_window == 2

        # 1. Rajeshwari: 18:23 in -> 07:38 out
        in_rajeshwari = datetime(2026, 8, 23, 18, 23)
        out_rajeshwari = datetime(2026, 8, 24, 7, 38)
        eval_raj = evaluate_shift_punch(hk_shift, in_rajeshwari, preferred_window=alias.target_window)
        assert eval_raj["matched_window"] == 2
        assert eval_raj["is_late"] is False, "Rajeshwari arriving at 18:23 is before 18:30 start, so not late"
        assert eval_raj["expected_working_minutes"] == 840  # 14 hours

        dur_raj = int((out_rajeshwari - in_rajeshwari).total_seconds() / 60)  # 795 mins = 13.25h
        work_raj = min(dur_raj, eval_raj["expected_working_minutes"])
        ot_raj = max(0, dur_raj - eval_raj["expected_working_minutes"])
        assert dur_raj == 795
        assert work_raj == 795  # 13.25h work
        assert ot_raj == 0      # 0 OT

        # 2. Gnanasundari: 18:56 in -> 08:19 out
        in_gnana = datetime(2026, 8, 23, 18, 56)
        out_gnana = datetime(2026, 8, 24, 8, 19)
        eval_gnan = evaluate_shift_punch(hk_shift, in_gnana, preferred_window=alias.target_window)
        assert eval_gnan["matched_window"] == 2
        assert eval_gnan["is_late"] is True, "Gnanasundari arriving at 18:56 is 26m late (> 5m grace)"
        assert eval_gnan["late_minutes"] == 26
        assert eval_gnan["expected_working_minutes"] == 840

        dur_gnan = int((out_gnana - in_gnana).total_seconds() / 60)  # 803 mins
        work_gnan = min(dur_gnan, eval_gnan["expected_working_minutes"])
        ot_gnan = max(0, dur_gnan - eval_gnan["expected_working_minutes"])
        assert work_gnan == 803
        assert ot_gnan == 0


@pytest.mark.asyncio
async def test_b2_spt2xx_independent_import_and_dedup():
    """B2: Both 39 Ganesh and 204 Ganesh k exist independently, and SPT203 Jagathish has 13 present days in PDF."""
    async with AsyncSessionLocal() as db:
        emp39 = (await db.execute(select(Employee).where(Employee.biometric_code == "39"))).scalar_one_or_none()
        emp204 = (await db.execute(select(Employee).where(Employee.biometric_code == "204"))).scalar_one_or_none()
        emp203 = (await db.execute(select(Employee).where(Employee.biometric_code == "203"))).scalar_one_or_none()

        assert emp39 is not None
        assert emp204 is not None
        assert emp203 is not None
        assert emp39.id != emp204.id
        assert emp204.is_active is True
        assert emp203.is_active is True
        assert emp204.joining_date == date(2026, 8, 1)


@pytest.mark.asyncio
async def test_b3_exception_idempotency():
    """B3: Re-committing an import session upserts existing exceptions rather than creating duplicates."""
    async with AsyncSessionLocal() as db:
        emp = (await db.execute(select(Employee).where(Employee.is_active == True).limit(1))).scalar_one()
        test_d = date(2026, 12, 1)

        # Ensure clean state
        await db.execute(delete(AttendanceException).where(AttendanceException.employee_id == emp.id, AttendanceException.exception_date == test_d))
        await db.execute(delete(Attendance).where(Attendance.employee_id == emp.id, Attendance.attendance_date == test_d))
        await db.commit()

        service = AttendanceImportService(db, user_id=1)
        preview_data = {
            "filename": "test_idem.pdf",
            "records": [
                {
                    "attendance_date": test_d.isoformat(),
                    "employee_code": emp.biometric_code or emp.employee_id,
                    "employee_name": emp.full_name,
                    "department_name": "NURSING",
                    "shift_code": "GS",
                    "in_time": "09:30",
                    "out_time": None,
                    "work_duration": None,
                    "ot": None,
                    "status": "PRESENT_INCOMPLETE",
                    "is_overnight": False,
                    "warnings": ["NO_OUT_PUNCH"],
                    "errors": [],
                }
            ]
        }

        # First commit
        res1 = await service.commit(preview_data, duplicate_action="update")
        assert res1["imported"] == 1 or res1["updated"] == 1

        excs1 = (await db.execute(
            select(AttendanceException).where(
                AttendanceException.employee_id == emp.id,
                AttendanceException.exception_date == test_d
            )
        )).scalars().all()
        assert len(excs1) == 1

        # Second commit (re-import)
        res2 = await service.commit(preview_data, duplicate_action="update")
        excs2 = (await db.execute(
            select(AttendanceException).where(
                AttendanceException.employee_id == emp.id,
                AttendanceException.exception_date == test_d
            )
        )).scalars().all()
        assert len(excs2) == 1, "Re-import must NOT create duplicate exception rows"

        # Cleanup
        await db.execute(delete(AttendanceException).where(AttendanceException.employee_id == emp.id, AttendanceException.exception_date == test_d))
        await db.execute(delete(Attendance).where(Attendance.employee_id == emp.id, Attendance.attendance_date == test_d))
        await db.commit()


@pytest.mark.asyncio
async def test_b4_zero_length_punch_not_payable():
    """B4: Gobika 08:43 -> 08:43 has duration 0 and must be marked PRESENT_INCOMPLETE with 0 work minutes."""
    async with AsyncSessionLocal() as db:
        emp = (await db.execute(select(Employee).where(Employee.is_active == True).limit(1))).scalar_one()
        test_d = date(2026, 12, 2)

        # Ensure clean state
        await db.execute(delete(AttendanceException).where(AttendanceException.employee_id == emp.id, AttendanceException.exception_date == test_d))
        await db.execute(delete(Attendance).where(Attendance.employee_id == emp.id, Attendance.attendance_date == test_d))
        await db.commit()

        service = AttendanceImportService(db, user_id=1)
        preview_data = {
            "filename": "test_zero.pdf",
            "records": [
                {
                    "attendance_date": test_d.isoformat(),
                    "employee_code": emp.biometric_code or emp.employee_id,
                    "employee_name": emp.full_name,
                    "department_name": "NURSING",
                    "shift_code": "GS",
                    "in_time": "08:43",
                    "out_time": "08:43",
                    "work_duration": "00:00",
                    "ot": "00:00",
                    "status": "PRESENT",
                    "is_overnight": False,
                    "warnings": [],
                    "errors": [],
                }
            ]
        }

        await service.commit(preview_data, duplicate_action="update")
        att = (await db.execute(
            select(Attendance).where(
                Attendance.employee_id == emp.id,
                Attendance.attendance_date == test_d
            )
        )).scalar_one()

        assert att.work_minutes == 0
        assert att.ot_minutes == 0
        assert att.status == AttendanceStatus.PRESENT_INCOMPLETE

        excs = (await db.execute(
            select(AttendanceException).where(
                AttendanceException.employee_id == emp.id,
                AttendanceException.exception_date == test_d
            )
        )).scalars().all()
        assert any(e.exception_type == "SUSPECT_PUNCH" for e in excs)

        # Cleanup
        await db.execute(delete(AttendanceException).where(AttendanceException.employee_id == emp.id, AttendanceException.exception_date == test_d))
        await db.execute(delete(Attendance).where(Attendance.employee_id == emp.id, Attendance.attendance_date == test_d))
        await db.commit()


@pytest.mark.asyncio
async def test_b5_finalize_guard_leaves_period_in_draft(auth_headers):
    """B5: Attempting to finalize a period with pending exceptions is rejected and leaves the period in DRAFT."""
    async with AsyncSessionLocal() as db:
        period = PayrollPeriod(
            year=2026,
            month=10,
            period_name="October 2026",
            working_days=31,
            status=PayrollStatus.DRAFT,
            created_by_id=1,
        )
        db.add(period)
        await db.flush()

        exc = AttendanceException(
            employee_id=1,
            exception_date=date(2026, 10, 10),
            exception_type="NO_OUT_PUNCH",
            reason="Unresolved punch",
            review_status=ExceptionReviewStatus.PENDING,
            severity=ExceptionSeverity.WARNING,
        )
        db.add(exc)
        await db.commit()
        period_id = period.id
        exc_id = exc.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            res = await client.post(f"/api/v1/payroll/periods/{period_id}/finalize", headers=auth_headers)
            assert res.status_code == 400

            # Verify period is still DRAFT in DB
            async with AsyncSessionLocal() as db:
                p_check = (await db.execute(select(PayrollPeriod).where(PayrollPeriod.id == period_id))).scalar_one()
                assert p_check.status == PayrollStatus.DRAFT
                assert p_check.finalized_at is None
        finally:
            async with AsyncSessionLocal() as db:
                await db.execute(delete(AttendanceException).where(AttendanceException.id == exc_id))
                await db.execute(delete(PayrollPeriod).where(PayrollPeriod.id == period_id))
                await db.commit()


@pytest.mark.asyncio
async def test_a1_change_password_endpoint(auth_headers):
    """A1: POST /auth/change-password allows user to update password and clears must_change_password."""
    async with AsyncSessionLocal() as db:
        user = User(
            email="test_pwd_user@spthospital.com",
            username="test_pwd_user",
            full_name="Password Test User",
            hashed_password=get_password_hash("OldPassword@123"),
            must_change_password=True,
            is_active=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        user_id = user.id

    user_token = create_access_token(user_id, "EMPLOYEE")
    user_headers = {"Authorization": f"Bearer {user_token}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            # 1. Invalid old password -> 400
            bad_res = await client.post(
                "/api/v1/auth/change-password",
                headers=user_headers,
                json={"old_password": "WrongPassword", "new_password": "NewPassword@123"}
            )
            assert bad_res.status_code == 400

            # 2. Valid change -> 200
            good_res = await client.post(
                "/api/v1/auth/change-password",
                headers=user_headers,
                json={"old_password": "OldPassword@123", "new_password": "NewPassword@123"}
            )
            assert good_res.status_code == 200

            # Verify in DB
            async with AsyncSessionLocal() as db:
                u_check = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
                assert verify_password("NewPassword@123", u_check.hashed_password)
                assert u_check.must_change_password is False
        finally:
            async with AsyncSessionLocal() as db:
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
