"""
SPT Hospital HRMS — Monthly Status Report (Detailed Work Duration) Parser

Parses the eSSL "Monthly Status Report (Detailed Work Duration)" PDF format.
Layout: A4 landscape, one employee per page (66 pages total), 25 day-columns,
8 metric rows (Status, InTime, OutTime, Duration, Late By, Early By, OT, Shift).

Algorithm:
1. Extract words per page using pdfplumber(x_tolerance=1.5, y_tolerance=2).
2. Cluster words into visual lines by y-coordinate tolerance (2.5px).
3. Derive 25 day-column anchors per page using the "Days" header line.
4. Header fields: Department, Employee code & name.
5. Aggregate block regex extraction against text with newlines collapsed to spaces.
6. Metric rows matching by label prefix ("Status", "InTime", "OutTime", "Duration", "OT", "Shift", "Late By", "Early By").
7. Map metric values to day-column anchors by x0 proximity.
8. Calculate qualifying lateness (>15m) and LOP days: lop_days = floor(qualifying_late_days / 3).
"""
import logging
import math
import re
from datetime import date, datetime, timedelta
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

# Regex patterns for aggregate fields
RE_AGG_TOTAL_WORK = re.compile(r"Total\s+Work\s+Duration:\s*([\d:]+)", re.IGNORECASE)
RE_AGG_TOTAL_OT = re.compile(r"Total\s+OT:\s*([\d:]+)", re.IGNORECASE)
RE_AGG_PRESENT = re.compile(r"Present:\s*(\d+)", re.IGNORECASE)
RE_AGG_ABSENT = re.compile(r"Absent:\s*(\d+)", re.IGNORECASE)
RE_AGG_WEEKLY_OFF = re.compile(r"WeeklyOff:\s*(\d+)", re.IGNORECASE)
RE_AGG_HOLIDAYS = re.compile(r"Holidays:\s*(\d+)", re.IGNORECASE)
RE_AGG_LEAVES = re.compile(r"Leaves\s+Taken:\s*(\d+)", re.IGNORECASE)
RE_AGG_LATE_HRS = re.compile(r"Late\s+By\s+Hrs:\s*([\d:]+)", re.IGNORECASE)
RE_AGG_LATE_DAYS = re.compile(r"Late\s+By\s+Days:\s*(\d+)", re.IGNORECASE)
RE_AGG_EARLY_HRS = re.compile(r"Early\s+By\s+Hrs:\s*([\d:]+)", re.IGNORECASE)
RE_AGG_EARLY_DAYS = re.compile(r"Early\s+going\s+By\s+Days:\s*(\d+)", re.IGNORECASE)
RE_AGG_TOTAL_DUR_OT = re.compile(r"Total\s+Duration\(\+OT\):\s*([\d:]+)", re.IGNORECASE)
RE_AGG_AVG_WORK = re.compile(r"Average\s+Working\s+Hrs:\s*([\d:]+)", re.IGNORECASE)

RE_DATE_RANGE = re.compile(
    r"(\w{3})\s+(\d{1,2})\s+(\d{4})\s+To\s+(\w{3})\s+(\d{1,2})\s+(\d{4})", re.IGNORECASE
)


def _parse_date_str(month_str: str, day_str: str, year_str: str) -> Optional[date]:
    for fmt in ["%b %d %Y", "%B %d %Y"]:
        try:
            return datetime.strptime(f"{month_str} {day_str} {year_str}", fmt).date()
        except ValueError:
            continue
    return None


def _classify_status(raw_status: str) -> ParsedStatus:
    if not raw_status:
        return ParsedStatus.NO_DATA
    s = raw_status.strip().upper()
    if s == "P":
        return ParsedStatus.PRESENT
    elif s == "A":
        return ParsedStatus.ABSENT
    else:
        return ParsedStatus.UNKNOWN


