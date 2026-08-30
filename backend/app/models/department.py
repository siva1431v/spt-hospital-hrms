"""
SPT Hospital HRMS — Department & Designation Models
"""
import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )
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
        "Employee", back_populates="department", foreign_keys="Employee.department_id"
    )
    manager: Mapped[Optional["Employee"]] = relationship(  # type: ignore[name-defined]
        "Employee", foreign_keys=[manager_id]
    )

    def __repr__(self) -> str:
        return f"<Department {self.code}: {self.name}>"


class Designation(Base):
    __tablename__ = "designations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    employees: Mapped[list["Employee"]] = relationship(  # type: ignore[name-defined]
        "Employee", back_populates="designation"
    )

    def __repr__(self) -> str:
        return f"<Designation {self.name}>"
