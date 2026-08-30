"""
SPT Hospital HRMS — Payroll Models
Salary structures, payroll periods, records, and salary slips.
"""
import enum
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy import (
    Boolean, Date, DateTime, Enum, Float, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ComponentType(str, enum.Enum):
    EARNING = "EARNING"
    DEDUCTION = "DEDUCTION"


class PayrollStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    NO_DATA = "NO_DATA"
    UNDER_REVIEW = "UNDER_REVIEW"
    FINALIZED = "FINALIZED"
    PAID = "PAID"


# ─────────────────────────────────────────────────────────────
# Salary Component Definition (global)
# ─────────────────────────────────────────────────────────────
class SalaryComponent(Base):
    __tablename__ = "salary_components"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    component_type: Mapped[ComponentType] = mapped_column(Enum(ComponentType), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_taxable: Mapped[bool] = mapped_column(Boolean, default=False)
    # If True: calculated as % of basic. If False: fixed amount
    is_percentage: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# ─────────────────────────────────────────────────────────────
# Salary Structure — per employee
# ─────────────────────────────────────────────────────────────
class SalaryStructure(Base):
    __tablename__ = "salary_structures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    basic_salary: Mapped[float] = mapped_column(Float, nullable=False)
    ot_rate_per_hour: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    employee: Mapped["Employee"] = relationship("Employee", back_populates="salary_structure")  # type: ignore[name-defined]
    items: Mapped[list["SalaryStructureItem"]] = relationship(
        "SalaryStructureItem", back_populates="salary_structure", cascade="all, delete-orphan"
    )


class SalaryStructureItem(Base):
    __tablename__ = "salary_structure_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    salary_structure_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("salary_structures.id", ondelete="CASCADE"), nullable=False
    )
    component_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("salary_components.id"), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    is_percentage: Mapped[bool] = mapped_column(Boolean, default=False)

    salary_structure: Mapped["SalaryStructure"] = relationship(
        "SalaryStructure", back_populates="items"
    )
    component: Mapped["SalaryComponent"] = relationship("SalaryComponent")


# ─────────────────────────────────────────────────────────────
# Payroll Period (monthly cycle)
# ─────────────────────────────────────────────────────────────
class PayrollPeriod(Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_payroll_period_year_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-12
    period_name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "August 2026"
    working_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[PayrollStatus] = mapped_column(
        Enum(PayrollStatus), default=PayrollStatus.DRAFT, nullable=False
    )
    finalized_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    payroll_records: Mapped[list["PayrollRecord"]] = relationship(
        "PayrollRecord", back_populates="period"
    )
    finalized_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[finalized_by_id])  # type: ignore[name-defined]
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_id])  # type: ignore[name-defined]


# ─────────────────────────────────────────────────────────────
# Payroll Record — per employee per month
# ─────────────────────────────────────────────────────────────
class PayrollRecord(Base):
    __tablename__ = "payroll_records"

    __table_args__ = (
        UniqueConstraint("employee_id", "period_id", name="uq_payroll_employee_period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    period_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False
    )

    # Attendance summary used for calculation
    total_working_days: Mapped[int] = mapped_column(Integer, default=0)
    present_days: Mapped[float] = mapped_column(Float, default=0.0)
    absent_days: Mapped[float] = mapped_column(Float, default=0.0)
    half_days: Mapped[float] = mapped_column(Float, default=0.0)
    leave_days: Mapped[float] = mapped_column(Float, default=0.0)
    paid_leave_days: Mapped[float] = mapped_column(Float, default=0.0)
    off_duty_days: Mapped[float] = mapped_column(Float, default=0.0)
    qualifying_late_days: Mapped[int] = mapped_column(Integer, default=0)
    loss_of_pay_days: Mapped[float] = mapped_column(Float, default=0.0)
    lop_days: Mapped[float] = mapped_column(Float, default=0.0)
    ot_hours: Mapped[float] = mapped_column(Float, default=0.0)

    # Manual Salary Calculator fields
    collection: Mapped[float] = mapped_column(Float, default=0.0)
    payable_days: Mapped[float] = mapped_column(Float, default=0.0)
    salary_part: Mapped[float] = mapped_column(Float, default=0.0)
    lifetime_collection: Mapped[float] = mapped_column(Float, default=0.0)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False)
    salary_source: Mapped[Optional[str]] = mapped_column(String(20), default="MIGRATED", nullable=True)

    # Deductions
    lop_deduction: Mapped[float] = mapped_column(Float, default=0.0)
    security_fund_deduction: Mapped[float] = mapped_column(Float, default=0.0)
    carried_forward_deductions: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, server_default="0.0")

    # Salary calculated
    basic_salary: Mapped[float] = mapped_column(Float, default=0.0)
    gross_salary: Mapped[float] = mapped_column(Float, default=0.0)
    total_deductions: Mapped[float] = mapped_column(Float, default=0.0)
    ot_amount: Mapped[float] = mapped_column(Float, default=0.0)
    net_salary: Mapped[float] = mapped_column(Float, default=0.0)

    status: Mapped[PayrollStatus] = mapped_column(
        Enum(PayrollStatus), default=PayrollStatus.DRAFT
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="payroll_records")  # type: ignore[name-defined]
    period: Mapped["PayrollPeriod"] = relationship("PayrollPeriod", back_populates="payroll_records")
    items: Mapped[list["PayrollItem"]] = relationship(
        "PayrollItem", back_populates="payroll_record", cascade="all, delete-orphan"
    )
    salary_slip: Mapped[Optional["SalarySlip"]] = relationship(
        "SalarySlip", back_populates="payroll_record", uselist=False
    )


class PayrollItem(Base):
    __tablename__ = "payroll_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payroll_record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payroll_records.id", ondelete="CASCADE"), nullable=False
    )
    component_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("salary_components.id", ondelete="SET NULL"), nullable=True
    )
    component_name: Mapped[str] = mapped_column(String(100), nullable=False)
    component_type: Mapped[ComponentType] = mapped_column(Enum(ComponentType), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    payroll_record: Mapped["PayrollRecord"] = relationship("PayrollRecord", back_populates="items")
    component: Mapped[Optional["SalaryComponent"]] = relationship("SalaryComponent")


class SalarySlip(Base):
    __tablename__ = "salary_slips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    payroll_record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payroll_records.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    generated_by_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    payroll_record: Mapped["PayrollRecord"] = relationship(
        "PayrollRecord", back_populates="salary_slip"
    )
    generated_by: Mapped["User"] = relationship("User")  # type: ignore[name-defined]
