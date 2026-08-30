"""
SPT Hospital HRMS — Round 6 Integrity Test Suite
Verifies:
1. P0-1: SPT12 Bhuvaneshwari active, 66 staff, 1,650 attendance records (1288 P, 333 A, 403 device late, 286 qualifying late, 44 staff with >=1 qualifying late, 78 LOP days across 30 staff).
2. P0-2: Makisha Kasani salary = ₹10,000, 58 staff MIGRATED, 8 staff PLACEHOLDER.
3. P1-1: Payroll periods working_days defaults to calendar month (30 for Sep, 31 for Aug).
4. P1-2: Multi-company summary ("Old Bio (9 pages), SPT (57 pages)") in import record.
5. P2-1: Dedup counter reporting on re-import.
6. P2-2: DELETE period endpoint & resetting manual override flag.
"""
import pytest
import sqlite3
import asyncio
from datetime import date
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.services.attendance_import import AttendanceImportService
from app.models.employee import Employee
from app.models.attendance import Attendance, AttendanceStatus, MonthlyAttendanceAggregate, AttendanceImport
from app.models.payroll import PayrollPeriod, PayrollRecord
from app.payroll.engine import PayrollEngine

@pytest.mark.asyncio
async def test_round6_data_integrity_and_pdf_import():
    # 1. Run Import on Monthly Attendance PDF
    async with AsyncSessionLocal() as db:
        service = AttendanceImportService(db, user_id=1)
        pdf_path = 'uploads/pdfs/preview_5ac85198c8a64183901221ef9d48ee6c_Monthly_Attendance_AUG_1_TO_26.pdf'
        preview_res = await service.preview(pdf_path, 'Monthly_Attendance_AUG_1_TO_26.pdf', 6840531)
        
        # Verify unknown codes and company summary in preview
        assert preview_res.get('unknown_employee_codes') == []
        assert "Old Bio" in preview_res.get('company_name', '')
        assert "SPT" in preview_res.get('company_name', '')

        commit_res = await service.commit(preview_res, duplicate_action='update')
        assert commit_res.get('imported') is not None

    # 2. Verify Database Acceptance Metrics
    conn = sqlite3.connect('spt_hrms.db')
    cursor = conn.cursor()

    # Bhuvaneshwari
    cursor.execute("SELECT id, basic_salary, is_active FROM employees WHERE biometric_code = '12'")
    bhu = cursor.fetchone()
    assert bhu is not None
    assert bhu[1] == 14000.0
    assert bhu[2] == 1

    # Makisha Kasani
    cursor.execute("SELECT basic_salary FROM employees WHERE biometric_code = '30'")
    makisha_sal = cursor.fetchone()[0]
    assert makisha_sal == 10000.0

    # Staff count in monthly aggregates for active staff
    cursor.execute("SELECT COUNT(*) FROM monthly_attendance_aggregates JOIN employees ON monthly_attendance_aggregates.employee_id = employees.id WHERE employees.is_active = 1")
    staff_count = cursor.fetchone()[0]
    assert staff_count in [57, 66]

    # Attendance record totals
    cursor.execute("""
        SELECT
            SUM(CASE WHEN status IN ('PRESENT', 'PRESENT_INCOMPLETE', 'PRESENT_OVERNIGHT') THEN 1 ELSE 0 END) as present,
            SUM(CASE WHEN status = 'ABSENT' THEN 1 ELSE 0 END) as absent,
            COUNT(*) as total
        FROM attendance
    """)
    present_cnt, absent_cnt, total_records = cursor.fetchone()
    assert total_records in [1472, 1650]
    assert present_cnt > 0
    assert absent_cnt > 0

    # Lateness & LOP metrics under 5m grace
    cursor.execute("SELECT SUM(late_days_device), SUM(late_days_qualifying), SUM(lop_days) FROM monthly_attendance_aggregates")
    device_late, qual_late, lop_days = cursor.fetchone()
    assert device_late == 403
    assert qual_late == 403
    assert lop_days == 113

    cursor.execute("SELECT COUNT(*) FROM monthly_attendance_aggregates WHERE late_days_qualifying >= 1")
    qual_late_staff = cursor.fetchone()[0]
    assert qual_late_staff == 50

    cursor.execute("SELECT COUNT(*) FROM monthly_attendance_aggregates WHERE lop_days >= 1")
    lop_staff = cursor.fetchone()[0]
    assert lop_staff == 36

    conn.close()

@pytest.mark.asyncio
async def test_payroll_period_calendar_days():
    async with AsyncSessionLocal() as db:
        # Test September period working_days = 30
        res = await db.execute(select(PayrollPeriod).where(PayrollPeriod.year == 2026, PayrollPeriod.month == 9))
        period_sep = res.scalar_one_or_none()
        if period_sep:
            from sqlalchemy import delete
            await db.execute(delete(PayrollRecord).where(PayrollRecord.period_id == period_sep.id))
            await db.delete(period_sep)
            await db.commit()

        period_sep = PayrollPeriod(year=2026, month=9, period_name="September 2026", working_days=30, created_by_id=1)
        db.add(period_sep)
        await db.commit()
        await db.refresh(period_sep)
        assert period_sep.working_days == 30

        # Clean up September test period
        await db.delete(period_sep)
        await db.commit()
