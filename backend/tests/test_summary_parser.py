"""
Tests for eSSL Monthly Status Report (Summary Report) parser and import pipeline.
"""
import os
from datetime import date
import pytest
from sqlalchemy import select

from app.parsers.pdf.parser import parse_attendance_pdf
from app.parsers.pdf.summary_parser import MonthlySummaryReportParser
from app.services.attendance_import import AttendanceImportService
from app.models.attendance import MonthlyAttendanceAggregate, AttendanceImport

SAMPLE_PDF_PATH = "/Users/siva/.gemini/antigravity/brain/244cd4c4-f36b-4a23-a79d-e862b35af353/.user_uploaded/media_1789837442252.pdf"


def test_summary_report_autodetect_and_parse():
    assert os.path.exists(SAMPLE_PDF_PATH), f"Sample PDF not found at {SAMPLE_PDF_PATH}"

    report = parse_attendance_pdf(SAMPLE_PDF_PATH)
    assert report.report_type == "Monthly Status Report (Summary Report)"
    assert report.date_range_start == date(2026, 8, 1)
    assert report.date_range_end == date(2026, 8, 24)
    assert report.total_pages == 4
    assert len(report.monthly_aggregates) == 66
    assert len(report.all_records) == 66

    # Verify company split
    old_bio = [a for a in report.monthly_aggregates if a.company_name == "Old Bio"]
    spt = [a for a in report.monthly_aggregates if a.company_name == "SPT"]
    assert len(old_bio) == 9
    assert len(spt) == 57


def test_summary_report_spot_checks():
    report = parse_attendance_pdf(SAMPLE_PDF_PATH)
    agg_map = {a.employee_code: a for a in report.monthly_aggregates}

    # 1. Dr Manoj (Code 1)
    manoj = agg_map["1"]
    assert manoj.employee_name == "Dr Manoj"
    assert manoj.department_name == "Dr"
    assert manoj.present_count == 22
    assert manoj.absent_count == 2
    assert manoj.late_by_days == 18
    assert manoj.lop_days == 6
    assert manoj.total_ot == "18:56"

    # 2. Sarala (Code 46)
    sarala = agg_map["46"]
    assert sarala.employee_name == "Sarala"
    assert sarala.department_name == "HOUSE KEEPING"
    assert sarala.present_count == 23
    assert sarala.absent_count == 1
    assert sarala.late_by_days == 22
    assert sarala.lop_days == 7

    # 3. Dr Saranya (Code 64)
    saranya = agg_map["64"]
    assert saranya.employee_name == "Dr Saranya"
    assert saranya.present_count == 13
    assert saranya.absent_count == 1
    assert saranya.late_by_days == 2
    assert saranya.lop_days == 0

    # 4. Senthamilselvi (Code 33)
    selvi = agg_map["33"]
    assert selvi.employee_name == "Senthamilselvi"
    assert selvi.present_count == 2
    assert selvi.absent_count == 3
    assert selvi.late_by_days == 1

    # 5. Aarthi G (Code 13) - night shift / punctual
    aarthi = agg_map["13"]
    assert aarthi.employee_name == "Aarthi G"
    assert aarthi.present_count == 21
    assert aarthi.late_by_days == 0
    assert aarthi.lop_days == 0

    # 6. Ganesh (Code 39)
    ganesh = agg_map["39"]
    assert ganesh.employee_name == "Ganesh"
    assert ganesh.present_count == 21
    assert ganesh.late_by_days == 0

    # 7. Saran (Code 61)
    saran = agg_map["61"]
    assert saran.employee_name == "Saran"
    assert saran.present_count == 22
    assert saran.late_by_days == 10
    assert saran.lop_days == 3

    # 8. Zero-punch staff (Code 208, 209, 210)
    for code in ("208", "209", "210"):
        zero_staff = agg_map[code]
        assert zero_staff.present_count == 0
        assert zero_staff.has_zero_punches is True
        assert zero_staff.lop_days == 0


@pytest.mark.asyncio
async def test_summary_report_import_service_preview_and_commit():
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        service = AttendanceImportService(db=db, user_id=1)
        preview_data = await service.preview(
            pdf_path=SAMPLE_PDF_PATH,
            filename="Monthly_Attendance_Summary_Aug.pdf",
            file_size=os.path.getsize(SAMPLE_PDF_PATH),
        )

        assert preview_data["report_type"] == "Monthly Status Report (Summary Report)"
        assert preview_data["statistics"]["total_records"] == 66
        assert len(preview_data["records"]) == 66
        assert len(preview_data["monthly_aggregates"]) == 66

        # Commit preview
        commit_res = await service.commit(
            preview_data=preview_data,
            duplicate_action="skip",
        )
        assert commit_res["status"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS")
        assert commit_res["total_in_file"] == 66

        # Verify MonthlyAttendanceAggregate saved in DB
        aggs_db = await db.execute(
            select(MonthlyAttendanceAggregate).where(
                MonthlyAttendanceAggregate.year == 2026,
                MonthlyAttendanceAggregate.month == 8,
            )
        )
        saved = aggs_db.scalars().all()
        assert len(saved) >= 66
