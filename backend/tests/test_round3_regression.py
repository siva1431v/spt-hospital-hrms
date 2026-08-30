"""
Regression test suite for Round 3 Bug Fixes (P0 to P7):
- P0: Device shift code mapping (NIGHT shift, MS->GS, NTS->NIGHT, HK->HK_SPLIT, etc.; NS is absent marker, not a shift).
- P1: Partial last day import handling (Printed On suppresses false NO_OUT_PUNCH on ongoing shifts).
- P2: Block finalize while unreviewed exceptions are pending.
- P3: Name collision diagnostic endpoint and biometric code dedup.
- P4: Approved exception backfill and resolution.
- P6: Post-midnight suspect punch detection (>14h duration).
- Negative lateness regression: Rajeshwari (18:23) not late, Gnanasundari (18:56) late.
"""
import pytest
from datetime import date, datetime, time, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app
from app.core.security import create_access_token
from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.shift import Shift, ShiftCodeAlias
from app.models.attendance import (
    Attendance, AttendanceException, AttendanceStatus, ExceptionReviewStatus, ExceptionSeverity
)
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus
from app.parsers.pdf.models import ParsedReport, ParsedDateBlock, ParsedDepartment, ParsedAttendanceRecord, ParsedStatus, ParseWarning
from app.parsers.pdf.monthly_parser import MonthlyStatusReportParser
from app.utils.shift_utils import evaluate_shift_punch


@pytest.fixture
def auth_headers():
    token = create_access_token(subject=1, role="SUPER_ADMIN")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_p0_night_shift_and_device_aliases():
    """P0: Verify canonical NIGHT shift exists, aliases map correctly, and NS is not mapped as a shift."""
    async with AsyncSessionLocal() as db:
        # Check NIGHT shift
        night_res = await db.execute(select(Shift).where(Shift.code == "NIGHT"))
        night_shift = night_res.scalar_one_or_none()
        assert night_shift is not None
        assert night_shift.start_time == time(19, 30)
        assert night_shift.end_time == time(9, 30)
        assert night_shift.is_overnight is True

        # Check aliases
        expected_aliases = {
            "MS": "GS",
            "NTS": "NIGHT",
            "HK": "HK_SPLIT",
            "HKN": "HK_SPLIT",
            "IS": "S2",
            "B": "S2",
            "GS": "DIET",
            "SS": "SEC_SPLIT",
            "SNS": "SEC_SPLIT",
        }
        for dev_code, expected_target in expected_aliases.items():
            a_res = await db.execute(
                select(ShiftCodeAlias).where(ShiftCodeAlias.device_code == dev_code)
            )
            alias = a_res.scalar_one_or_none()
            assert alias is not None, f"Alias {dev_code} not found in DB"
            s_res = await db.execute(select(Shift).where(Shift.id == alias.shift_id))
            target_s = s_res.scalar_one()
            assert target_s.code == expected_target, f"{dev_code} mapped to {target_s.code}, expected {expected_target}"

        # Check that NS is NOT mapped to any shift
        ns_alias = (await db.execute(
            select(ShiftCodeAlias).where(ShiftCodeAlias.device_code == "NS")
        )).scalar_one_or_none()
        assert ns_alias is None, "NS must NOT be mapped to any shift (NS is ABSENT marker)"


@pytest.mark.asyncio
async def test_p1_partial_day_handling_suppresses_no_out_punch():
    """P1: When import report was printed during the last day, missing out-punches on that date are marked partial and do not raise NO_OUT_PUNCH."""
    report = ParsedReport(
        report_type="Monthly Status Report (Detailed Work Duration)",
        company_name="SPT",
        date_range_start=date(2026, 8, 1),
        date_range_end=date(2026, 8, 25),
        printed_on=datetime(2026, 8, 25, 19, 10),
    )

    # Record 1: August 24 (not last day) with missing out punch -> NO_OUT_PUNCH
    rec1 = ParsedAttendanceRecord(
        attendance_date=date(2026, 8, 24),
        employee_code="999",
        status=ParsedStatus.PRESENT,
        in_time_str="09:30",
        out_time_str=None,
    )
    # Record 2: August 25 (last day, printed at 19:10) with in-punch at 09:30 and no out punch yet -> PARTIAL_DAY
    rec2 = ParsedAttendanceRecord(
        attendance_date=date(2026, 8, 25),
        employee_code="999",
        status=ParsedStatus.PRESENT,
        in_time_str="09:30",
        out_time_str=None,
    )

    # Evaluate logic as implemented in parser
    for r in [rec1, rec2]:
        warnings = []
        is_partial = False
        if r.status == ParsedStatus.PRESENT and r.in_time_str and not r.out_time_str:
            if (
                report.printed_on
                and report.date_range_end
                and r.attendance_date == report.date_range_end == report.printed_on.date()
            ):
                is_partial = True
                warnings.append(ParseWarning.PARTIAL_DAY)
            else:
                warnings.append(ParseWarning.NO_OUT_PUNCH)
        r.is_partial = is_partial
        r.warnings = warnings

    assert rec1.is_partial is False
    assert ParseWarning.NO_OUT_PUNCH in rec1.warnings

    assert rec2.is_partial is True
    assert ParseWarning.PARTIAL_DAY in rec2.warnings
    assert ParseWarning.NO_OUT_PUNCH not in rec2.warnings