class MonthlyStatusReportParser:
    """Parser for eSSL 'Monthly Status Report (Detailed Work Duration)' PDF."""

    def __init__(self, pdf_path: str, grace_minutes: int = 5):
        self.pdf_path = pdf_path
        self.grace_minutes = grace_minutes

    def parse(self) -> ParsedReport:
        report = ParsedReport(
            report_type="Monthly Status Report (Detailed Work Duration)",
        )

        with pdfplumber.open(self.pdf_path) as pdf:
            report.total_pages = len(pdf.pages)

            page1_text = pdf.pages[0].extract_text(x_tolerance=3, y_tolerance=3) or ""
            self._extract_header_info(report, page1_text, pdf.pages)
            date_list = self._build_date_list(report)

            for page_idx, page in enumerate(pdf.pages):
                try:
                    self._process_page(page, page_idx, report, date_list)
                except Exception as e:
                    logger.error(f"Error parsing page {page_idx + 1}: {e}")
                    report.parse_warnings.append(f"Page {page_idx + 1} parse error: {str(e)}")

        return report

    def _extract_header_info(self, report: ParsedReport, text: str, pages: list):
        m = RE_DATE_RANGE.search(text)
        if m:
            report.date_range_start = _parse_date_str(m.group(1), m.group(2), m.group(3))
            report.date_range_end = _parse_date_str(m.group(4), m.group(5), m.group(6))

        report.printed_on = self._extract_printed_on(text)
        if not report.printed_on and pages:
            for p in pages:
                p_text = p.extract_text() or ""
                po = self._extract_printed_on(p_text)
                if po:
                    report.printed_on = po
                    break

        company_counts = {}
        for p in pages:
            p_text = p.extract_text() or ""
            co = self._extract_company(p_text)
            if co:
                company_counts[co] = company_counts.get(co, 0) + 1

        if company_counts:
            summary_parts = [f"{co} ({cnt} pages)" for co, cnt in sorted(company_counts.items())]
            report.company_name = ", ".join(summary_parts)
        else:
            report.company_name = "SPT"

    def _build_date_list(self, report: ParsedReport) -> list[date]:
        if not report.date_range_start or not report.date_range_end:
            return []
        dates = []
        current = report.date_range_start
        while current <= report.date_range_end:
            dates.append(current)
            current += timedelta(days=1)
        return dates

    def _process_page(self, page, page_idx: int, report: ParsedReport, date_list: list[date]):
        words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
        if not words:
            return

        full_text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
        full_text_single_line = full_text.replace("\n", " ")
        page_company = self._extract_company(full_text) or report.company_name or "SPT"
        department_name = self._extract_department(full_text_single_line)
        employee_code, employee_name = self._extract_employee(full_text_single_line)

        if not employee_code:
            report.parse_warnings.append(f"Page {page_idx + 1}: missing employee code")
            return

        # Cluster words into visual lines by top coordinate (tolerance 2.5px)
        lines = []
        for w in sorted(words, key=lambda x: (x["top"], x["x0"])):
            matched = False
            for line in lines:
                if abs(line[0]["top"] - w["top"]) < 2.5:
                    line.append(w)
                    matched = True
                    break
            if not matched:
                lines.append([w])

        # Extract 25 day column anchors from Days header line
        anchors = self._extract_day_anchors(lines)

        # Extract metric row maps: metric_name -> {day_num: value_str}
        grid_rows = self._extract_grid_rows(lines, anchors)

        # Calculate lateness metrics
        late_map = grid_rows.get("late_by", {})
        late_days_device = 0
        late_days_qualifying = 0

        for day_num, late_str in late_map.items():
            if late_str and late_str != "00:00":
                late_days_device += 1
                try:
                    parts = late_str.split(":")
                    mins = int(parts[0]) * 60 + int(parts[1])
                    if mins > self.grace_minutes:
                        late_days_qualifying += 1
                except Exception:
                    pass

        lop_days = math.floor(late_days_qualifying / 3)

        # Check for zero punches all month (no InTime and no OutTime for all days)
        in_map = grid_rows.get("in_time", {})
        out_map = grid_rows.get("out_time", {})
        has_any_punch = any(v for v in in_map.values()) or any(v for v in out_map.values())
        has_zero_punches = not has_any_punch

        # Build aggregate object
        agg = self._extract_aggregates(
            full_text_single_line,
            employee_code,
            employee_name,
            department_name,
            company_name=page_company,
            late_days_device=late_days_device,
            late_days_qualifying=late_days_qualifying,
            lop_days=lop_days,
            has_zero_punches=has_zero_punches,
        )
        report.monthly_aggregates.append(agg)

        # Build daily attendance records
        num_days = len(date_list)
        for day_idx in range(num_days):
            day_num = day_idx + 1
            att_date = date_list[day_idx]

            status_raw = grid_rows.get("status", {}).get(day_num, "")
            in_time = grid_rows.get("in_time", {}).get(day_num, "")
            out_time = grid_rows.get("out_time", {}).get(day_num, "")
            duration = grid_rows.get("duration", {}).get(day_num, "")
            late_by = grid_rows.get("late_by", {}).get(day_num, "")
            ot = grid_rows.get("ot", {}).get(day_num, "")
            shift = grid_rows.get("shift", {}).get(day_num, "")

            status = _classify_status(status_raw)

            warnings = []
            is_partial = False
            dur_mins = self._parse_duration_mins(duration)

            if status == ParsedStatus.PRESENT and in_time and not out_time:
                # Check if this falls on the last day of import and report was printed during that day
                if (
                    report.printed_on
                    and report.date_range_end
                    and att_date == report.date_range_end == report.printed_on.date()
                ):
                    is_partial = True
                    warnings.append(ParseWarning.PARTIAL_DAY)
                else:
                    warnings.append(ParseWarning.NO_OUT_PUNCH)
                    status = ParsedStatus.PRESENT_INCOMPLETE

            # Zero-duration punch detection (e.g. In 08:43 -> Out 08:43)
            if in_time and out_time and in_time == out_time and status == ParsedStatus.PRESENT:
                status = ParsedStatus.PRESENT_INCOMPLETE
                warnings.append(ParseWarning.SUSPECT_PUNCH)
            elif in_time and out_time and dur_mins == 0 and status == ParsedStatus.PRESENT:
                status = ParsedStatus.PRESENT_INCOMPLETE
                warnings.append(ParseWarning.SUSPECT_PUNCH)

            # Post-midnight punch anomaly detection (in-punch 00:00-03:00 and duration > 14h / 840 mins)
            if in_time and ":" in in_time:
                try:
                    ih = int(in_time.split(":")[0])
                    if 0 <= ih < 3 and dur_mins and dur_mins > 840:
                        warnings.append(ParseWarning.SUSPECT_PUNCH)
                except Exception:
                    pass

            record = ParsedAttendanceRecord(
                attendance_date=att_date,
                department_name=department_name,
                row_number=page_idx * num_days + day_idx + 1,
                raw_employee_code=employee_code,
                raw_employee_name=employee_name,
                raw_shift=shift or None,
                raw_in_time=in_time or None,
                raw_out_time=out_time or None,
                raw_work_duration=duration or None,
                raw_ot=ot or None,
                raw_status=status_raw or None,
                employee_code=employee_code,
                employee_name=employee_name,
                shift_code=shift or None,
                status=status,
                in_time_str=in_time or None,
                out_time_str=out_time or None,
                work_minutes=dur_mins,
                ot_minutes=self._parse_duration_mins(ot),
                is_partial=is_partial,
                warnings=warnings,
            )

            self._add_to_report(report, record, att_date, department_name)

    def _extract_printed_on(self, text: str) -> Optional[datetime]:
        m = re.search(r"Printed\s+On\s*:\s*([A-Za-z]{3}\s+\d{1,2}\s+\d{4}\s+\d{1,2}:\d{2})", text, re.IGNORECASE)
        if m:
            try:
                return datetime.strptime(m.group(1).strip(), "%b %d %Y %H:%M")
            except Exception:
                pass
        m2 = re.search(r"Printed\s+On\s*:\s*(\d{1,2}[/-]\d{1,2}[/-]\d{4}\s+\d{1,2}:\d{2})", text, re.IGNORECASE)
        if m2:
            try:
                return datetime.strptime(m2.group(1).strip().replace("-", "/"), "%d/%m/%Y %H:%M")
            except Exception:
                pass
        return None

    def _extract_company(self, text: str) -> Optional[str]:
        for line in text.split("\n"):
            if "Company:" in line:
                parts = re.split(r"\s+Printed\s+On\s*:", line, flags=re.IGNORECASE)
                company_raw = parts[0].replace("Company:", "").strip()
                if company_raw:
                    return company_raw
        m = re.search(r"Company:\s*(.+?)(?:\s+Printed\s+On|\s+$)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    def _extract_department(self, text: str) -> str:
        m = re.search(r"Department:\s*(.+?)(?:\s+Employee:|\s+$)", text, re.IGNORECASE)
        if m:
            dept = m.group(1).strip()
            # Normalize 'Dt HR' -> 'HR' and 'Dr'/'DR' -> 'DOCTOR'
            if dept == "Dt HR":
                return "HR"
            if dept.upper() in ["DR", "DR."]:
                return "DOCTOR"
            return dept
        return "Default"

    def _extract_employee(self, text: str) -> tuple[str, str]:
        m = re.search(r"Employee:\s*(\d+)\s*:\s*(.+?)\s+Total Work Duration", text, re.IGNORECASE)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        return "", ""

    def _extract_day_anchors(self, lines: list[list[dict]]) -> list[tuple[int, float]]:
        days_line = None
        for line in lines:
            if any(w["text"] == "Days" for w in line):
                days_line = line
                break

        if not days_line:
            return []

        anchors = []
        seen = set()
        for w in days_line:
            m = re.match(r"^(\d{1,2})$", w["text"].strip())
            if m:
                d_num = int(m.group(1))
                if 1 <= d_num <= 31 and d_num not in seen:
                    seen.add(d_num)
                    anchors.append((d_num, w["x0"]))
        anchors.sort(key=lambda x: x[0])
        return anchors

    def _extract_grid_rows(
        self, lines: list[list[dict]], anchors: list[tuple[int, float]]
    ) -> dict[str, dict[int, str]]:
        if not anchors:
            return {}

        grid_rows: dict[str, dict[int, str]] = {}

        for line in lines:
            if not line:
                continue
            txts = [w["text"].strip() for w in line]
            line_str = " ".join(txts)

            # Skip page title/header lines
            if "Monthly" in txts or "Report" in txts or "Printed" in txts:
                continue

            metric_key = None
            if "Status" in txts:
                metric_key = "status"
            elif "InTime" in txts:
                metric_key = "in_time"
            elif "OutTime" in txts:
                metric_key = "out_time"
            elif "Duration" in txts and "Total" not in txts:
                metric_key = "duration"
            elif "OT" in txts and "Total" not in txts:
                metric_key = "ot"
            elif "Shift" in txts:
                metric_key = "shift"
            elif "Late" in txts and "By" in txts and "Hrs:" not in txts and "Days:" not in txts:
                metric_key = "late_by"
            elif "Early" in txts and "By" in txts and "Hrs:" not in txts and "Days:" not in txts:
                metric_key = "early_by"

            if metric_key and metric_key not in grid_rows:
                val_words = [w for w in line if w["x0"] >= 35]
                row_map = {}
                for w in val_words:
                    txt = w["text"].strip()
                    if txt in ["Status", "InTime", "OutTime", "Duration", "Late", "By", "Early", "OT", "Shift", "Hrs", "Hrs.", "Hrs:", "Days:", "going"]:
                        continue

                    # Find nearest anchor by x0
                    best_d = min(anchors, key=lambda a: abs(a[1] - w["x0"]))[0]
                    row_map[best_d] = txt

                grid_rows[metric_key] = row_map

        return grid_rows

    def _extract_aggregates(
        self,
        text: str,
        employee_code: str,
        employee_name: str,
        department_name: str,
        company_name: Optional[str],
        late_days_device: int,
        late_days_qualifying: int,
        lop_days: int,
        has_zero_punches: bool,
    ) -> MonthlyEmployeeAggregate:
        def _search_int(pattern, default=0):
            m = pattern.search(text)
            return int(m.group(1)) if m else default

        def _search_str(pattern):
            m = pattern.search(text)
            return m.group(1) if m else None

        agg = MonthlyEmployeeAggregate(
            employee_code=employee_code,
            employee_name=employee_name,
            department_name=department_name,
            company_name=company_name,
            total_work_duration=_search_str(RE_AGG_TOTAL_WORK),
            total_ot=_search_str(RE_AGG_TOTAL_OT),
            present_count=_search_int(RE_AGG_PRESENT),
            absent_count=_search_int(RE_AGG_ABSENT),
            weekly_off_count=_search_int(RE_AGG_WEEKLY_OFF),
            holidays_count=_search_int(RE_AGG_HOLIDAYS),
            leaves_taken=_search_int(RE_AGG_LEAVES),
            late_by_hrs=_search_str(RE_AGG_LATE_HRS),
            late_by_days=_search_int(RE_AGG_LATE_DAYS),
            late_days_device=late_days_device,
            late_days_qualifying=late_days_qualifying,
            lop_days=lop_days,
            early_by_hrs=_search_str(RE_AGG_EARLY_HRS),
            early_going_by_days=_search_int(RE_AGG_EARLY_DAYS),
            total_duration_with_ot=_search_str(RE_AGG_TOTAL_DUR_OT),
            average_working_hrs=_search_str(RE_AGG_AVG_WORK),
            has_zero_punches=has_zero_punches,
        )
        return agg

    def _parse_duration_mins(self, duration_str: Optional[str]) -> Optional[int]:
        if not duration_str:
            return None
        duration_str = duration_str.strip()
        if not duration_str or duration_str == "00:00":
            return 0
        try:
            parts = duration_str.split(":")
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            pass
        return None

    def _add_to_report(
        self,
        report: ParsedReport,
        record: ParsedAttendanceRecord,
        att_date: date,
        department_name: str,
    ):
        date_block = None
        for db in report.date_blocks:
            if db.attendance_date == att_date:
                date_block = db
                break
        if date_block is None:
            date_block = ParsedDateBlock(attendance_date=att_date)
            report.date_blocks.append(date_block)

        dept_block = None
        for d in date_block.departments:
            if d.name == department_name:
                dept_block = d
                break
        if dept_block is None:
            dept_block = ParsedDepartment(name=department_name)
            date_block.departments.append(dept_block)

        dept_block.records.append(record)
