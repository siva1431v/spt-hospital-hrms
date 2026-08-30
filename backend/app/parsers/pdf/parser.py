"""
SPT Hospital HRMS — eSSL PDF Parser
Robustly extracts attendance data from eSSL Daily Attendance Report PDFs.

The parser handles:
- Multi-page PDFs (does NOT stop at page 1)
- Multiple attendance dates per report
- Multiple departments per date
- Absent records (00:00 / 00:00)
- No OutPunch records ("Present (No OutPunch)")
- Overnight shifts (out < in)
- Suspicious durations (flagged as exceptions)
- Multi-word employee names
- Header repetition across pages
"""
import re
import logging
from datetime import date, datetime, timedelta
from typing import Optional

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

from app.parsers.pdf.models import (
    ParsedReport, ParsedDateBlock, ParsedDepartment,
    ParsedAttendanceRecord, ParsedStatus, ParseWarning
)

logger = logging.getLogger(__name__)

# ─── Regex Patterns ───────────────────────────────────────────────────────────
# Attendance date line: "Attendance Date: 16-Aug-2026" or "Attendance Date 16-Aug-2026"
RE_ATTENDANCE_DATE = re.compile(
    r"Attendance\s+Date\s*[:\-]?\s*(\d{1,2}[-/]\w{3}[-/]\d{4})",
    re.IGNORECASE,
)

# Date range: "Aug 16 2026 To Aug 20 2026"
RE_DATE_RANGE = re.compile(
    r"(\w{3}\s+\d{1,2}\s+\d{4})\s+To\s+(\w{3}\s+\d{1,2}\s+\d{4})",
    re.IGNORECASE,
)

# Report type
RE_REPORT_TYPE = re.compile(r"Daily Attendance Report", re.IGNORECASE)
RE_BASIC_REPORT = re.compile(r"Basic Report", re.IGNORECASE)

# Company/hospital name line (typically appears near top)
RE_COMPANY = re.compile(r"(?:Company|Hospital|Organisation|Organization)\s*[:\-]?\s*(.+)", re.IGNORECASE)

# Department header: "Department Default", "Department: NURSING", "Dept : NURSING"
RE_DEPT_HEADER = re.compile(r"(?:Department|Dept)\s*[:\-]?\s*(.+)", re.IGNORECASE)

# Time pattern: HH:MM
RE_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")

# Duration pattern: HH:MM (can exceed 24h)
RE_DURATION = re.compile(r"^(\d{1,3}):(\d{2})$")

# Status patterns
STATUS_ABSENT_PATTERNS = ["absent", "a"]
STATUS_INCOMPLETE_PATTERNS = ["no outpunch", "no out punch", "present (no outpunch)", "(no", "no out"]
STATUS_PRESENT_PATTERNS = ["present", "p"]

# Known header/footer lines to skip
SKIP_LINE_PATTERNS = [
    re.compile(r"SNo\s+E\.?\s*Code", re.IGNORECASE),
    re.compile(r"InTime\s+OutTime", re.IGNORECASE),
    re.compile(r"Work Dur", re.IGNORECASE),
    re.compile(r"Page\s+\d+\s+of\s+\d+", re.IGNORECASE),
    re.compile(r"Total\s+:", re.IGNORECASE),
    re.compile(r"Report generated", re.IGNORECASE),
    re.compile(r"^\s*$"),  # blank lines
]

DATE_FORMATS = [
    "%d-%b-%Y",   # 16-Aug-2026
    "%d/%b/%Y",   # 16/Aug/2026
    "%d-%B-%Y",   # 16-August-2026
    "%d-%m-%Y",   # 16-08-2026
    "%d/%m/%Y",   # 16/08/2026
    "%b %d %Y",   # Aug 16 2026
    "%B %d %Y",   # August 16 2026
]


def parse_date(date_str: str) -> Optional[date]:
    """Try multiple date formats and return a date object."""
    date_str = date_str.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    logger.warning(f"Could not parse date: {date_str!r}")
    return None


