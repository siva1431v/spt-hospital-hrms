"""
SPT Hospital HRMS — Attendance Models
Stores parsed attendance records with full audit trail.
Preserves original PDF values separately from corrections.
"""
import enum
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint, Index, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"
    PRESENT_INCOMPLETE = "PRESENT_INCOMPLETE"   # No OutPunch
    PRESENT_OVERNIGHT = "PRESENT_OVERNIGHT"     # Overnight shift crossing midnight
    HALF_DAY = "HALF_DAY"
    LEAVE = "LEAVE"
    HOLIDAY = "HOLIDAY"
    WEEKLY_OFF = "WEEKLY_OFF"
    NO_DATA = "NO_DATA"


class ImportStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    SKIPPED = "SKIPPED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExceptionSeverity(str, enum.Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ExceptionReviewStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    CORRECTED = "CORRECTED"
    DISMISSED = "DISMISSED"


# ─────────────────────────────────────────────────────────────
# Attendance Import Session
# ─────────────────────────────────────────────────────────────
class AttendanceImport(Base):
    __tablename__ = "attendance_imports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # SHA-256

    # Detected from PDF
    report_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    date_range_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Import summary
    total_records_in_pdf: Mapped[int] = mapped_column(Integer, default=0)
    records_imported: Mapped[int] = mapped_column(Integer, default=0)
    records_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    records_error: Mapped[int] = mapped_column(Integer, default=0)
    records_warning: Mapped[int] = mapped_column(Integer, default=0)
    unknown_employees: Mapped[int] = mapped_column(Integer, default=0)
    unknown_departments: Mapped[int] = mapped_column(Integer, default=0)
    unknown_employee_codes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unknown_department_names: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unmatched_row_count: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[ImportStatus] = mapped_column(
        Enum(ImportStatus), default=ImportStatus.PROCESSING, nullable=False
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    uploaded_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    uploaded_by: Mapped["User"] = relationship("User")  # type: ignore[name-defined]
    records: Mapped[list["AttendanceImportRecord"]] = relationship(
        "AttendanceImportRecord", back_populates="import_session"
    )
    attendance_records: Mapped[list["Attendance"]] = relationship(
        "Attendance", back_populates="import_session"
    )


# ─────────────────────────────────────────────────────────────
# Raw Import Record — preserves every field from the PDF
# ─────────────────────────────────────────────────────────────
class AttendanceImportRecord(Base):
    __tablename__ = "attendance_import_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    import_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("attendance_imports.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Exactly as found in the PDF
    raw_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    raw_department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raw_employee_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    raw_employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raw_shift: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    raw_in_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_out_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_work_duration: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_ot: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_total_duration: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_status: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    raw_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Mapping result
    mapped_employee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
    mapped_department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    has_error: Mapped[bool] = mapped_column(Boolean, default=False)
    has_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    warning_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Link to created attendance record (if import succeeded)
    attendance_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("attendance.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    import_session: Mapped["AttendanceImport"] = relationship(
        "AttendanceImport", back_populates="records"
    )


# ─────────────────────────────────────────────────────────────
# Attendance Record — canonical attendance per employee per day
# ─────────────────────────────────────────────────────────────
class Attendance(Base):
    __tablename__ = "attendance"

    __table_args__ = (
        UniqueConstraint("employee_id", "attendance_date", name="uq_attendance_employee_date"),
        Index("ix_attendance_date", "attendance_date"),
        Index("ix_attendance_employee_date", "employee_id", "attendance_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ── SOURCE (original from PDF — never modified) ─────────────────────────
    source_import_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("attendance_imports.id", ondelete="SET NULL"), nullable=True
    )
    source_department_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_shift_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_in_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_out_time: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_work_duration: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_ot: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_total_duration: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source_status: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── EFFECTIVE VALUES (may be corrected by HR) ──────────────────────────
    # Stored as full datetime to correctly handle overnight shifts
    check_in_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Duration in minutes (calculated or corrected)
    work_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ot_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    total_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus), nullable=False, default=AttendanceStatus.PRESENT
    )

    # Assigned department and shift (from employee profile or corrected)
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    shift_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True
    )

    # Flags
    is_late: Mapped[bool] = mapped_column(Boolean, default=False)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0)
    is_corrected: Mapped[bool] = mapped_column(Boolean, default=False)
    has_exception: Mapped[bool] = mapped_column(Boolean, default=False)

    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="attendance_records")  # type: ignore[name-defined]
    import_session: Mapped[Optional["AttendanceImport"]] = relationship(
        "AttendanceImport", back_populates="attendance_records"
    )
    department: Mapped[Optional["Department"]] = relationship("Department")  # type: ignore[name-defined]
    shift: Mapped[Optional["Shift"]] = relationship("Shift")  # type: ignore[name-defined]
    corrections: Mapped[list["AttendanceCorrection"]] = relationship(
        "AttendanceCorrection", back_populates="attendance"
    )
    exceptions: Mapped[list["AttendanceException"]] = relationship(
        "AttendanceException", back_populates="attendance"
    )

    def __repr__(self) -> str:
        return f"<Attendance {self.employee_id} on {self.attendance_date}: {self.status}>"


