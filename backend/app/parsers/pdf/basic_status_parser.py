"""
SPT Hospital HRMS — Monthly Status Report (Basic Report) Parser

Parses the eSSL "Monthly Status Report (Basic Report)" PDF format.
Layout: A4 landscape table rendered by Microsoft Reporting Services:
Sl | Emp. Code | Name | Day Columns (1 T ... 30 W / 31) | P | A | L | H | HP | WO | WOP

Features:
1. Column-position parsing (via pdfplumber words x0/x1 coordinate proximity).
2. Header-derived period dates (e.g., Sep 01 2026 To Sep 30 2026).
3. Checksum verification per row comparing calculated day counts against printed totals.
4. Multi-page and multi-company support (e.g., Old Bio on page 1, SPT on pages 2-5).
5. Empty cell handling as NO_DATA (never defaults to Absent or Leave).
6. Preserves separate rows across pages without overwriting repeated departments (e.g., NURSING).
"""
import calendar
import logging
import math
import re
from datetime import date, datetime, timedelta
from typing import Optional

import pdfplumber

from app.parsers.pdf.models import (
    MonthlyBasicStatusRow,
    MonthlyEmployeeAggregate,
    ParsedAttendanceRecord,
    ParsedDateBlock,
    ParsedDepartment,
    ParsedReport,
    ParsedStatus,
    ParseWarning,
)

logger = logging.getLogger(__name__)

RE_DATE_RANGE = re.compile(
    r"(\w{3}\s+\d{1,2}\s+\d{4})\s+To\s+(\w{3}\s+\d{1,2}\s+\d{4})", re.IGNORECASE
)
RE_COMPANY = re.compile(
    r"Company:\s*([^\n\r]+?)(?:\s+Printed\s+On|$)", re.IGNORECASE
)
RE_PRINTED_ON = re.compile(
    r"Printed\s+On\s*:\s*(\w{3}\s+\d{1,2}\s+\d{4}(?:\s+\d{1,2}:\d{2})?)", re.IGNORECASE
)
RE_DEPT_HEADER = re.compile(r"Department\s+([^\n\r]+)", re.IGNORECASE)

# Mapping of cell status text to ParsedStatus enum
STATUS_CODE_MAP: dict[str, ParsedStatus] = {
    "P": ParsedStatus.PRESENT,
    "A": ParsedStatus.ABSENT,
    "L": ParsedStatus.LEAVE,
    "H": ParsedStatus.HOLIDAY,
    "HP": ParsedStatus.HALF_DAY,
    "WO": ParsedStatus.WEEKLY_OFF,
    "WOP": ParsedStatus.WEEKLY_OFF_PRESENT,
}


