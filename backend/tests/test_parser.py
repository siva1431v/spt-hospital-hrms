import pytest
from app.parsers.pdf.parser import EsslPdfParser
from app.parsers.pdf.models import ParsedStatus, ParseWarning

def test_parse_single_punch_row():
    """Verify that a row with Present (No OutPunch) correctly extracts InTime and skips empty OutTime."""
    parser = EsslPdfParser("mock_path.pdf")
    
    # Page 1, Row 1 (Murugesan)
    line = "1 207 Murugesan NTS 20:49 12:41 00:00 12:41 Present (No OutPunch)"
    record = parser._parse_employee_row(line, None, "Default")
    
    assert record is not None
    assert record.employee_code == "207"
    assert record.employee_name == "Murugesan"
    assert record.shift_code == "NTS"
    assert record.raw_in_time == "20:49"
    assert record.raw_out_time is None
    assert record.raw_work_duration == "12:41"
    assert record.work_minutes == 12 * 60 + 41
    assert record.status == ParsedStatus.PRESENT_INCOMPLETE
    assert ParseWarning.NO_OUT_PUNCH in record.warnings

def test_parse_double_punch_row():
    """Verify that a standard row with both In and Out times parses correctly."""
    parser = EsslPdfParser("mock_path.pdf")
    
    # Page 1, Row 2 (Jagathish)
    line = "2 203 Jagathish IS 09:44 21:19 10:16 1:19 11:35 Present"
    record = parser._parse_employee_row(line, None, "NURSING")
    
    assert record is not None
    assert record.employee_code == "203"
    assert record.employee_name == "Jagathish"
    assert record.shift_code == "IS"
    assert record.raw_in_time == "09:44"
    assert record.raw_out_time == "21:19"
    assert record.raw_work_duration == "10:16"
    assert record.raw_ot == "1:19"
    assert record.work_minutes == 10 * 60 + 16
    assert record.ot_minutes == 1 * 60 + 19
    assert record.status == ParsedStatus.PRESENT
