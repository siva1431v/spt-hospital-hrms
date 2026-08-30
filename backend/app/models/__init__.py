"""
SPT Hospital HRMS — Models Package
Imports all models to ensure they are registered with SQLAlchemy.
"""
from app.models.user import User, UserRole
from app.models.department import Department, Designation
from app.models.shift import Shift
from app.models.employee import Employee, EmploymentType, Gender
from app.models.attendance import (
    Attendance, AttendanceStatus, AttendanceImport, AttendanceImportRecord,
    AttendanceCorrection, AttendanceException, ImportStatus,
    ExceptionSeverity, ExceptionReviewStatus, MonthlyAttendanceAggregate
)
from app.models.leave import LeaveType, LeaveRequest, LeaveBalance, LeaveRequestStatus
from app.models.payroll import (
    SalaryComponent, SalaryStructure, SalaryStructureItem,
    PayrollPeriod, PayrollRecord, PayrollItem, SalarySlip,
    ComponentType, PayrollStatus,
)
from app.models.audit import AuditLog, SystemSetting

__all__ = [
    "User", "UserRole",
    "Department", "Designation",
    "Shift",
    "Employee", "EmploymentType", "Gender",
    "Attendance", "AttendanceStatus", "AttendanceImport", "AttendanceImportRecord",
    "AttendanceCorrection", "AttendanceException", "ImportStatus",
    "ExceptionSeverity", "ExceptionReviewStatus", "MonthlyAttendanceAggregate",
    "LeaveType", "LeaveRequest", "LeaveBalance", "LeaveRequestStatus",
    "SalaryComponent", "SalaryStructure", "SalaryStructureItem",
    "PayrollPeriod", "PayrollRecord", "PayrollItem", "SalarySlip",
    "ComponentType", "PayrollStatus",
    "AuditLog", "SystemSetting",
]
