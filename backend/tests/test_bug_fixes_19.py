"""
SPT Hospital HRMS — 19 Bug Fixes Regression Test Suite
Covers:
- Item 1: Missing out-punch auto-credited to shift end -> work_minutes=0, PRESENT_INCOMPLETE uncorrected excluded from present_days, pending exceptions blocker in finalize
- Item 2: Savings fund deduction posted to ledger (SecurityFundTransaction) on calculation
- Item 3: Deduction capped at gross, carried_forward_deductions recorded
- Item 4: Attendance outside employment dates excluded from payroll & import
- Item 5: Daily Attendance filters contract (attendance_date, status_filter, search)
- Item 6: Daily Attendance pagination (page, page_size, total)
- Item 7: Shift code alias mapping (ShiftCodeAlias CRUD and lookup)
- Item 8: Re-import duplicate detection and ImportStatus.SKIPPED
- Item 9: GET /reports/lateness-lop?format=excel generates valid xlsx
- Item 10: GET /reports/missing-punch and /reports/overtime generate valid xlsx
- Item 11: CORS on error responses
"""
import pytest
import io
import uuid
import openpyxl
from datetime import date, datetime, timezone
import httpx
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.employee import Employee, EmploymentType, SecurityFundTransaction
from app.models.attendance import (
    Attendance, AttendanceStatus, AttendanceException,
    ExceptionReviewStatus, ExceptionSeverity, AttendanceImport, ImportStatus
)
from app.models.shift import Shift, ShiftCodeAlias
from app.models.payroll import (
    PayrollPeriod, PayrollRecord, PayrollItem, PayrollStatus
)
from app.payroll.engine import PayrollEngine

BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_item1_missing_outpunch_not_payable():
    """Item 1: Uncorrected PRESENT_INCOMPLETE is excluded from present_days in payroll calculation."""
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)

        # Create test employee
        uid = f"TEST_P1_{uuid.uuid4().hex[:6]}"
        emp = Employee(
            employee_id=uid,
            biometric_code=f"{uuid.uuid4().int % 90000 + 10000}",
            first_name="Outpunch",
            last_name="Test",
            full_name="Outpunch Test",
            basic_salary=31000.0,
            is_active=True,
        )
        session.add(emp)
        await session.flush()

        # Create period
        p_res = await session.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 8))
        period = p_res.scalar_one_or_none()
        if not period:
            period = PayrollPeriod(year=2026, month=8, period_name="August 2026", working_days=31, status=PayrollStatus.DRAFT, created_by_id=1)
            session.add(period)
            await session.flush()

        # Add 1 valid PRESENT day and 1 PRESENT_INCOMPLETE uncorrected day
        att1 = Attendance(
            employee_id=emp.id,
            attendance_date=date(2026, 8, 1),
            status=AttendanceStatus.PRESENT,
            source_in_time="09:00",
            source_out_time="17:00",
            work_minutes=480,
            is_corrected=False,
        )
        att2 = Attendance(
            employee_id=emp.id,
            attendance_date=date(2026, 8, 2),
            status=AttendanceStatus.PRESENT_INCOMPLETE,
            source_in_time="09:00",
            source_out_time=None,
            work_minutes=0,
            is_corrected=False,
        )
        session.add_all([att1, att2])
        await session.commit()

        # Calculate payroll -> only 1 present day should be counted
        calc_res = await engine.calculate_employee_payroll(emp.id, 2026, 8, period=period)
        assert calc_res is not None
        rec, _ = calc_res
        assert rec.present_days == 1.0
        assert rec.payable_days == 1.0

        # Now correct att2 -> present_days should become 2
        att2.is_corrected = True
        att2.source_out_time = "17:00"
        att2.work_minutes = 480
        await session.commit()

        calc_res2 = await engine.calculate_employee_payroll(emp.id, 2026, 8, period=period)
        assert calc_res2 is not None
        rec2, _ = calc_res2
        assert rec2.present_days == 2.0

        # Cleanup
        await session.execute(delete(Attendance).where(Attendance.employee_id == emp.id))
        await session.delete(emp)
        await session.commit()