def parse_duration_to_minutes(duration_str: str) -> Optional[int]:
    """
    Parse a duration string like "08:30" or "24:06" into total minutes.
    Returns None if the string is not a valid duration.
    """
    if not duration_str or duration_str.strip() in ("", "00:00", "--", "N/A"):
        return None
    duration_str = duration_str.strip()
    m = RE_DURATION.match(duration_str)
    if m:
        hours = int(m.group(1))
        minutes = int(m.group(2))
        return hours * 60 + minutes
    return None


def classify_status(
    raw_status: Optional[str],
    raw_in: Optional[str],
    raw_out: Optional[str],
    raw_remarks: Optional[str],
) -> tuple[ParsedStatus, list[ParseWarning]]:
    """
    Classify attendance status from raw PDF values.
    Returns (status, list_of_warnings).
    """
    warnings = []
    raw_status_lower = (raw_status or "").lower().strip()
    raw_remarks_lower = (raw_remarks or "").lower().strip()

    # Check for no-out-punch first (takes priority over "present")
    if any(p in raw_status_lower for p in STATUS_INCOMPLETE_PATTERNS) or \
       any(p in raw_remarks_lower for p in STATUS_INCOMPLETE_PATTERNS):
        warnings.append(ParseWarning.NO_OUT_PUNCH)
        return ParsedStatus.PRESENT_INCOMPLETE, warnings

    # Absent check
    if any(p == raw_status_lower for p in STATUS_ABSENT_PATTERNS):
        # Double-check: both times are 00:00
        if raw_in in (None, "", "00:00") and raw_out in (None, "", "00:00"):
            warnings.append(ParseWarning.ZERO_TIMES)
        return ParsedStatus.ABSENT, warnings

    # Present
    if any(p == raw_status_lower or raw_status_lower.startswith(p) for p in STATUS_PRESENT_PATTERNS):
        return ParsedStatus.PRESENT, warnings

    # If both times are 00:00 and status is unclear, treat as absent
    if raw_in in (None, "", "00:00") and raw_out in (None, "", "00:00"):
        warnings.append(ParseWarning.ZERO_TIMES)
        return ParsedStatus.ABSENT, warnings

    return ParsedStatus.PRESENT, warnings


def detect_overnight(in_str: Optional[str], out_str: Optional[str]) -> bool:
    """
    Detect if a shift is overnight (out_time < in_time).
    Example: InTime=18:49, OutTime=09:37 → overnight.
    """
    if not in_str or not out_str:
        return False
    in_m = RE_TIME.match(in_str.strip())
    out_m = RE_TIME.match(out_str.strip())
    if not in_m or not out_m:
        return False
    in_minutes = int(in_m.group(1)) * 60 + int(in_m.group(2))
    out_minutes = int(out_m.group(1)) * 60 + int(out_m.group(2))
    # If both are 00:00, not overnight (absent)
    if in_minutes == 0 and out_minutes == 0:
        return False
    return out_minutes < in_minutes


def is_suspicious_duration(work_minutes: Optional[int]) -> bool:
    """Flag durations over 16 hours as suspicious."""
    if work_minutes is None:
        return False
    return work_minutes > 16 * 60  # 16 hours in minutes


def should_skip_line(line: str) -> bool:
    """Return True if this line should be skipped (header, footer, blank)."""
    return any(p.search(line) for p in SKIP_LINE_PATTERNS)