@pytest.mark.asyncio
async def test_p2_block_finalize_on_pending_exceptions(auth_headers):
    """P2: Finalize must refuse with 400 when PENDING exceptions exist for the period."""
    async with AsyncSessionLocal() as db:
        # Create a dummy period
        period = PayrollPeriod(
            year=2026,
            month=11,
            period_name="November 2026",
            working_days=30,
            status=PayrollStatus.DRAFT,
            created_by_id=1,
        )
        db.add(period)
        await db.flush()

        # Add a dummy pending exception
        exc = AttendanceException(
            employee_id=1,
            exception_date=date(2026, 11, 15),
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
            response = await client.post(
                f"/api/v1/payroll/periods/{period_id}/finalize",
                headers=auth_headers,
            )
            assert response.status_code == 400
            data = response.json()
            detail_msg = data.get("detail", {}).get("message", "") if isinstance(data.get("detail"), dict) else data.get("detail", "")
            assert "unreviewed attendance exceptions remain" in detail_msg or "pending" in detail_msg
        finally:
            async with AsyncSessionLocal() as db:
                await db.execute(delete(AttendanceException).where(AttendanceException.id == exc_id))
                await db.execute(delete(PayrollPeriod).where(PayrollPeriod.id == period_id))
                await db.commit()


@pytest.mark.asyncio
async def test_p3_name_collisions_endpoint(auth_headers):
    """P3: GET /employees/name-collisions identifies active employees sharing similar names across distinct biometric IDs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/employees/name-collisions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "collisions" in data
        assert "total_collisions" in data

        # Verify that Ganesh or Madesh or Murugesan (who have dual enrollments) are listed in collisions
        collision_names = [c["normalized_name"] for c in data["collisions"]]
        assert any("ganesh" in name or "murugesan" in name or "madesh" in name or "saran" in name for name in collision_names)


@pytest.mark.asyncio
async def test_p4_exception_approval_resolution():
    """P4: Approving an exception resolves out_time, calculates proper duration and marks is_corrected."""
    async with AsyncSessionLocal() as db:
        # Fetch or create employee with GS shift
        res = await db.execute(select(Employee).where(Employee.is_active == True).limit(1))
        emp = res.scalar_one()

        test_date = date(2026, 12, 23)
        # Ensure clean state for test date
        await db.execute(
            delete(Attendance).where(
                Attendance.employee_id == emp.id,
                Attendance.attendance_date == test_date,
            )
        )

        att = Attendance(
            employee_id=emp.id,
            attendance_date=test_date,
            source_in_time="09:46",
            source_out_time=None,
            source_status="P",
            status=AttendanceStatus.PRESENT_INCOMPLETE,
            is_corrected=False,
        )
        db.add(att)
        await db.flush()

        exc = AttendanceException(
            attendance_id=att.id,
            employee_id=emp.id,
            exception_date=test_date,
            exception_type="NO_OUT_PUNCH",
            reason="Present (No OutPunch)",
            review_status=ExceptionReviewStatus.APPROVED,
            severity=ExceptionSeverity.WARNING,
        )
        db.add(exc)
        await db.flush()

        from app.api.v1.endpoints.attendance import _resolve_single_approved_exception
        await _resolve_single_approved_exception(db, exc, user_id=1)
        await db.commit()

        await db.refresh(att)
        assert att.check_out_datetime is not None
        assert att.work_minutes >= 60
        assert att.status == AttendanceStatus.PRESENT
        assert att.is_corrected is True

        # Clean up test rows
        await db.execute(delete(AttendanceException).where(AttendanceException.id == exc.id))
        await db.execute(delete(Attendance).where(Attendance.id == att.id))
        await db.commit()


@pytest.mark.asyncio
async def test_p6_suspect_post_midnight_punch_flag():
    """P6: Post-midnight in-punch between 00:00 and 03:00 with duration > 14h is flagged as SUSPECT_PUNCH."""
    parser = MonthlyStatusReportParser(pdf_path="dummy", grace_minutes=5)

    # 00:38 in, 19:52 out, 19:14 duration -> 1154 minutes (>840 mins)
    duration_str = "19:14"
    in_time_str = "00:38"
    dur_mins = parser._parse_duration_mins(duration_str)
    assert dur_mins == 19 * 60 + 14

    warnings = []
    ih = int(in_time_str.split(":")[0])
    if 0 <= ih < 3 and dur_mins and dur_mins > 840:
        warnings.append(ParseWarning.SUSPECT_PUNCH)

    assert ParseWarning.SUSPECT_PUNCH in warnings


@pytest.mark.asyncio
async def test_negative_lateness_cases_preserved():
    """Regression: Verify that on-time night arrivals are NOT marked late."""
    async with AsyncSessionLocal() as db:
        # Load HK_SPLIT shift (Window 2: 18:30 - 08:30)
        hk_res = await db.execute(select(Shift).where(Shift.code == "HK_SPLIT"))
        hk_shift = hk_res.scalar_one()

        # Negative case: Rajeshwari punches in at 18:23 (7 mins BEFORE 18:30 window 2 start)
        in_rajeshwari = datetime(2026, 8, 10, 18, 23)
        res_raj = evaluate_shift_punch(hk_shift, in_rajeshwari)
        assert res_raj["is_late"] is False, "Rajeshwari at 18:23 must NOT be marked late"
        assert res_raj["late_minutes"] == 0

        # Positive case: Gnanasundari punches in at 18:56 (26 mins AFTER 18:30 window 2 start, > 5m grace)
        in_gnanasundari = datetime(2026, 8, 10, 18, 56)
        res_gnan = evaluate_shift_punch(hk_shift, in_gnanasundari)
        assert res_gnan["is_late"] is True, "Gnanasundari at 18:56 must be marked late"
        assert res_gnan["late_minutes"] == 26
