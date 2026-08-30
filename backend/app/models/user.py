"""
SPT Hospital HRMS — User Model
Stores login accounts with role-based access control.
"""
import enum
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    HR_ADMIN = "HR_ADMIN"
    DEPT_MANAGER = "DEPT_MANAGER"
    EMPLOYEE = "EMPLOYEE"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.EMPLOYEE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Link to employee record (optional — admins may not have an employee record)
    employee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("employees.id", ondelete="SET NULL"), nullable=True
    )

    # Metadata
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    employee: Mapped[Optional["Employee"]] = relationship(  # type: ignore[name-defined]
        "Employee", back_populates="user", foreign_keys=[employee_id]
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(  # type: ignore[name-defined]
        "AuditLog", back_populates="user"
    )

    def __repr__(self) -> str:
        return f"<User {self.username} [{self.role}]>"