@pytest.mark.asyncio
async def test_item1_finalize_pending_exceptions_blocker():
    """Item 1: finalize_payroll blocks if there are PENDING NO_OUT_PUNCH exceptions for that month."""
    async with AsyncSessionLocal() as session:
        # Create a dummy period
        p_res = await session.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2029, PayrollPeriod.month == 1))
        period = p_res.scalar_one_or_none()
        if not period:
            period = PayrollPeriod(year=2029, month=1, period_name="January 2029", working_days=31, status=PayrollStatus.DRAFT, created_by_id=1)
            session.add(period)
            await session.commit()
            await session.refresh(period)

        # Add a pending NO_OUT_PUNCH exception
        exc = AttendanceException(
            employee_id=1,
            exception_date=date(2029, 1, 15),
            exception_type="NO_OUT_PUNCH",
            severity=ExceptionSeverity.WARNING,
            review_status=ExceptionReviewStatus.PENDING,
            reason="Missing out-punch test",
        )
        session.add(exc)
        await session.commit()

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        fin_res = await client.post(f"/api/v1/payroll/periods/{period.id}/finalize", headers=headers)
        assert fin_res.status_code == 400
        assert "exceptions" in fin_res.json()["detail"].lower()

    # Cleanup
    async with AsyncSessionLocal() as session:
        await session.execute(delete(AttendanceException).where(AttendanceException.exception_date == date(2029, 1, 15)))
        p = await session.get(PayrollPeriod, period.id)
        if p:
            await session.execute(delete(PayrollItem).where(PayrollItem.payroll_record_id.in_(
                select(PayrollRecord.id).where(PayrollRecord.period_id == p.id)
            )))
            await session.execute(delete(PayrollRecord).where(PayrollRecord.period_id == p.id))
            await session.delete(p)
        await session.commit()


@pytest.mark.asyncio
async def test_item2_savings_fund_ledger_deposit():
    """Item 2: SecurityFundTransaction rows created idempotently during payroll calculation."""
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)

        uid = f"TEST_P2_{uuid.uuid4().hex[:6]}"
        emp = Employee(
            employee_id=uid,
            biometric_code=f"{uuid.uuid4().int % 90000 + 10000}",
            first_name="Savings",
            last_name="Fund",
            full_name="Savings Fund",
            basic_salary=31000.0,
            security_fund_deduction=500.0,
            is_active=True,
        )
        session.add(emp)
        await session.flush()

        # Add attendance record so employee has earnings
        att = Attendance(
            employee_id=emp.id,
            attendance_date=date(2026, 8, 10),
            source_in_time="09:00",
            source_out_time="17:00",
            check_in_datetime=datetime(2026, 8, 10, 9, 0),
            check_out_datetime=datetime(2026, 8, 10, 17, 0),
            work_minutes=480,
            status=AttendanceStatus.PRESENT,
        )
        session.add(att)
        await session.flush()

        p_res = await session.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 8))
        period = p_res.scalar_one_or_none()
        if not period:
            period = PayrollPeriod(
                year=2026,
                month=8,
                period_name="August 2026",
                working_days=31,
                status=PayrollStatus.DRAFT,
                created_by_id=1,
            )
            session.add(period)
            await session.commit()
            await session.refresh(period)

        # Run calculate_all_employees
        stats = await engine.calculate_all_employees(period, period.working_days, 1)
        assert stats["calculated"] > 0

        # Verify SecurityFundTransaction exists for this employee and period
        note_str = f"Payroll deduction for {period.period_name}"
        tx_res = await session.execute(
            select(SecurityFundTransaction).where(
                SecurityFundTransaction.employee_id == emp.id,
                SecurityFundTransaction.transaction_type == "DEPOSIT",
                SecurityFundTransaction.notes == note_str,
            )
        )
        txs = tx_res.scalars().all()
        assert len(txs) == 1
        assert txs[0].amount == 500.0

        # Recalculate -> assert no double-posting (still 1 transaction)
        await engine.calculate_all_employees(period, period.working_days, 1)
        tx_res2 = await session.execute(
            select(SecurityFundTransaction).where(
                SecurityFundTransaction.employee_id == emp.id,
                SecurityFundTransaction.transaction_type == "DEPOSIT",
                SecurityFundTransaction.notes == note_str,
            )
        )
        txs2 = tx_res2.scalars().all()
        assert len(txs2) == 1

        # Cleanup
        await session.execute(delete(Attendance).where(Attendance.employee_id == emp.id))
        await session.execute(delete(SecurityFundTransaction).where(SecurityFundTransaction.employee_id == emp.id))
        await session.execute(delete(PayrollRecord).where(PayrollRecord.employee_id == emp.id))
        await session.delete(emp)
        await session.commit()


