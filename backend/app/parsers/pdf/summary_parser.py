"""
SPT Hospital HRMS — Monthly Status Report (Summary Report) Parser

Parses the eSSL "Monthly Status Report (Summary Report)" PDF format.
Layout: A4 portrait/landscape table with 18 columns per employee,
grouped by "Department: <DeptName>".

Extracts:
- Report metadata (Company, Date Range: start/end dates, Printed On)
- Department groupings (normalized, e.g. "Dt HR" -> "HR")
- Table metrics per employee:
  - Emp. Code, EmployeeName
  - P (Present), A (Absent), H, HP, WO, WOP, CL, PL, SL, Other Leave, Total Leave
  - Total Present, Total Pay Days, Total OT in Hrs, Total Late By, Total Early By
- Generates MonthlyEmployeeAggregate objects for all employees
- Generates ParsedAttendanceRecord summary records for preview/commit pipelines
"""
import logging
import math
import re
from datetime import date, datetime
from typing import Optional

import pdfplumber

from app.parsers.pdf.models import (
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
RE_DEPT = re.compile(r"Department:\s*([^\n\r]+)", re.IGNORECASE)


def _safe_int(val: Optional[str], default: int = 0) -> int:
    if val is None:
        return default
    s = str(val).strip()
    try:
        return int(s)
    except ValueError:
        return default


def _clean_str(val: Optional[str]) -> str:
    if val is None:
        return ""
    return " ".join(str(val).split())


def _normalize_dept(dept_name: str) -> str:
    dept = dept_name.strip()
    if dept.upper() in ("DT HR", "DTHR"):
        return "HR"
    return dept


class MonthlySummaryReportParser:
    """Parser for eSSL Monthly Status Report (Summary Report) PDFs."""

    def __init__(self, pdf_path: str, grace_minutes: int = 5):
        self.pdf_path = pdf_path
        self.grace_minutes = grace_minutes

    def parse(self) -> ParsedReport:
        report = ParsedReport(
            report_type="Monthly Status Report (Summary Report)",
            company_name="SPT",
        )

        aggregates: list[MonthlyEmployeeAggregate] = []
        summary_records: list[ParsedAttendanceRecord] = []
        departments_dict: dict[str, ParsedDepartment] = {}

        date_start: Optional[date] = None
        date_end: Optional[date] = None
        printed_on: Optional[datetime] = None

        with pdfplumber.open(self.pdf_path) as pdf:
            report.total_pages = len(pdf.pages)

            for page_idx, page in enumerate(pdf.pages):
                text = page.extract_text() or ""

                # Extract date range from first available page
                if not date_start:
                    m_range = RE_DATE_RANGE.search(text)
                    if m_range:
                        try:
                            date_start = datetime.strptime(m_range.group(1), "%b %d %Y").date()
                            date_end = datetime.strptime(m_range.group(2), "%b %d %Y").date()
                        except ValueError:
                            pass

                # Extract Printed On
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

                # Extract page-level company
                m_comp = RE_COMPANY.search(text)
                page_company = m_comp.group(1).strip() if m_comp else "SPT"

                # Extract departments on this page
                raw_depts = RE_DEPT.findall(text)
                page_depts = [_normalize_dept(d) for d in raw_depts]

                # Extract tables on this page
                tables = page.extract_tables()

                # Process tables
                for t_idx, table in enumerate(tables):
                    dept_name = page_depts[t_idx] if t_idx < len(page_depts) else (page_depts[-1] if page_depts else "Default")

                    if dept_name not in departments_dict:
                        departments_dict[dept_name] = ParsedDepartment(name=dept_name)

                    # Iterate rows (skip header row with 'Emp. Code')
                    for row in table:
                        if not row or not row[0]:
                            continue
                        code_str = str(row[0]).strip()
                        if code_str.lower() in ("emp. code", "emp code", "code"):
                            continue

                        emp_name = _clean_str(row[1]) if len(row) > 1 else ""
                        p_count = _safe_int(row[2]) if len(row) > 2 else 0
                        a_count = _safe_int(row[3]) if len(row) > 3 else 0
                        h_count = _safe_int(row[4]) if len(row) > 4 else 0
                        hp_count = _safe_int(row[5]) if len(row) > 5 else 0
                        wo_count = _safe_int(row[6]) if len(row) > 6 else 0
                        wop_count = _safe_int(row[7]) if len(row) > 7 else 0
                        total_leave = _safe_int(row[12]) if len(row) > 12 else 0
                        total_present = _safe_int(row[13]) if len(row) > 13 else p_count
                        total_pay_days = _safe_int(row[14]) if len(row) > 14 else p_count
                        total_ot_raw = str(row[15]).strip() if len(row) > 15 and row[15] else "00:00"
                        total_late_by = _safe_int(row[16]) if len(row) > 16 else 0
                        total_early_by = _safe_int(row[17]) if len(row) > 17 else 0

                        has_zero_punches = (p_count == 0)

                        # Zero-punch staff (or inactive codes) do not get LOP
                        if has_zero_punches or code_str in ("208", "209", "210"):
                            lop_days = 0
                            qualifying_late = 0
                        else:
                            qualifying_late = total_late_by
                            lop_days = qualifying_late // 3

                        # Build aggregate
                        agg = MonthlyEmployeeAggregate(
                            employee_code=code_str,
                            employee_name=emp_name,
                            department_name=dept_name,
                            company_name=page_company,
                            total_work_duration=None,
                            total_ot=total_ot_raw if total_ot_raw != "00:00" else None,
                            present_count=p_count,
                            absent_count=a_count,
                            weekly_off_count=wo_count,
                            holidays_count=h_count,
                            leaves_taken=total_leave,
                            late_by_hrs=None,
                            late_by_days=total_late_by,
                            late_days_device=total_late_by,
                            late_days_qualifying=qualifying_late,
                            lop_days=lop_days,
                            early_by_hrs=None,
                            early_going_by_days=total_early_by,
                            has_zero_punches=has_zero_punches,
                        )
                        aggregates.append(agg)

                        # Build summary attendance record so existing preview displays all staff
                        rec_date = date_end or date.today()
                        status = ParsedStatus.PRESENT if p_count > 0 else ParsedStatus.ABSENT
                        record = ParsedAttendanceRecord(
                            attendance_date=rec_date,
                            department_name=dept_name,
                            row_number=len(summary_records) + 1,
                            raw_employee_code=code_str,
                            raw_employee_name=emp_name,
                            raw_status="PRESENT" if p_count > 0 else "ABSENT",
                            raw_work_duration=f"Present: {p_count}d, Absent: {a_count}d, Pay: {total_pay_days}d",
                            raw_ot=total_ot_raw if total_ot_raw != "00:00" else None,
                            raw_total_duration=f"Late: {total_late_by}d, Early: {total_early_by}d",
                            employee_code=code_str,
                            employee_name=emp_name,
                            status=status,
                        )
                        departments_dict[dept_name].records.append(record)
                        summary_records.append(record)

        report.date_range_start = date_start
        report.date_range_end = date_end
        report.printed_on = printed_on
        report.monthly_aggregates = aggregates

        if date_end:
            date_block = ParsedDateBlock(
                attendance_date=date_end,
                departments=list(departments_dict.values()),
            )
            report.date_blocks.append(date_block)

        logger.info(
            f"MonthlySummaryReportParser extracted {len(aggregates)} employee aggregates "
            f"across {len(departments_dict)} departments (Date range: {date_start} -> {date_end})"
        )
        return report
