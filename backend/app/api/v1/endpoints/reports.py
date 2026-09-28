"""
SPT Hospital HRMS — Reports API Endpoints
Generates attendance, payroll, and HR reports in JSON, Excel, and PDF.
"""
import io
import logging
import calendar
from datetime import date
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, extract, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.models.user import UserRole
from app.models.attendance import Attendance, AttendanceStatus
from app.models.employee import Employee
from app.models.department import Department
from app.models.payroll import PayrollRecord, PayrollPeriod

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["Reports"])


def _excel_response(wb, filename: str) -> Response:
    """Helper to return an openpyxl workbook as a file download."""
    import openpyxl
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/attendance")
async def attendance_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
    year: Annotated[Optional[int], Query(ge=2020, le=2050)] = None,
    department_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None),
    format: str = Query("json", pattern="^(json|excel)$"),
):
    """Attendance report with date range, department, and employee filters."""
    if year is not None and month is not None:
        last_day = calendar.monthrange(year, month)[1]
        if date_from is None:
            date_from = date(year, month, 1)
        if date_to is None:
            date_to = date(year, month, last_day)

    query = (
        select(Attendance)
        .options(
            selectinload(Attendance.employee),
            selectinload(Attendance.department),
        )
        .order_by(Attendance.attendance_date, Attendance.employee_id)
    )
    if date_from:
        query = query.where(Attendance.attendance_date >= date_from)
    if date_to:
        query = query.where(Attendance.attendance_date <= date_to)
    if department_id:
        query = query.where(Attendance.department_id == department_id)
    if employee_id:
        query = query.where(Attendance.employee_id == employee_id)
    if status_filter:
        try:
            query = query.where(Attendance.status == AttendanceStatus(status_filter))
        except ValueError:
            pass

    result = await db.execute(query)
    records = result.scalars().all()

    if format == "excel":
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Attendance Report"
        headers = ["Date", "Emp Code", "Employee Name", "Department", "Shift", "In Time",
                   "Out Time", "Work (hrs)", "OT (hrs)", "Status", "Corrected"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(fgColor="0F766E", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        for row_idx, a in enumerate(records, 2):
            ws.cell(row=row_idx, column=1, value=str(a.attendance_date))
            ws.cell(row=row_idx, column=2, value=a.employee.employee_id if a.employee else "")
            ws.cell(row=row_idx, column=3, value=a.employee.full_name if a.employee else "")
            ws.cell(row=row_idx, column=4, value=a.department.name if a.department else a.source_department_name)
            ws.cell(row=row_idx, column=5, value=a.source_shift_code or "")
            ws.cell(row=row_idx, column=6, value=a.source_in_time or "")
            ws.cell(row=row_idx, column=7, value=a.source_out_time or "")
            ws.cell(row=row_idx, column=8, value=round((a.work_minutes or 0) / 60, 2))
            ws.cell(row=row_idx, column=9, value=round((a.ot_minutes or 0) / 60, 2))
            ws.cell(row=row_idx, column=10, value=a.status.value)
            ws.cell(row=row_idx, column=11, value="Yes" if a.is_corrected else "No")
        return _excel_response(wb, "attendance_report.xlsx")

    return {
        "data": [
            {
                "date": a.attendance_date,
                "employee_code": a.employee.employee_id if a.employee else None,
                "employee_name": a.employee.full_name if a.employee else None,
                "department": a.department.name if a.department else a.source_department_name,
                "shift": a.source_shift_code,
                "in_time": a.source_in_time,
                "out_time": a.source_out_time,
                "work_hours": round((a.work_minutes or 0) / 60, 2),
                "ot_hours": round((a.ot_minutes or 0) / 60, 2),
                "status": a.status.value,
                "is_corrected": a.is_corrected,
            }
            for a in records
        ],
        "total": len(records),
    }


@router.get("/missing-punch")
async def missing_punch_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
    year: Annotated[Optional[int], Query(ge=2020, le=2050)] = None,
    department_id: Optional[int] = Query(None),
    format: str = Query("json", pattern="^(json|excel)$"),
):
    """Report of all 'Present (No OutPunch)' records."""
    if year is not None and month is not None:
        last_day = calendar.monthrange(year, month)[1]
        if date_from is None:
            date_from = date(year, month, 1)
        if date_to is None:
            date_to = date(year, month, last_day)

    query = (
        select(Attendance)
        .options(selectinload(Attendance.employee), selectinload(Attendance.department))
        .where(Attendance.status == AttendanceStatus.PRESENT_INCOMPLETE)
        .order_by(Attendance.attendance_date.desc())
    )
    if date_from:
        query = query.where(Attendance.attendance_date >= date_from)
    if date_to:
        query = query.where(Attendance.attendance_date <= date_to)
    if department_id:
        query = query.where(Attendance.department_id == department_id)

    result = await db.execute(query)
    records = result.scalars().all()

    if format == "excel":
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Missing Punch Report"
        headers = ["Date", "Emp Code", "Employee Name", "Department", "In Time", "Status"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(fgColor="D97706", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        for row_idx, a in enumerate(records, 2):
            ws.cell(row=row_idx, column=1, value=str(a.attendance_date))
            ws.cell(row=row_idx, column=2, value=a.employee.employee_id if a.employee else "")
            ws.cell(row=row_idx, column=3, value=a.employee.full_name if a.employee else "")
            ws.cell(row=row_idx, column=4, value=a.department.name if a.department else (a.source_department_name or ""))
            ws.cell(row=row_idx, column=5, value=a.source_in_time or "")
            ws.cell(row=row_idx, column=6, value="MISSING OUT PUNCH")
        return _excel_response(wb, "missing_punch_report.xlsx")

    return {
        "report": "Missing Punch Report",
        "data": [
            {
                "date": a.attendance_date,
                "employee_code": a.employee.employee_id if a.employee else None,
                "employee_name": a.employee.full_name if a.employee else None,
                "department": a.department.name if a.department else a.source_department_name,
                "in_time": a.source_in_time,
                "out_time": None,
                "status": "MISSING OUT PUNCH",
            }
            for a in records
        ],
        "total": len(records),
    }


@router.get("/overtime")
async def overtime_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
    year: Annotated[Optional[int], Query(ge=2020, le=2050)] = None,
    department_id: Optional[int] = Query(None),
    format: str = Query("json", pattern="^(json|excel)$"),
):
    """OT report with employee, department, date, hours."""
    if year is not None and month is not None:
        last_day = calendar.monthrange(year, month)[1]
        if date_from is None:
            date_from = date(year, month, 1)
        if date_to is None:
            date_to = date(year, month, last_day)

    query = (
        select(Attendance)
        .options(selectinload(Attendance.employee), selectinload(Attendance.department))
        .where(Attendance.ot_minutes > 0)
        .order_by(Attendance.ot_minutes.desc())
    )
    if date_from:
        query = query.where(Attendance.attendance_date >= date_from)
    if date_to:
        query = query.where(Attendance.attendance_date <= date_to)
    if department_id:
        query = query.where(Attendance.department_id == department_id)

    result = await db.execute(query)
    records = result.scalars().all()

    if format == "excel":
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Overtime Report"
        headers = ["Date", "Emp Code", "Employee Name", "Department", "OT Hours", "OT Minutes"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(fgColor="7C3AED", fill_type="solid")
            cell.alignment = Alignment(horizontal="center")
        for row_idx, a in enumerate(records, 2):
            ws.cell(row=row_idx, column=1, value=str(a.attendance_date))
            ws.cell(row=row_idx, column=2, value=a.employee.employee_id if a.employee else "")
            ws.cell(row=row_idx, column=3, value=a.employee.full_name if a.employee else "")
            ws.cell(row=row_idx, column=4, value=a.department.name if a.department else (a.source_department_name or ""))
            ws.cell(row=row_idx, column=5, value=round((a.ot_minutes or 0) / 60, 2))
            ws.cell(row=row_idx, column=6, value=a.ot_minutes or 0)
        return _excel_response(wb, "overtime_report.xlsx")

    return {
        "report": "Overtime Report",
        "data": [
            {
                "date": a.attendance_date,
                "employee_code": a.employee.employee_id if a.employee else None,
                "employee_name": a.employee.full_name if a.employee else None,
                "department": a.department.name if a.department else a.source_department_name,
                "ot_hours": round((a.ot_minutes or 0) / 60, 2),
                "ot_minutes": a.ot_minutes,
            }
            for a in records
        ],
        "total": len(records),
    }


@router.get("/salary-register")
async def salary_register(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
    year: Annotated[Optional[int], Query(ge=2020, le=2050)] = None,
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
    department_id: Optional[int] = Query(None),
    format: str = Query("json", pattern="^(json|excel)$"),
):
    """Payroll salary register report."""
    query = (
        select(PayrollRecord)
        .join(PayrollPeriod)
        .options(
            selectinload(PayrollRecord.employee).selectinload(Employee.department),
            selectinload(PayrollRecord.period),
        )
        .order_by(PayrollRecord.employee_id)
    )
    if year and isinstance(year, int):
        query = query.where(PayrollPeriod.year == year)
    if month and isinstance(month, int):
        query = query.where(PayrollPeriod.month == month)

    result = await db.execute(query)
    records = result.scalars().all()

    if format == "excel":
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Salary Register"
        headers = ["Emp Code", "Name", "Department", "Period", "Present", "Absent",
                   "OT Hours", "Basic", "Gross", "Deductions", "Net Salary"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=h)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(fgColor="0F172A", fill_type="solid")
        for row_idx, r in enumerate(records, 2):
            ws.cell(row=row_idx, column=1, value=r.employee.employee_id if r.employee else "")
            ws.cell(row=row_idx, column=2, value=r.employee.full_name if r.employee else "")
            ws.cell(row=row_idx, column=3, value=r.employee.department.name if r.employee and r.employee.department else "")
            ws.cell(row=row_idx, column=4, value=r.period.period_name if r.period else "")
            ws.cell(row=row_idx, column=5, value=r.present_days)
            ws.cell(row=row_idx, column=6, value=r.absent_days)
            ws.cell(row=row_idx, column=7, value=r.ot_hours)
            ws.cell(row=row_idx, column=8, value=round(r.basic_salary, 2))
            ws.cell(row=row_idx, column=9, value=round(r.gross_salary, 2))
            ws.cell(row=row_idx, column=10, value=round(r.total_deductions, 2))
            ws.cell(row=row_idx, column=11, value=round(r.net_salary, 2))
        return _excel_response(wb, "salary_register.xlsx")

    return {
        "report": "Salary Register",
        "data": [
            {
                "employee_code": r.employee.employee_id if r.employee else None,
                "employee_name": r.employee.full_name if r.employee else None,
                "department": r.employee.department.name if r.employee and r.employee.department else None,
                "period": r.period.period_name if r.period else None,
                "present_days": r.present_days,
                "absent_days": r.absent_days,
                "ot_hours": r.ot_hours,
                "basic_salary": round(r.basic_salary, 2),
                "gross_salary": round(r.gross_salary, 2),
                "total_deductions": round(r.total_deductions, 2),
                "net_salary": round(r.net_salary, 2),
                "status": r.status.value,
            }
            for r in records
        ],
        "total": len(records),
    }


@router.get("/lateness-lop")
async def lateness_lop_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
    year: Annotated[Optional[int], Query(ge=2020, le=2050)] = None,
    month: Annotated[Optional[int], Query(ge=1, le=12)] = None,
    department_id: Optional[int] = Query(None),
    format: str = Query("json", pattern="^(json|excel)$"),
):
    """Lateness and Loss of Pay (LOP) deduction summary report."""
    import calendar
    from app.models.attendance import MonthlyAttendanceAggregate

    today = date.today()
    target_year = year if isinstance(year, int) else today.year
    target_month = month if isinstance(month, int) else today.month

    days_in_month = calendar.monthrange(target_year, target_month)[1]

    # Query active employees
    emp_query = select(Employee).options(selectinload(Employee.department)).where(Employee.is_active == True)
    if department_id:
        emp_query = emp_query.where(Employee.department_id == department_id)
    emp_query = emp_query.order_by(Employee.first_name)
    emp_res = await db.execute(emp_query)
    employees = emp_res.scalars().all()

    report_data = []
    for emp in employees:
        # Check monthly aggregate
        agg_res = await db.execute(
            select(MonthlyAttendanceAggregate).where(
                MonthlyAttendanceAggregate.employee_id == emp.id,
                MonthlyAttendanceAggregate.year == target_year,
                MonthlyAttendanceAggregate.month == target_month,
            )
        )
        agg = agg_res.scalar_one_or_none()

        if agg and agg.late_by_days > 0:
            late_days_count = agg.late_by_days
            lop_days = float(agg.lop_days)
        else:
            # Check daily attendance records
            att_res = await db.execute(
                select(Attendance).where(
                    Attendance.employee_id == emp.id,
                    extract("year", Attendance.attendance_date) == target_year,
                    extract("month", Attendance.attendance_date) == target_month,
                    Attendance.is_late == True,
                )
            )
            late_records = att_res.scalars().all()
            late_days_count = len(late_records)
            lop_days = float(late_days_count // 3)

        basic_salary = float(emp.basic_salary or 0.0)
        per_day = round(basic_salary / days_in_month, 2) if days_in_month > 0 else 0.0
        lop_deduction_amount = round(lop_days * per_day, 2)

        report_data.append({
            "employee_id": emp.id,
            "employee_code": emp.employee_id,
            "biometric_code": emp.biometric_code,
            "employee_name": emp.full_name,
            "department": emp.department.name if emp.department else "—",
            "year": year,
            "month": month,
            "late_days_count": late_days_count,
            "lop_days": lop_days,
            "basic_salary": basic_salary,
            "per_day_rate": per_day,
            "lop_deduction_amount": lop_deduction_amount,
        })

    if format == "excel":
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"Lateness LOP {year}-{month:02d}"

        # Load configured grace period
        from app.models.audit import SystemSetting
        grace_res = await db.execute(
            select(SystemSetting).where(SystemSetting.key == "attendance_grace_period")
        )
        s_obj = grace_res.scalar_one_or_none()
        grace_period = int(s_obj.value) if s_obj and s_obj.value else 5

        headers = [
            "Emp Code", "Biometric", "Employee Name", "Department",
            f"Late Days (>{grace_period}m)", "LOP Days (Late/3)", "Basic Salary (₹)",
            "Per Day Rate (₹)", "LOP Deduction (₹)"
        ]
        header_font = Font(bold=True, color="FFFFFF", name="Arial", size=10)
        header_fill = PatternFill(fgColor="0F766E", fill_type="solid")
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        for row_idx, r in enumerate(report_data, 2):
            ws.cell(row=row_idx, column=1, value=r["employee_code"])
            ws.cell(row=row_idx, column=2, value=r["biometric_code"] or "")
            ws.cell(row=row_idx, column=3, value=r["employee_name"])
            ws.cell(row=row_idx, column=4, value=r["department"])
            ws.cell(row=row_idx, column=5, value=r["late_days_count"])
            ws.cell(row=row_idx, column=6, value=r["lop_days"])
            ws.cell(row=row_idx, column=7, value=r["basic_salary"])
            ws.cell(row=row_idx, column=8, value=r["per_day_rate"])
            ws.cell(row=row_idx, column=9, value=r["lop_deduction_amount"])
            for col_idx in range(1, len(headers) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                if col_idx in [5, 6]:
                    cell.alignment = Alignment(horizontal="center")
                elif col_idx in [7, 8, 9]:
                    cell.alignment = Alignment(horizontal="right")
                    cell.number_format = "#,##0.00"

        return _excel_response(wb, f"lateness_lop_report_{year}_{month:02d}.xlsx")

    return {
        "report": "Lateness & LOP Summary Report",
        "year": year,
        "month": month,
        "total_employees": len(report_data),
        "total_lop_days": sum(r["lop_days"] for r in report_data),
        "total_lop_deductions": round(sum(r["lop_deduction_amount"] for r in report_data), 2),
        "data": report_data,
    }
