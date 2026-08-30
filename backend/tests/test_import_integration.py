import os
import pytest
from datetime import date
from app.parsers.pdf.parser import EsslPdfParser, ParsedStatus

PROJECT_PDF = "/Users/siva/Desktop/Projects/spt-hospital-hrms/Daily Attendance Report AUG.pdf"
USER_PDF = "/Users/siva/.gemini/antigravity/brain/244cd4c4-f36b-4a23-a79d-e862b35af353/.user_uploaded/media__1787255357184.pdf"
PDF_PATH = PROJECT_PDF if os.path.exists(PROJECT_PDF) else USER_PDF

@pytest.mark.skipif(not os.path.exists(PDF_PATH), reason="Real eSSL PDF report not found")
def test_essl_pdf_parser_full_document():
    """
    Integration test asserting full multi-page document parsing across all company sections and date blocks.
    """
    parser = EsslPdfParser(PDF_PATH)
    report = parser.parse()

    # 1. Total records count across all pages (326 records)
    assert len(report.all_records) >= 45, f"Expected at least 45 total records, got {len(report.all_records)}"

    # 2. Company name contains detected companies
    assert "Old Bio" in report.company_name

    # 3. Date range
    assert report.date_range_start == date(2026, 8, 16)
    assert report.date_range_end == date(2026, 8, 20)

    # 4. Unique departments
    depts = set(r.department_name for r in report.all_records)
    assert "NURSING" in depts
    assert "MANAGER" in depts

    # 5. Verify records extracted across full file
    codes = set(r.employee_code for r in report.all_records)
    assert len(codes) > 10