class EsslPdfParser:
    """
    Parses eSSL Daily Attendance Report (Basic Report) PDFs.

    Strategy:
    1. Extract all text using pdfplumber (best for tabular data), fall back to PyMuPDF.
    2. Process line by line, tracking current date context and department context.
    3. Parse employee rows using flexible column detection.
    4. Handle all edge cases: overnight, absent, no-outpunch, suspicious durations.
    """

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self._pages_text: list[list[str]] = []  # list of pages, each page = list of lines

    def _extract_text_pdfplumber(self) -> list[list[str]]:
        """Extract text line by line using pdfplumber (preferred — better column handling)."""
        pages = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
                lines = [line for line in text.splitlines()]
                pages.append(lines)
        return pages

    def _extract_text_pymupdf(self) -> list[list[str]]:
        """Fallback: extract text using PyMuPDF."""
        pages = []
        doc = fitz.open(self.pdf_path)
        for page in doc:
            text = page.get_text("text") or ""
            lines = [line for line in text.splitlines()]
            pages.append(lines)
        doc.close()
        return pages

    def _extract_all_text(self) -> list[list[str]]:
        """Extract text from all pages using best available library."""
        if HAS_PDFPLUMBER:
            try:
                return self._extract_text_pdfplumber()
            except Exception as e:
                logger.warning(f"pdfplumber failed: {e}. Trying PyMuPDF.")

        if HAS_PYMUPDF:
            try:
                return self._extract_text_pymupdf()
            except Exception as e:
                logger.error(f"PyMuPDF also failed: {e}")

        raise RuntimeError("No PDF extraction library available. Install pdfplumber or PyMuPDF.")

    def _parse_employee_row(
        self,
        line: str,
        attendance_date: Optional[date],
        department_name: Optional[str],
    ) -> Optional[ParsedAttendanceRecord]:
        """
        Parse a single employee attendance row from the PDF.

        Expected column layout (from eSSL report):
        SNo | E.Code | Employee Name | Shift | InTime | OutTime | WorkDur | OT | TotalDur | Status | Remarks

        The parser uses token-based detection rather than fixed column positions
        because PDF text extraction does not guarantee exact character positions.
        """
        line = line.strip()
        if not line or should_skip_line(line):
            return None

        tokens = line.split()
        if len(tokens) < 4:
            return None

        # First token should be a serial number (integer)
        sno = tokens[0]
        if not sno.isdigit():
            return None

        # Second token should be employee code (typically numeric, but allow alphanumeric)
        emp_code = tokens[1]
        if not (emp_code.isdigit() or re.match(r'^[A-Z0-9\-]+$', emp_code)):
            return None

        record = ParsedAttendanceRecord(
            attendance_date=attendance_date,
            department_name=department_name,
            raw_sno=sno,
            raw_employee_code=emp_code,
            employee_code=emp_code,
        )

        # Find the shift code by looking for known shift-like tokens
        # Shift codes from the PDF are typically 2-4 uppercase letters
        # Times are HH:MM format
        # Strategy: scan from token[2] onwards to find name, shift, times

        # Identify time tokens (HH:MM pattern)
        time_indices = [
            i for i, t in enumerate(tokens)
            if RE_TIME.match(t) and i > 1
        ]

        # Check if the line is an incomplete punch (no outpunch)
        is_no_outpunch = any(p in line.lower() for p in STATUS_INCOMPLETE_PATTERNS)

        if is_no_outpunch and len(time_indices) >= 1:
            first_time_idx = time_indices[0]
            shift_idx = first_time_idx - 1
            if shift_idx > 1:
                name_tokens = tokens[2:shift_idx]
                shift_code = tokens[shift_idx] if shift_idx < len(tokens) else None
            else:
                name_tokens = tokens[2:first_time_idx]
                shift_code = None

            record.raw_employee_name = " ".join(name_tokens) if name_tokens else None
            record.employee_name = record.raw_employee_name
            record.raw_shift = shift_code
            record.shift_code = shift_code

            record.raw_in_time = tokens[first_time_idx]
            record.raw_out_time = None
            record.in_time_str = tokens[first_time_idx]
            record.out_time_str = None

            # After first_time_idx, find duration-like tokens
            remaining = tokens[first_time_idx + 1:]
            duration_tokens = []
            status_tokens = []
            remarks_tokens = []

            dur_found = 0
            for i, tok in enumerate(remaining):
                if RE_DURATION.match(tok) and dur_found < 3:
                    duration_tokens.append(tok)
                    dur_found += 1
                else:
                    rest = remaining[i:]
                    for j, rt in enumerate(rest):
                        rt_lower = rt.lower()
                        if any(p in rt_lower for p in ["present", "absent", "p", "a"]):
                            status_tokens = rest[:min(j + 4, len(rest))]
                            remarks_tokens = rest[min(j + 4, len(rest)):]
                            break
                    else:
                        status_tokens = rest
                    break

            if len(duration_tokens) >= 1:
                record.raw_work_duration = duration_tokens[0]
                record.work_minutes = parse_duration_to_minutes(duration_tokens[0])
            if len(duration_tokens) >= 2:
                record.raw_ot = duration_tokens[1]
                record.ot_minutes = parse_duration_to_minutes(duration_tokens[1])
            if len(duration_tokens) >= 3:
                record.raw_total_duration = duration_tokens[2]
                record.total_minutes = parse_duration_to_minutes(duration_tokens[2])

            raw_status = " ".join(status_tokens).strip() if status_tokens else None
            raw_remarks = " ".join(remarks_tokens).strip() if remarks_tokens else None
            record.raw_status = raw_status
            record.raw_remarks = raw_remarks

        elif len(time_indices) >= 2:
            first_time_idx = time_indices[0]

            # Shift code is the token just before the first time
            # Name is everything between emp_code token and shift code
            shift_idx = first_time_idx - 1

            if shift_idx > 1:
                name_tokens = tokens[2:shift_idx]
                shift_code = tokens[shift_idx] if shift_idx < len(tokens) else None
            else:
                name_tokens = tokens[2:first_time_idx]
                shift_code = None

            record.raw_employee_name = " ".join(name_tokens) if name_tokens else None
            record.employee_name = record.raw_employee_name
            record.raw_shift = shift_code
            record.shift_code = shift_code

            # Parse in_time and out_time
            raw_in = tokens[time_indices[0]] if len(time_indices) > 0 else None
            raw_out = tokens[time_indices[1]] if len(time_indices) > 1 else None

            record.raw_in_time = raw_in
            record.raw_out_time = raw_out
            record.in_time_str = raw_in
            record.out_time_str = raw_out

            # After out_time, look for duration tokens (HH:MM including those > 24:00)
            after_times = time_indices[1] + 1
            remaining = tokens[after_times:]

            # Find duration-like tokens (HH:MM including 24:MM etc.)
            duration_tokens = []
            status_tokens = []
            remarks_tokens = []

            dur_found = 0
            for i, tok in enumerate(remaining):
                if RE_DURATION.match(tok) and dur_found < 3:
                    duration_tokens.append(tok)
                    dur_found += 1
                else:
                    # Everything after the 3 duration values is status/remarks
                    status_start = i
                    rest = remaining[i:]
                    # Status is the first non-duration token(s)
                    # Look for known status keywords
                    for j, rt in enumerate(rest):
                        rt_lower = rt.lower()
                        if any(p in rt_lower for p in ["present", "absent", "p", "a"]):
                            # Grab status (may be multi-word like "Present (No OutPunch)")
                            status_tokens = rest[:min(j + 4, len(rest))]
                            remarks_tokens = rest[min(j + 4, len(rest)):]
                            break
                    else:
                        status_tokens = rest
                    break

            if len(duration_tokens) >= 1:
                record.raw_work_duration = duration_tokens[0]
                record.work_minutes = parse_duration_to_minutes(duration_tokens[0])
            if len(duration_tokens) >= 2:
                record.raw_ot = duration_tokens[1]
                record.ot_minutes = parse_duration_to_minutes(duration_tokens[1])
            if len(duration_tokens) >= 3:
                record.raw_total_duration = duration_tokens[2]
                record.total_minutes = parse_duration_to_minutes(duration_tokens[2])

            raw_status = " ".join(status_tokens).strip() if status_tokens else None
            raw_remarks = " ".join(remarks_tokens).strip() if remarks_tokens else None
            record.raw_status = raw_status
            record.raw_remarks = raw_remarks

        else:
            # No time tokens found — this might be an absent record or malformed
            # Try to extract what we can
            name_end = min(4, len(tokens))
            record.raw_employee_name = " ".join(tokens[2:name_end])
            record.employee_name = record.raw_employee_name
            record.raw_status = " ".join(tokens[name_end:]) if name_end < len(tokens) else None

        # Classify status
        record.status, warnings = classify_status(
            record.raw_status,
            record.raw_in_time,
            record.raw_out_time,
            record.raw_remarks,
        )
        record.warnings.extend(warnings)

        # Detect overnight
        if record.status == ParsedStatus.PRESENT:
            if detect_overnight(record.raw_in_time, record.raw_out_time):
                record.is_overnight = True
                record.status = ParsedStatus.PRESENT_OVERNIGHT
                record.warnings.append(ParseWarning.OVERNIGHT_SHIFT)

        # Flag suspicious duration
        if record.work_minutes is not None and is_suspicious_duration(record.work_minutes):
            record.warnings.append(ParseWarning.SUSPICIOUS_DURATION)
            record.parse_errors.append(
                f"Suspicious work duration: {record.raw_work_duration} ({record.work_minutes} minutes)"
            )

        return record

    def _detect_department(self, line: str, prev_context: dict) -> Optional[str]:
        """
        Attempt to detect a department header line.
        Department lines in the eSSL PDF typically appear as:
        - "Dept : NURSING" or "Department: NURSING"
        - Or as a standalone header before employee rows
        """
        line = line.strip()
        if not line:
            return None

        # Explicit dept prefix
        m = RE_DEPT_HEADER.match(line)
        if m:
            raw_dept = m.group(1).strip()
            if raw_dept.upper() in ["DT HR", "DT_HR", "DIET HR"]:
                return "HR"
            if raw_dept.upper() in ["DR", "DR."]:
                return "DOCTOR"
            return raw_dept

        # Lines like "NURSING" or "HOUSE KEEPING" that appear between date and employee rows
        # Heuristic: ALL CAPS, no digits, length between 2 and 60 chars, not a known header
        if (
            line.isupper()
            and 2 < len(line) <= 60
            and not any(d.isdigit() for d in line)
            and not should_skip_line(line)
            and not RE_ATTENDANCE_DATE.search(line)
        ):
            # Make sure it doesn't look like a table header
            header_keywords = {"INTIME", "OUTTIME", "SHIFT", "STATUS", "REMARKS", "WORK", "DURATION", "SL", "SN", "SNO"}
            upper_words = set(line.upper().split())
            if not upper_words.intersection(header_keywords):
                return line

        return None

    def parse(self) -> ParsedReport:
        """
        Parse the entire eSSL PDF and return a structured ParsedReport.
        Processes ALL pages.
        """
        self._pages_text = self._extract_all_text()

        report = ParsedReport(total_pages=len(self._pages_text))
        current_date: Optional[date] = None
        current_dept: Optional[str] = None
        current_date_block: Optional[ParsedDateBlock] = None
        current_dept_section: Optional[ParsedDepartment] = None
        page_context: dict = {}

        # Process all pages sequentially
        for page_num, page_lines in enumerate(self._pages_text):
            for line in page_lines:
                stripped = line.strip()
                if not stripped:
                    continue

                # ── Detect report type ─────────────────────────────────────
                if RE_REPORT_TYPE.search(stripped) and report.report_type is None:
                    report.report_type = "Daily Attendance Report"
                    if RE_BASIC_REPORT.search(stripped):
                        report.report_type = "Daily Attendance Report (Basic Report)"

                # ── Detect company name ────────────────────────────────────
                cm = RE_COMPANY.match(stripped)
                if cm:
                    raw_cname = cm.group(1).strip()
                    clean_cname = re.sub(r"\s+Printed\s+On\s*:.*$", "", raw_cname, flags=re.IGNORECASE).strip()
                    if report.company_name is None:
                        report.company_name = clean_cname
                    elif clean_cname not in report.company_name:
                        report.company_name = f"{report.company_name}, {clean_cname}"

                # ── Detect date range ──────────────────────────────────────
                if report.date_range_start is None:
                    dr_m = RE_DATE_RANGE.search(stripped)
                    if dr_m:
                        report.date_range_start = parse_date(dr_m.group(1))
                        report.date_range_end = parse_date(dr_m.group(2))

                # ── Detect attendance date ─────────────────────────────────
                ad_m = RE_ATTENDANCE_DATE.search(stripped)
                if ad_m:
                    parsed_date = parse_date(ad_m.group(1))
                    if parsed_date and parsed_date != current_date:
                        current_date = parsed_date
                        current_dept = None
                        current_date_block = ParsedDateBlock(attendance_date=parsed_date)
                        report.date_blocks.append(current_date_block)
                        current_dept_section = None
                    continue

                if current_date is None:
                    # Haven't found a date yet — skip non-structural lines
                    continue

                # ── Skip table headers and footers ─────────────────────────
                if should_skip_line(stripped):
                    continue

                # ── Detect department ──────────────────────────────────────
                dept_name = self._detect_department(stripped, page_context)
                if dept_name:
                    current_dept = dept_name
                    current_dept_section = ParsedDepartment(name=dept_name)
                    if current_date_block:
                        current_date_block.departments.append(current_dept_section)
                    continue

                # ── Parse employee row ─────────────────────────────────────
                record = self._parse_employee_row(stripped, current_date, current_dept)
                if record:
                    if current_dept_section is None:
                        # Records appearing before a department header
                        current_dept_section = ParsedDepartment(name="UNKNOWN")
                        if current_date_block:
                            current_date_block.departments.append(current_dept_section)
                    current_dept_section.records.append(record)

        logger.info(
            f"Parsed {report.total_pages} pages, "
            f"{len(report.date_blocks)} date blocks, "
            f"{len(report.all_records)} total records"
        )
        return report


