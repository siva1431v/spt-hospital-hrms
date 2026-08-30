"""
SPT Hospital HRMS — Shift Model
Configurable hospital shift schedules.
"""
from datetime import datetime, time, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, Integer, String, Time, Interval, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from sqlalchemy import ForeignKey


class ShiftCodeAlias(Base):
    """Maps device/PDF shift codes to canonical Shift records."""
    __tablename__ = "shift_code_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    device_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    shift_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False
    )
    target_window: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1 or 2 for split shifts
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationship
    shift: Mapped["Shift"] = relationship("Shift", backref="aliases")

class Shift(Base):
    __tablename__ = "shifts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Shift identification
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing (Window 1)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_overnight: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timing (Optional Window 2 for split/rotating shifts like Lab, Housekeeping, Security)
    is_split: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_time_2: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    end_time_2: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    is_overnight_2: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Grace period in minutes before late marking
    grace_period_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    # Expected working hours in minutes
    expected_working_minutes: Mapped[int] = mapped_column(Integer, default=480, nullable=False)  # 8h default

    # OT threshold — minutes worked beyond which counts as OT
    ot_threshold_minutes: Mapped[int] = mapped_column(Integer, default=480, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    employees: Mapped[list["Employee"]] = relationship(  # type: ignore[name-defined]
        "Employee", back_populates="shift"
    )

    def __repr__(self) -> str:
        return f"<Shift {self.code}: {self.start_time}–{self.end_time}>"