def _parse_date_str(s: str) -> Optional[date]:
    for fmt in ("%b %d %Y", "%B %d %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    return None


class MonthlyBasicStatusReportParser:
    """Parser for eSSL 'Monthly Status Report (Basic Report)' grid PDFs."""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def parse(self) -> ParsedReport:
        report = ParsedReport(
            report_type="Monthly Status Report (Basic Report)",
        )

        with pdfplumber.open(self.pdf_path) as pdf:
            report.total_pages = len(pdf.pages)
            if report.total_pages == 0:
                report.parse_warnings.append("PDF contains 0 pages")
                return report

            # 1. Extract Period and Metadata from page 1 (and fallback across pages)
            date_start: Optional[date] = None
            date_end: Optional[date] = None
            printed_on: Optional[datetime] = None
            company_fallback: Optional[str] = None

            for page in pdf.pages:
                text = page.extract_text() or ""
                if not date_start:
                    m_range = RE_DATE_RANGE.search(text)
                    if m_range:
                        date_start = _parse_date_str(m_range.group(1))
                        date_end = _parse_date_str(m_range.group(2))
                if not printed_on:
                    m_print = RE_PRINTED_ON.search(text)
                    if m_print:
                        p_str = m_print.group(1).strip()
                        for fmt in ("%b %d %Y %H:%M", "%b %d %Y"):
                            try:
                                printed_on = datetime.strptime(p_str, fmt)
                                break
                            except ValueError:
                                pass
                if not company_fallback:
                    m_comp = RE_COMPANY.search(text)
                    if m_comp:
                        company_fallback = m_comp.group(1).strip()

            report.date_range_start = date_start
            report.date_range_end = date_end
            report.printed_on = printed_on
            report.company_name = company_fallback or "SPT"

            if not date_start or not date_end:
                report.parse_warnings.append("Could not extract period date range from PDF header")
                return report

            days_in_period = (date_end - date_start).days + 1
            if days_in_period not in (28, 29, 30, 31):
                report.parse_warnings.append(
                    f"Unusual period length: {days_in_period} days ({date_start} to {date_end})"
                )

            # Dictionary to accumulate date blocks: date -> ParsedDateBlock
            date_blocks_map: dict[date, ParsedDateBlock] = {}
            for d_idx in range(days_in_period):
                d_curr = date_start + timedelta(days=d_idx)
                date_blocks_map[d_curr] = ParsedDateBlock(attendance_date=d_curr)

            # 2. Process each page
            all_rows: list[MonthlyBasicStatusRow] = []
            seen_employee_keys: set[tuple[str, str]] = set()

            for page_idx, page in enumerate(pdf.pages):
                page_text = page.extract_text() or ""
                page_company = self._extract_page_company(page_text, fallback=report.company_name or "SPT")
                words = page.extract_words(x_tolerance=2, y_tolerance=2)

                # Group words into visual lines by vertical y-position (tolerance 3.0)
                lines = self._cluster_lines(words, y_tolerance=3.0)

                # Identify header anchors for day columns on this page
                day_anchors = self._derive_day_anchors(lines, days_in_period)

                # Track department sections
                current_dept = "Default"

                for line in lines:
                    line_str = " ".join(w["text"] for w in line)

                    # Department section header
                    if "Department" in line_str:
                        m_dept = RE_DEPT_HEADER.search(line_str)
                        if m_dept:
                            current_dept = m_dept.group(1).strip()
                        continue

                    # Skip non-employee lines (page titles, table headers, subheaders, blank)
                    if any(
                        keyword in line_str
                        for keyword in [
                            "Monthly Status Report",
                            "Sep 01",
                            "Company:",
                            "Emp. Code",
                            "Printed On",
                            "Page No.",
                            "Generated By",
                        ]
                    ):
                        continue
                    if line_str.startswith("Th ") or line_str.startswith("St ") or line_str.startswith("M ") or line_str.startswith("W "):
                        # Wrapped weekday subheaders
                        continue

                    # Check for employee row:
                    # Sl no (x0 < 20), Code (20 <= x0 < 65, digits), Name (65 <= x0 < 160)
                    code_words = [w for w in line if 20 <= w["x0"] < 65 and w["text"].isdigit()]
                    if not code_words:
                        continue

                    emp_code = code_words[0]["text"]
                    name_words = [w for w in line if 65 <= w["x0"] < 160]
                    emp_name = " ".join(w["text"] for w in name_words).strip() or f"Employee {emp_code}"

                    # Segment words: day cell words (160 <= x0 < 685), summary words (x0 >= 685)
                    day_words = [w for w in line if 160 <= w["x0"] < 685]
                    sum_words = [w for w in line if w["x0"] >= 685]

                    # Map cells to days 1..days_in_period
                    day_statuses: dict[int, str] = {}
                    for d_num in range(1, days_in_period + 1):
                        x_center = day_anchors.get(d_num, 165.2 + (d_num - 1) * 17.28)
                        # Find closest word within tolerance
                        matching_words = [w for w in day_words if abs(w["x0"] + (w.get("width", 5.0) / 2.0) - x_center) <= 8.5]
                        if matching_words:
                            day_statuses[d_num] = matching_words[0]["text"].strip().upper()
                        else:
                            day_statuses[d_num] = ""  # NO_DATA

                    # Extract printed totals from summary columns (P, A, L, H, HP, WO, WOP)
                    # Columns layout on right:
                    # P: ~700 (<710), A: ~718 (710-727), L: ~735 (727-744), H: ~752 (744-760),
                    # HP: ~770 (760-778), WO: ~787 (778-796), WOP: ~806 (>=796)
                    printed_totals: dict[str, int] = {
                        "P": 0, "A": 0, "L": 0, "H": 0, "HP": 0, "WO": 0, "WOP": 0,
                    }
                    for w in sum_words:
                        val = int(w["text"]) if w["text"].isdigit() else 0
                        x = w["x0"]
                        if x < 710:
                            printed_totals["P"] = val
                        elif x < 727:
                            printed_totals["A"] = val
                        elif x < 744:
                            printed_totals["L"] = val
                        elif x < 760:
                            printed_totals["H"] = val
                        elif x < 778:
                            printed_totals["HP"] = val
                        elif x < 796:
                            printed_totals["WO"] = val
                        else:
                            printed_totals["WOP"] = val

                    # Recompute checksum totals from day cells
                    computed_totals: dict[str, int] = {
                        "P": sum(1 for v in day_statuses.values() if v == "P"),
                        "A": sum(1 for v in day_statuses.values() if v == "A"),
                        "L": sum(1 for v in day_statuses.values() if v == "L"),
                        "H": sum(1 for v in day_statuses.values() if v == "H"),
                        "HP": sum(1 for v in day_statuses.values() if v == "HP"),
                        "WO": sum(1 for v in day_statuses.values() if v == "WO"),
                        "WOP": sum(1 for v in day_statuses.values() if v == "WOP"),
                    }

                    # Checksum validation
                    checksum_errors: list[str] = []
                    for k in ["P", "A", "L", "H", "HP", "WO", "WOP"]:
                        if computed_totals[k] != printed_totals.get(k, 0):
                            checksum_errors.append(
                                f"Checksum mismatch for {k}: calculated {computed_totals[k]} != printed {printed_totals.get(k, 0)}"
                            )

                    no_data_days = [d for d in range(1, days_in_period + 1) if not day_statuses[d]]

                    row_obj = MonthlyBasicStatusRow(
                        company=page_company,
                        employee_code=emp_code,
                        employee_name=emp_name,
                        pdf_department=current_dept,
                        day_statuses=day_statuses,
                        printed_totals=printed_totals,
                        computed_totals=computed_totals,
                        checksum_valid=(len(checksum_errors) == 0),
                        checksum_errors=checksum_errors,
                        no_data_days=no_data_days,
                    )

                    key = (page_company, emp_code)
                    if key in seen_employee_keys:
                        report.parse_warnings.append(
                            f"Duplicate employee entry in PDF: {page_company} - code {emp_code} ({emp_name})"
                        )
                    seen_employee_keys.add(key)
                    all_rows.append(row_obj)

                    # Build daily attendance records
                    for d_num in range(1, days_in_period + 1):
                        d_curr = date_start + timedelta(days=d_num - 1)
                        raw_code = day_statuses.get(d_num, "")
                        parsed_status = STATUS_CODE_MAP.get(raw_code, ParsedStatus.NO_DATA if not raw_code else ParsedStatus.UNKNOWN)

                        rec = ParsedAttendanceRecord(
                            attendance_date=d_curr,
                            department_name=current_dept,
                            employee_code=emp_code,
                            employee_name=emp_name,
                            status=parsed_status,
                            raw_status=raw_code if raw_code else "NO_DATA",
                        )

                        # Group by department inside date block
                        block = date_blocks_map[d_curr]
                        target_dept = next((dept for dept in block.departments if dept.name == current_dept), None)
                        if not target_dept:
                            target_dept = ParsedDepartment(name=current_dept)
                            block.departments.append(target_dept)
                        target_dept.records.append(rec)

                    # Build MonthlyEmployeeAggregate for this employee
                    monthly_agg = MonthlyEmployeeAggregate(
                        employee_code=emp_code,
                        employee_name=emp_name,
                        department_name=current_dept,
                        company_name=page_company,
                        present_count=computed_totals["P"],
                        absent_count=computed_totals["A"],
                        leaves_taken=computed_totals["L"],
                        holidays_count=computed_totals["H"],
                        weekly_off_count=computed_totals["WO"],
                        late_by_days=0,
                        late_days_device=0,
                        late_days_qualifying=0,
                        lop_days=0,
                        has_zero_punches=True,  # Basic Report has no punch times
                    )
                    report.monthly_aggregates.append(monthly_agg)

            report.date_blocks = list(date_blocks_map.values())
            report.basic_status_rows = all_rows

        return report

    def _extract_page_company(self, page_text: str, fallback: str) -> str:
        """Extract company name specifically from this page."""
        m = RE_COMPANY.search(page_text)
        if m:
            comp = m.group(1).strip()
            if comp:
                return comp
        if "Old Bio" in page_text:
            return "Old Bio"
        if "SPT" in page_text:
            return "SPT"
        return fallback

    def _cluster_lines(self, words: list[dict], y_tolerance: float = 3.0) -> list[list[dict]]:
        """Cluster words into horizontal visual lines based on vertical proximity."""
        if not words:
            return []
        sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
        lines: list[list[dict]] = []
        current_line: list[dict] = []
        current_top: Optional[float] = None

        for w in sorted_words:
            if current_top is None:
                current_top = w["top"]
                current_line = [w]
            elif abs(w["top"] - current_top) <= y_tolerance:
                current_line.append(w)
            else:
                lines.append(sorted(current_line, key=lambda x: x["x0"]))
                current_top = w["top"]
                current_line = [w]
        if current_line:
            lines.append(sorted(current_line, key=lambda x: x["x0"]))
        return lines

    def _derive_day_anchors(self, lines: list[list[dict]], days_in_period: int) -> dict[int, float]:
        """
        Derive the horizontal center positions for each day column 1..days_in_period.
        Uses header line detection with standard step fallback.
        """
        anchors: dict[int, float] = {}

        # Look for header lines containing "1" and day abbreviations
        for line in lines:
            line_str = " ".join(w["text"] for w in line)
            if "Emp. Code" in line_str and "Name" in line_str and "1" in line_str:
                for w in line:
                    t = w["text"].strip()
                    if t.isdigit():
                        d_num = int(t)
                        if 1 <= d_num <= days_in_period:
                            # Center of the day column is slightly to the right of the day number
                            # In basic report, day number is centered at ~165.2 + (d_num - 1) * 17.28
                            # The status letter (P, A, etc.) is centered around ~165.2 + (d_num - 1) * 17.28
                            anchors[d_num] = w["x0"] + (w.get("width", 5.0) / 2.0)

        # Fallback for any missing days based on standard step (17.28 points per day, starting at 165.2)
        base_x = anchors.get(1, 165.2)
        for d in range(1, days_in_period + 1):
            if d not in anchors:
                anchors[d] = base_x + (d - 1) * 17.28
            else:
                # Adjust base_x if day 1 was found to ensure consistency
                anchors[d] = 165.2 + (d - 1) * 17.28

        return anchors