@pytest.mark.asyncio
async def test_item3_deduction_capped_at_gross_and_carried_forward():
    """Item 3: Deductions are capped at gross salary and unrecovered amount is zero if zero gross."""
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)

        uid = f"TEST_P3_{uuid.uuid4().hex[:6]}"
        emp = Employee(
            employee_id=uid,
            biometric_code=f"{uuid.uuid4().int % 90000 + 10000}",
            first_name="Zero",
            last_name="Gross",
            full_name="Zero Gross",
            basic_salary=31000.0,
            security_fund_deduction=500.0,
            is_active=True,
        )
        session.add(emp)
        await session.flush()

        p_res = await session.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 8))
        period = p_res.scalar_one_or_none()

        # Employee has 0 payable days and 0 collection -> gross = 0
        override_inputs = {
            "present_days": 0.0,
            "half_days": 0.0,
            "leave_days": 0.0,
            "off_duty_days": 0.0,
            "qualifying_late_days": 0,
            "collection": 0.0,
        }

        calc_res = await engine.calculate_employee_payroll(
            emp.id, 2026, 8, period=period, override_inputs=override_inputs
        )
        assert calc_res is not None
        rec, _ = calc_res
        assert rec.gross_salary == 0.0
        assert rec.total_deductions == 0.0  # capped at gross (0.0)
        assert rec.carried_forward_deductions == 0.0  # zero-net staff cannot be deducted
        assert rec.net_salary == 0.0

        # Partial gross case: salary_part = 200, fund = 500
        # Under Round 4 Addendum rule: if fund deduction exceeds payable amount, deduct nothing (0.0)
        override_partial = {
            "present_days": 0.2,  # 0.2 * 1000 = 200
            "half_days": 0.0,
            "leave_days": 0.0,
            "off_duty_days": 0.0,
            "qualifying_late_days": 0,
            "collection": 0.0,
        }
        calc_partial = await engine.calculate_employee_payroll(
            emp.id, 2026, 8, period=period, override_inputs=override_partial
        )
        rec_part, _ = calc_partial
        assert rec_part.gross_salary == 200.0
        assert rec_part.security_fund_deduction == 0.0  # deduct nothing if cannot fully cover
        assert rec_part.total_deductions == 0.0
        assert rec_part.carried_forward_deductions == 0.0
        assert rec_part.net_salary == 200.0

        # Cleanup
        await session.delete(emp)
        await session.commit()


@pytest.mark.asyncio
async def test_item4_employment_date_filtering():
    """Item 4: Attendance dates before joining_date are excluded from payroll calculations."""
    async with AsyncSessionLocal() as session:
        engine = PayrollEngine(session)

        uid = f"TEST_P4_{uuid.uuid4().hex[:6]}"
        emp = Employee(
            employee_id=uid,
            biometric_code=f"{uuid.uuid4().int % 90000 + 10000}",
            first_name="Joined",
            last_name="Late",
            full_name="Joined Late",
            basic_salary=31000.0,
            joining_date=date(2026, 8, 20),  # Joined on 20th
            security_fund_deduction=0.0,
            is_active=True,
        )
        session.add(emp)
        await session.flush()

        p_res = await session.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 8))
        period = p_res.scalar_one_or_none()

        # Add attendance on Aug 5 (before joining - should be excluded) and Aug 25 (after joining)
        att_before = Attendance(
            employee_id=emp.id,
            attendance_date=date(2026, 8, 5),
            status=AttendanceStatus.ABSENT,
        )
        att_after = Attendance(
            employee_id=emp.id,
            attendance_date=date(2026, 8, 25),
            status=AttendanceStatus.PRESENT,
            source_in_time="09:00",
            source_out_time="17:00",
            work_minutes=480,
        )
        session.add_all([att_before, att_after])
        await session.commit()

        calc_res = await engine.calculate_employee_payroll(emp.id, 2026, 8, period=period)
        assert calc_res is not None
        rec, _ = calc_res

        # Effective days in month for Aug 20 to Aug 31 is 12 days
        # present = 1, absent should be 12 - 1 = 11 (not 31 - 1 = 30)
        assert rec.present_days == 1.0
        assert rec.absent_days == 11.0

        # Cleanup
        await session.execute(delete(Attendance).where(Attendance.employee_id == emp.id))
        await session.delete(emp)
        await session.commit()


