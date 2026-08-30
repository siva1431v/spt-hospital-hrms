"""
SPT Hospital HRMS — PDF Parser Data Models
Structured dataclasses representing parsed attendance data.
These are intermediate objects used during PDF parsing before DB persistence.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional
from enum import Enum


class ParsedStatus(str, Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    PRESENT_INCOMPLETE = "PRESENT_INCOMPLETE"
    PRESENT_OVERNIGHT = "PRESENT_OVERNIGHT"
    NO_DATA = "NO_DATA"
    UNKNOWN = "UNKNOWN"


class ParseWarning(str, Enum):
    NO_OUT_PUNCH = "NO_OUT_PUNCH"
    SUSPICIOUS_DURATION = "SUSPICIOUS_DURATION"
    SUSPECT_PUNCH = "SUSPECT_PUNCH"
    PARTIAL_DAY = "PARTIAL_DAY"
    OVERNIGHT_SHIFT = "OVERNIGHT_SHIFT"
    ZERO_TIMES = "ZERO_TIMES"
    MISSING_EMPLOYEE_CODE = "MISSING_EMPLOYEE_CODE"


@dataclass
class ParsedAttendanceRecord:
    """Single attendance record extracted from the eSSL PDF."""
    # Context
    attendance_date: Optional[date] = None
    department_name: Optional[str] = None
    row_number: int = 0

    # Raw strings exactly as found in the PDF
    raw_sno: Optional[str] = None
    raw_employee_code: Optional[str] = None
    raw_employee_name: Optional[str] = None
    raw_shift: Optional[str] = None
    raw_in_time: Optional[str] = None
    raw_out_time: Optional[str] = None
    raw_work_duration: Optional[str] = None
    raw_ot: Optional[str] = None
    raw_total_duration: Optional[str] = None
    raw_status: Optional[str] = None
    raw_remarks: Optional[str] = None

    # Parsed values
    employee_code: Optional[str] = None
    employee_name: Optional[str] = None
    shift_code: Optional[str] = None
    status: ParsedStatus = ParsedStatus.UNKNOWN

    # Times parsed from strings
    in_time_str: Optional[str] = None
    out_time_str: Optional[str] = None
    work_minutes: Optional[int] = None
    ot_minutes: Optional[int] = None
    total_minutes: Optional[int] = None

    # Flags
    is_overnight: bool = False
    is_partial: bool = False
    warnings: list[ParseWarning] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)


@dataclass
class ParsedDepartment:
    """A department section within a date block."""
    name: str
    records: list[ParsedAttendanceRecord] = field(default_factory=list)


@dataclass
class ParsedDateBlock:
    """All attendance data for a single date."""
    attendance_date: date
    departments: list[ParsedDepartment] = field(default_factory=list)

    @property
    def all_records(self) -> list[ParsedAttendanceRecord]:
        records = []
        for dept in self.departments:
            records.extend(dept.records)
        return records


@dataclass
class MonthlyEmployeeAggregate:
    """Per-employee monthly aggregate stats from 'Monthly Status Report (Detailed Work Duration)'.
    These are pre-computed by the eSSL source system and stored as-is — not re-derived from daily cells."""
    employee_code: str = ""
    employee_name: str = ""
    department_name: str = ""
    company_name: Optional[str] = None
    total_work_duration: Optional[str] = None  # "23:28"
    total_ot: Optional[str] = None
    present_count: int = 0
    absent_count: int = 0
    weekly_off_count: int = 0
    holidays_count: int = 0
    leaves_taken: int = 0
    late_by_hrs: Optional[str] = None
    late_by_days: int = 0
    late_days_device: int = 0
    late_days_qualifying: int = 0
    lop_days: int = 0
    early_by_hrs: Optional[str] = None
    early_going_by_days: int = 0
    total_duration_with_ot: Optional[str] = None
    average_working_hrs: Optional[str] = None
    has_zero_punches: bool = False


@dataclass
class ParsedReport:
    """Complete parsed eSSL attendance PDF report."""
    report_type: Optional[str] = None
    company_name: Optional[str] = None
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    printed_on: Optional[datetime] = None
    date_blocks: list[ParsedDateBlock] = field(default_factory=list)
    parse_warnings: list[str] = field(default_factory=list)
    total_pages: int = 0
    monthly_aggregates: list[MonthlyEmployeeAggregate] = field(default_factory=list)

    @property
    def all_records(self) -> list[ParsedAttendanceRecord]:
        records = []
        for block in self.date_blocks:
            records.extend(block.all_records)
        return records

    @property
    def unique_departments(self) -> set[str]:
        departments = set()
        for block in self.date_blocks:
            for dept in block.departments:
                departments.add(dept.name)
        return departments

    @property
    def unique_employee_codes(self) -> set[str]:
        codes = set()
        for record in self.all_records:
            if record.employee_code:
                codes.add(record.employee_code)
        return codes

    def summary(self) -> dict:
        records = self.all_records
        return {
            "total_records": len(records),
            "unique_employees": len(self.unique_employee_codes),
            "unique_departments": len(self.unique_departments),
            "present": sum(1 for r in records if r.status == ParsedStatus.PRESENT),
            "absent": sum(1 for r in records if r.status == ParsedStatus.ABSENT),
            "incomplete": sum(1 for r in records if r.status == ParsedStatus.PRESENT_INCOMPLETE),
            "overnight": sum(1 for r in records if r.is_overnight),
            "with_warnings": sum(1 for r in records if r.warnings),
            "with_errors": sum(1 for r in records if r.parse_errors),
        }