def parse_attendance_pdf(pdf_path: str, grace_minutes: int = 5) -> ParsedReport:
    """
    Public interface: auto-detect report type and parse an eSSL attendance PDF.

    Sniffs page-1 title text to determine the report format:
    - "Monthly Status Report" → MonthlyStatusReportParser (grid layout)
    - Anything else → EsslPdfParser (row-list Daily Attendance Report)

    Args:
        pdf_path: Absolute path to the PDF file.
        grace_minutes: Attendance grace period in minutes (default 5).

    Returns:
        ParsedReport with all extracted attendance data.

    Raises:
        FileNotFoundError: If the PDF does not exist.
        ValueError: If the PDF does not appear to be an eSSL attendance report.
        RuntimeError: If no PDF library is available.
    """
    import os
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    # Sniff report type from page 1
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            page1_text = pdf.pages[0].extract_text(x_tolerance=3, y_tolerance=3) or ""
    except Exception:
        page1_text = ""

    if "Monthly Status Report" in page1_text:
        logger.info("Detected report type: Monthly Status Report (Detailed Work Duration)")
        from app.parsers.pdf.monthly_parser import MonthlyStatusReportParser
        parser = MonthlyStatusReportParser(pdf_path, grace_minutes=grace_minutes)
        report = parser.parse()
    else:
        logger.info("Detected report type: Daily Attendance Report (default path)")
        parser = EsslPdfParser(pdf_path)
        report = parser.parse()

    if report.report_type is None:
        logger.warning("Could not confirm report type from PDF content")
    if len(report.all_records) == 0:
        logger.warning("No attendance records were extracted from the PDF")

    return report