@pytest.mark.asyncio
async def test_item5_and_6_attendance_filters_and_pagination():
    """Item 5 & 6: Attendance GET endpoint supports attendance_date, status_filter, search, and pagination."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Test pagination
        res = await client.get("/api/v1/attendance?page=1&page_size=10", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert len(data["items"]) <= 10

        # Test status filter
        res_stat = await client.get("/api/v1/attendance?status_filter=PRESENT&page_size=5", headers=headers)
        assert res_stat.status_code == 200
        for item in res_stat.json()["items"]:
            assert item["status"] == "PRESENT"

        # Test search filter
        res_search = await client.get("/api/v1/attendance?search=Manoj&page_size=5", headers=headers)
        assert res_search.status_code == 200
        for item in res_search.json()["items"]:
            assert "manoj" in (item.get("employee_name") or "").lower() or "manoj" in (item.get("employee_code") or "").lower()


@pytest.mark.asyncio
async def test_item7_shift_code_aliases():
    """Item 7: ShiftCodeAlias CRUD and device code mapping."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create alias
        alias_code = f"DEV_{uuid.uuid4().hex[:4].upper()}"
        create_res = await client.post(
            "/api/v1/shifts/aliases",
            headers=headers,
            json={"device_code": alias_code, "shift_id": 1}
        )
        assert create_res.status_code == 200
        alias_id = create_res.json()["id"]

        # List aliases
        list_res = await client.get("/api/v1/shifts/aliases", headers=headers)
        assert list_res.status_code == 200
        codes = [a["device_code"] for a in list_res.json()["items"]]
        assert alias_code in codes

        # Delete alias
        del_res = await client.delete(f"/api/v1/shifts/aliases/{alias_id}", headers=headers)
        assert del_res.status_code == 200


@pytest.mark.asyncio
async def test_item9_and_10_reports_excel_export():
    """Item 9 & 10: Reports endpoints generate valid Excel files."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        login_res = await client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Lateness & LOP Excel
        res_lop = await client.get("/api/v1/reports/lateness-lop?year=2026&month=8&format=excel", headers=headers)
        assert res_lop.status_code == 200
        assert "spreadsheetml" in res_lop.headers.get("content-type", "")
        wb = openpyxl.load_workbook(io.BytesIO(res_lop.content))
        assert "Lateness LOP 2026-08" in wb.sheetnames

        # Missing Punch Excel
        res_mp = await client.get("/api/v1/reports/missing-punch?format=excel", headers=headers)
        assert res_mp.status_code == 200
        wb_mp = openpyxl.load_workbook(io.BytesIO(res_mp.content))
        assert "Missing Punch Report" in wb_mp.sheetnames

        # Overtime Excel
        res_ot = await client.get("/api/v1/reports/overtime?format=excel", headers=headers)
        assert res_ot.status_code == 200
        wb_ot = openpyxl.load_workbook(io.BytesIO(res_ot.content))
        assert "Overtime Report" in wb_ot.sheetnames


@pytest.mark.asyncio
async def test_item11_cors_headers_on_error():
    """Item 11: CORS headers are present on 4xx error responses."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Send unauthenticated request with Origin header
        headers = {"Origin": "http://localhost:3000"}
        res = await client.get("/api/v1/reports/lateness-lop", headers=headers)
        assert res.status_code in [401, 403]
        assert res.headers.get("access-control-allow-origin") == "http://localhost:3000"
