"""
SPT Hospital HRMS — Employee Model
Complete employee profile with biometric code linkage.
"""
import enum
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import (
    Boolean, Date, DateTime, Enum, ForeignKey, Integer,
    Numeric, String, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class EmploymentType(str, enum.Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    PROBATION = "PROBATION"
    INTERN = "INTERN"


class Gender(str, enum.Enum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Internal unique ID (e.g., EMP-0001)
    employee_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    # ── CRITICAL: Biometric/eSSL Code ──────────────────────────────────────
    # This is the E. Code from the eSSL PDF. Used to map PDF records to employees.
    # Stored as string because some codes may have leading zeros or prefixes.
    biometric_code: Mapped[Optional[str]] = mapped_column(
        String(50), unique=True, nullable=True, index=True
    )

    # Personal Information
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, default="")
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gender: Mapped[Optional[Gender]] = mapped_column(Enum(Gender), nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Employment
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    designation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("designations.id", ondelete="SET NULL"), nullable=True
    )
    shift_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True
    )
    joining_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType), default=EmploymentType.FULL_TIME, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Salary (base values — actual structure is in salary_structures)
    basic_salary: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    salary_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")
    salary_source: Mapped[Optional[str]] = mapped_column(String(20), default="MIGRATED", nullable=True)
    security_fund_deduction: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), default=500.0, nullable=True)

    # Bank & Tax Details
    bank_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bank_account_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bank_ifsc: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pan_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    pf_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    esi_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    department: Mapped[Optional["Department"]] = relationship(  # type: ignore[name-defined]
        "Department", back_populates="employees", foreign_keys=[department_id]
    )
    designation: Mapped[Optional["Designation"]] = relationship(  # type: ignore[name-defined]
        "Designation", back_populates="employees"
    )
    shift: Mapped[Optional["Shift"]] = relationship(  # type: ignore[name-defined]
        "Shift", back_populates="employees"
    )
    user: Mapped[Optional["User"]] = relationship(  # type: ignore[name-defined]
        "User", back_populates="employee", foreign_keys="User.employee_id"
    )
    attendance_records: Mapped[list["Attendance"]] = relationship(  # type: ignore[name-defined]
        "Attendance", back_populates="employee"
    )
    leave_requests: Mapped[list["LeaveRequest"]] = relationship(  # type: ignore[name-defined]
        "LeaveRequest", back_populates="employee"
    )
    salary_structure: Mapped[Optional["SalaryStructure"]] = relationship(  # type: ignore[name-defined]
        "SalaryStructure", back_populates="employee", uselist=False
    )
    payroll_records: Mapped[list["PayrollRecord"]] = relationship(  # type: ignore[name-defined]
        "PayrollRecord", back_populates="employee"
    )

    def __repr__(self) -> str:
        return f"<Employee {self.employee_id}: {self.full_name}>"


class SecurityFundTransaction(Base):
    __tablename__ = "security_fund_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "ADDITION" | "WITHDRAWAL" | "DEDUCTION" | "REFUND"
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    employee: Mapped["Employee"] = relationship("Employee")
