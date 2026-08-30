"""
SPT Hospital HRMS — Monthly Status Report PDF Parser Integration Tests
Validates parsing, auto-detection, and daily grid extraction against the real 66-page PDF.
"""
import os
from datetime import date
import pytest

from app.parsers.pdf.parser import parse_attendance_pdf
from app.parsers.pdf.models import ParsedStatus

MONTHLY_PDF_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "uploads",
    "pdfs",
    "preview_5ac85198c8a64183901221ef9d48ee6c_Monthly_Attendance_AUG_1_TO_26.pdf",
)


def test_monthly_pdf_exists():
    """Ensure the 66-page test PDF exists in the test repository."""
    assert os.path.exists(MONTHLY_PDF_PATH), f"Test PDF not found at {MONTHLY_PDF_PATH}"


def test_monthly_report_autodetect_and_parse():
    """Test auto-detection and complete grid extraction of the 66-page Monthly Status Report."""
    report = parse_attendance_pdf(MONTHLY_PDF_PATH)

    # 1. Report Type Auto-detection
    assert report.report_type == "Monthly Status Report (Detailed Work Duration)"

    # 2. Page & Record Counts
    assert report.total_pages == 66
    assert len(report.monthly_aggregates) == 66
    assert len(report.all_records) == 1650  # 66 employees * 25 days

    # 3. Date Range
    assert report.date_range_start == date(2026, 8, 1)
    assert report.date_range_end == date(2026, 8, 25)

    # 4. Company Name (must cover both devices Old Bio and SPT)
    assert "Old Bio" in report.company_name and "SPT" in report.company_name

    # 5. Shift Codes (must include 'Sam')
    shift_codes = set()
    for r in report.all_records:
        if r.shift_code:
            shift_codes.add(r.shift_code)
    assert "Sam" in shift_codes
    for expected_shift in ["GS", "MS", "NS", "HK", "NTS", "IS", "HKN", "B", "SS", "SNS"]:
        assert expected_shift in shift_codes

    # 6. Page 1 Employee 207 Aggregate Check
    agg0 = report.monthly_aggregates[0]
    assert agg0.employee_code == "207"
    assert agg0.employee_name == "Murugesan"
    assert agg0.present_count == 4
    assert agg0.absent_count == 21
    assert agg0.late_by_days == 2
    assert agg0.total_ot == "21:44"
    assert agg0.average_working_hrs == "11:18"

    # 7. Sample Daily Cell Check (Page 1, Emp 207, Aug 16)
    day_16_rec = None
    for r in report.all_records:
        if r.employee_code == "207" and r.attendance_date == date(2026, 8, 16):
            day_16_rec = r
            break

    assert day_16_rec is not None
    assert day_16_rec.in_time_str == "20:49"
    assert day_16_rec.shift_code == "NTS"

    # 8. Status Counts across 1,650 records (1,288 Present, 333 Absent, 29 No Data)
    status_counts = {}
    for r in report.all_records:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    present_total = status_counts.get(ParsedStatus.PRESENT, 0) + status_counts.get(ParsedStatus.PRESENT_INCOMPLETE, 0)
    assert present_total == 1288
    assert status_counts.get(ParsedStatus.ABSENT, 0) == 333
    assert status_counts.get(ParsedStatus.NO_DATA, 0) == 29

    # 9. Multi-Company Extraction (Old Bio: 9 pages, SPT: 57 pages)
    companies = {}
    for agg in report.monthly_aggregates:
        companies[agg.company_name] = companies.get(agg.company_name, 0) + 1
    assert companies.get("Old Bio") == 9
    assert companies.get("SPT") == 57


def test_lateness_and_lop_assertions():
    """Verify total late instances, qualifying late instances, and top LOP employees under 5m and 15m grace."""
    # Test default 5-minute grace
    report5 = parse_attendance_pdf(MONTHLY_PDF_PATH, grace_minutes=5)
    total_late_device5 = sum(a.late_days_device for a in report5.monthly_aggregates)
    total_late_qualifying5 = sum(a.late_days_qualifying for a in report5.monthly_aggregates)
    total_lop5 = sum(a.lop_days for a in report5.monthly_aggregates)

    assert total_late_device5 == 403
    assert total_late_qualifying5 == 403
    assert total_lop5 == 113

    # Test 15-minute grace override
    report15 = parse_attendance_pdf(MONTHLY_PDF_PATH, grace_minutes=15)
    total_late_qualifying15 = sum(a.late_days_qualifying for a in report15.monthly_aggregates)
    total_lop15 = sum(a.lop_days for a in report15.monthly_aggregates)

    assert total_late_qualifying15 == 286
    assert total_lop15 == 78

    # Check top 6 LOP employees under 15m grace
    agg_map15 = {a.employee_code: a for a in report15.monthly_aggregates}
    assert agg_map15["46"].lop_days == 7   # Sarala (Housekeeping) 23 late -> 7 LOP
    assert agg_map15["56"].lop_days == 7   # Gnanasundari (Housekeeping) 22 late -> 7 LOP
    assert agg_map15["15"].lop_days == 7   # Syed Sajith (Pharmacy) 21 late -> 7 LOP
    assert agg_map15["6"].lop_days == 6    # Senthil Murugan (Manager) 20 late -> 6 LOP
    assert agg_map15["1"].lop_days == 5    # DR Manoj (DR) 17 late -> 5 LOP
    assert agg_map15["62"].lop_days == 5   # Selladurai (Nursing) 15 late -> 5 LOP
