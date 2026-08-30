"""
SPT Hospital HRMS — Leave Models
Configurable leave types, requests, and balances.
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


class LeaveRequestStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class LeaveType(Base):
    __tablename__ = "leave_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_days_per_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    leave_requests: Mapped[list["LeaveRequest"]] = relationship(
        "LeaveRequest", back_populates="leave_type"
    )


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    leave_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leave_types.id"), nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_count: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[LeaveRequestStatus] = mapped_column(
        Enum(LeaveRequestStatus), default=LeaveRequestStatus.PENDING, nullable=False
    )
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    employee: Mapped["Employee"] = relationship("Employee", back_populates="leave_requests")  # type: ignore[name-defined]
    leave_type: Mapped["LeaveType"] = relationship("LeaveType", back_populates="leave_requests")
    reviewed_by: Mapped[Optional["User"]] = relationship("User")  # type: ignore[name-defined]


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type_id", "year", name="uq_leave_balance"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    leave_type_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("leave_types.id"), nullable=False
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    allocated_days: Mapped[float] = mapped_column(Float, default=0.0)
    used_days: Mapped[float] = mapped_column(Float, default=0.0)
    remaining_days: Mapped[float] = mapped_column(Float, default=0.0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    employee: Mapped["Employee"] = relationship("Employee")  # type: ignore[name-defined]
    leave_type: Mapped["LeaveType"] = relationship("LeaveType")