# ─────────────────────────────────────────────────────────────
# Attendance Correction — audit trail for HR corrections
# ─────────────────────────────────────────────────────────────
class AttendanceCorrection(Base):
    __tablename__ = "attendance_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    attendance_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("attendance.id", ondelete="CASCADE"), nullable=False
    )
    corrected_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )

    # What was before
    original_check_in: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    original_check_out: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    original_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # What was set
    corrected_check_in: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    corrected_check_out: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    corrected_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    reason: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    attendance: Mapped["Attendance"] = relationship("Attendance", back_populates="corrections")
    corrected_by: Mapped["User"] = relationship("User")  # type: ignore[name-defined]


# ─────────────────────────────────────────────────────────────
# Attendance Exception — flagged suspicious records
# ─────────────────────────────────────────────────────────────
class AttendanceException(Base):
    __tablename__ = "attendance_exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    attendance_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("attendance.id", ondelete="CASCADE"), nullable=True
    )
    import_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("attendance_imports.id", ondelete="CASCADE"), nullable=True
    )

    employee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=True
    )
    exception_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    exception_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "SUSPICIOUS_DURATION"
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    original_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    severity: Mapped[ExceptionSeverity] = mapped_column(
        Enum(ExceptionSeverity), default=ExceptionSeverity.WARNING
    )
    review_status: Mapped[ExceptionReviewStatus] = mapped_column(
        Enum(ExceptionReviewStatus), default=ExceptionReviewStatus.PENDING
    )
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    attendance: Mapped[Optional["Attendance"]] = relationship(
        "Attendance", back_populates="exceptions"
    )
    employee: Mapped[Optional["Employee"]] = relationship("Employee")  # type: ignore[name-defined]
    reviewed_by: Mapped[Optional["User"]] = relationship("User")  # type: ignore[name-defined]


class MonthlyAttendanceAggregate(Base):
    """Pre-computed monthly attendance aggregates from eSSL Monthly Status Report.
    These values are imported directly from the source system, not re-derived."""
    __tablename__ = "monthly_attendance_aggregates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("attendance_imports.id", ondelete="CASCADE"), nullable=True)
    employee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=True, index=True)
    employee: Mapped[Optional["Employee"]] = relationship("Employee")  # type: ignore[name-defined]
    employee_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    employee_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Pre-computed by eSSL source system
    total_work_duration: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    total_ot: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    present_count: Mapped[int] = mapped_column(Integer, default=0)
    absent_count: Mapped[int] = mapped_column(Integer, default=0)
    weekly_off_count: Mapped[int] = mapped_column(Integer, default=0)
    holidays_count: Mapped[int] = mapped_column(Integer, default=0)
    leaves_taken: Mapped[int] = mapped_column(Integer, default=0)
    late_by_hrs: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    late_by_days: Mapped[int] = mapped_column(Integer, default=0)
    late_days_device: Mapped[int] = mapped_column(Integer, default=0)
    late_days_qualifying: Mapped[int] = mapped_column(Integer, default=0)
    lop_days: Mapped[int] = mapped_column(Integer, default=0)
    early_by_hrs: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    early_going_by_days: Mapped[int] = mapped_column(Integer, default=0)
    total_duration_with_ot: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    average_working_hrs: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    has_zero_punches: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("employee_id", "year", "month", name="uq_monthly_agg_emp_period"),
    )
