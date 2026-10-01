"""
SPT Hospital HRMS — Attendance Import Service
Handles mapping, validation, duplicate detection, and DB commit of parsed PDF records.
"""
import hashlib
import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from app.models.employee import Employee
from app.models.department import Department
from app.models.shift import Shift
from app.models.attendance import (
    Attendance, AttendanceStatus, AttendanceImport,
    AttendanceImportRecord, AttendanceException,
    ExceptionSeverity, ExceptionReviewStatus, ImportStatus,
)
from app.parsers.pdf.models import ParsedReport, ParsedAttendanceRecord, ParsedStatus, ParseWarning
from app.parsers.pdf.parser import parse_attendance_pdf
from app.utils.audit import log_audit

logger = logging.getLogger(__name__)


def _parse_time_to_datetime(
    attendance_date: date,
    time_str: Optional[str],
    is_next_day: bool = False,
) -> Optional[datetime]:
    """
    Convert a time string (HH:MM) and an attendance date into a full datetime.
    If is_next_day=True, adds one day (for overnight shift checkout).
    """
    if not time_str or time_str in ("00:00", "", "--"):
        return None
    try:
        h, m = map(int, time_str.strip().split(":"))
        target_date = attendance_date
        if is_next_day:
            from datetime import timedelta
            target_date = attendance_date + timedelta(days=1)
        return datetime(
            target_date.year, target_date.month, target_date.day, h, m,
            tzinfo=timezone.utc,
        )
    except (ValueError, AttributeError):
        return None


def _map_status(parsed_status: ParsedStatus, is_overnight: bool) -> AttendanceStatus:
    """Map parser status to database AttendanceStatus."""
    mapping = {
        ParsedStatus.PRESENT: AttendanceStatus.PRESENT,
        ParsedStatus.ABSENT: AttendanceStatus.ABSENT,
        ParsedStatus.PRESENT_INCOMPLETE: AttendanceStatus.PRESENT_INCOMPLETE,
        ParsedStatus.PRESENT_OVERNIGHT: AttendanceStatus.PRESENT_OVERNIGHT,
    }
    if is_overnight and parsed_status == ParsedStatus.PRESENT:
        return AttendanceStatus.PRESENT_OVERNIGHT
    return mapping.get(parsed_status, AttendanceStatus.PRESENT)


async def get_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file for duplicate detection."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            sha256.update(chunk)
    return sha256.hexdigest()


class AttendanceImportService:
    """
    Orchestrates the full import workflow:
    1. Parse PDF
    2. Map employee codes to employees
    3. Map department names to departments
    4. Detect duplicates
    5. Return preview (no DB writes)
    6. Commit confirmed records to DB
    """

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id

    async def _load_employee_map(self) -> dict[str, Employee]:
        """Load all employees indexed by biometric_code, employee_id, and numeric code suffix."""
        import re
        from sqlalchemy.orm import selectinload
        result = await self.db.execute(
            select(Employee).options(selectinload(Employee.shift))
        )
        employees = result.scalars().all()
        emp_map: dict[str, Employee] = {}
        for emp in employees:
            if emp.biometric_code:
                emp_map[str(emp.biometric_code).strip()] = emp
            if emp.employee_id:
                emp_code_str = str(emp.employee_id).strip()
                emp_map[emp_code_str] = emp
                # Strip leading non-digit prefix (e.g. SPT201 -> 201)
                num_part = re.sub(r"^[^\d]+", "", emp_code_str)
                if num_part and num_part not in emp_map:
                    emp_map[num_part] = emp
        return emp_map

    async def _load_department_map(self) -> dict[str, Department]:
        """Load all departments indexed by normalized name, code, and aliases."""
        result = await self.db.execute(select(Department))
        departments = result.scalars().all()
        dept_map = {dept.name.upper().strip(): dept for dept in departments}
        for dept in departments:
            if dept.code:
                dept_map[dept.code.upper().strip()] = dept
        
        # Aliases for PDF department names
        if "DOCTOR" in dept_map:
            doc_dept = dept_map["DOCTOR"]
            dept_map["DR"] = doc_dept
            dept_map["DR."] = doc_dept
        return dept_map

    async def _load_shift_map(self) -> tuple[dict[str, Shift], dict[str, int]]:
        """Load all shifts indexed by code, including device code aliases and target window preferences."""
        from sqlalchemy.orm import selectinload
        from app.models.shift import ShiftCodeAlias
        result = await self.db.execute(select(Shift))
        shifts = result.scalars().all()
        shift_map = {shift.code.upper().strip(): shift for shift in shifts}
        # Also add shift name as a lookup key
        for shift in shifts:
            if shift.name:
                shift_map[shift.name.upper().strip()] = shift
        # Load device code aliases and target window preferences
        alias_target_window_map: dict[str, int] = {}
        alias_result = await self.db.execute(
            select(ShiftCodeAlias).options(selectinload(ShiftCodeAlias.shift))
        )
        for alias in alias_result.scalars().all():
            code_key = alias.device_code.upper().strip()
            shift_map[code_key] = alias.shift
            if alias.target_window:
                alias_target_window_map[code_key] = alias.target_window
        return shift_map, alias_target_window_map

    async def _check_duplicate(self, employee_id: int, attendance_date: date) -> bool:
        """Check if an attendance record already exists for employee+date."""
        result = await self.db.execute(
            select(Attendance).where(
                Attendance.employee_id == employee_id,
                Attendance.attendance_date == attendance_date,
            )
        )
        return result.scalar_one_or_none() is not None

    async def preview(
        self, pdf_path: str, filename: str, file_size: int
    ) -> dict:
        """
        Parse the PDF and return a preview dict without saving anything.
        Called by POST /attendance/import/preview.
        """
        # Load grace period from system settings
        from app.models.audit import SystemSetting
        grace_minutes = 5
        try:
            s_res = await self.db.execute(
                select(SystemSetting).where(SystemSetting.key == "attendance_grace_period")
            )
            s = s_res.scalar_one_or_none()
            if s and s.value:
                grace_minutes = int(s.value)
        except Exception:
            pass

        # Parse PDF
        report = parse_attendance_pdf(pdf_path, grace_minutes=grace_minutes)

        # Load lookup maps
        employee_map = await self._load_employee_map()
        dept_map = await self._load_department_map()
        shift_map, alias_target_window_map = await self._load_shift_map()

        preview_records = []
        unknown_employee_codes = set()
        unknown_department_names = set()
        unmapped_shift_codes = set()
        stats = {
            "total_records": 0,
            "present": 0,
            "absent": 0,
            "incomplete": 0,
            "overnight": 0,
            "duplicate": 0,
            "unknown_employees": 0,
            "unknown_departments": 0,
            "errors": 0,
            "warnings": 0,
            "unmapped_shifts": 0,
        }

        for raw_record in report.all_records:
            stats["total_records"] += 1
            preview_item = {
                "attendance_date": raw_record.attendance_date.isoformat() if raw_record.attendance_date else None,
                "department_name": raw_record.department_name,
                "employee_code": raw_record.employee_code,
                "employee_name": raw_record.employee_name,
                "shift_code": raw_record.shift_code,
                "in_time": raw_record.in_time_str,
                "out_time": raw_record.out_time_str,
                "work_duration": raw_record.raw_work_duration,
                "ot": raw_record.raw_ot,
                "status": raw_record.status.value,
                "is_overnight": raw_record.is_overnight,
                "warnings": [w.value for w in raw_record.warnings],
                "errors": raw_record.parse_errors,
                "is_duplicate": False,
                "is_unknown_employee": False,
                "is_unknown_department": False,
                "mapped_employee_id": None,
                "mapped_employee_name": None,
                "mapped_department_id": None,
            }

            # Map employee
            emp = employee_map.get(raw_record.employee_code) if raw_record.employee_code else None
            if emp:
                preview_item["mapped_employee_id"] = emp.id
                preview_item["mapped_employee_name"] = emp.full_name

                # Check duplicate
                if report.report_type == "Monthly Status Report (Summary Report)":
                    year_val = report.date_range_start.year if report.date_range_start else None
                    month_val = report.date_range_start.month if report.date_range_start else None
                    if emp and year_val and month_val:
                        from app.models.attendance import MonthlyAttendanceAggregate
                        existing_agg_res = await self.db.execute(
                            select(MonthlyAttendanceAggregate).where(
                                MonthlyAttendanceAggregate.employee_id == emp.id,
                                MonthlyAttendanceAggregate.year == year_val,
                                MonthlyAttendanceAggregate.month == month_val,
                            )
                        )
                        if existing_agg_res.scalar_one_or_none():
                            preview_item["is_duplicate"] = True
                            stats["duplicate"] += 1
                elif raw_record.attendance_date:
                    is_dup = await self._check_duplicate(emp.id, raw_record.attendance_date)
                    if is_dup:
                        preview_item["is_duplicate"] = True
                        stats["duplicate"] += 1
            else:
                if raw_record.employee_code:
                    preview_item["is_unknown_employee"] = True
                    unknown_employee_codes.add(raw_record.employee_code)
                    stats["unknown_employees"] += 1
                    stats["errors"] += 1

            # Map department
            dept_key = (raw_record.department_name or "").upper().strip()
            dept = dept_map.get(dept_key)
            if dept:
                preview_item["mapped_department_id"] = dept.id
            elif raw_record.department_name:
                preview_item["is_unknown_department"] = True
                unknown_department_names.add(raw_record.department_name)
                stats["unknown_departments"] += 1

            shift_code = (raw_record.shift_code or "").upper().strip()
            if shift_code and shift_code not in shift_map:
                unmapped_shift_codes.add(raw_record.shift_code)
                stats["unmapped_shifts"] += 1

            # Status counts
            if raw_record.status == ParsedStatus.PRESENT:
                stats["present"] += 1
            elif raw_record.status == ParsedStatus.ABSENT:
                stats["absent"] += 1
            elif raw_record.status == ParsedStatus.PRESENT_INCOMPLETE:
                stats["incomplete"] += 1
                stats["warnings"] += 1
            if raw_record.is_overnight:
                stats["overnight"] += 1
            if raw_record.warnings:
                stats["warnings"] += 1
            if raw_record.parse_errors:
                stats["errors"] += 1

            preview_records.append(preview_item)

        file_hash = await get_file_hash(pdf_path)

        # Check if this exact file was already imported
        existing_import_stmt = (
            select(AttendanceImport)
            .where(
                AttendanceImport.file_hash == file_hash,
                AttendanceImport.status.in_([
                    ImportStatus.COMPLETED,
                    ImportStatus.COMPLETED_WITH_WARNINGS,
                    ImportStatus.PARTIAL,
                    ImportStatus.SKIPPED,
                ]),
            )
            .order_by(AttendanceImport.imported_at.desc())
        )
        existing_import_res = await self.db.execute(existing_import_stmt)
        existing_import = existing_import_res.scalars().first()

        return {
            "report_type": report.report_type,
            "company_name": report.company_name,
            "date_range_start": report.date_range_start.isoformat() if report.date_range_start else None,
            "date_range_end": report.date_range_end.isoformat() if report.date_range_end else None,
            "filename": filename,
            "file_size": file_size,
            "file_hash": file_hash,
            "is_duplicate_file": bool(existing_import),
            "existing_import": {
                "id": existing_import.id,
                "filename": existing_import.filename,
                "imported_at": existing_import.imported_at.isoformat() if existing_import.imported_at else None,
                "records_imported": existing_import.records_imported,
                "records_duplicate": existing_import.records_duplicate,
                "status": existing_import.status.value,
            } if existing_import else None,
            "pdf_path": pdf_path,
            "total_pages": report.total_pages,
            "statistics": stats,
            "unique_departments": list(report.unique_departments),
            "unique_employee_codes": list(report.unique_employee_codes),
            "unknown_employee_codes": list(unknown_employee_codes),
            "unknown_department_names": list(unknown_department_names),
            "unmapped_shift_codes": list(unmapped_shift_codes),
            "records": preview_records,
            "monthly_aggregates": [
                {
                    "employee_code": agg.employee_code,
                    "employee_name": agg.employee_name,
                    "department_name": agg.department_name,
                    "company_name": agg.company_name,
                    "total_work_duration": agg.total_work_duration,
                    "total_ot": agg.total_ot,
                    "present_count": agg.present_count,
                    "absent_count": agg.absent_count,
                    "weekly_off_count": agg.weekly_off_count,
                    "holidays_count": agg.holidays_count,
                    "leaves_taken": agg.leaves_taken,
                    "late_by_hrs": agg.late_by_hrs,
                    "late_by_days": agg.late_by_days,
                    "late_days_device": agg.late_days_device,
                    "late_days_qualifying": agg.late_days_qualifying,
                    "lop_days": agg.lop_days,
                    "early_by_hrs": agg.early_by_hrs,
                    "early_going_by_days": agg.early_going_by_days,
                    "total_duration_with_ot": agg.total_duration_with_ot,
                    "average_working_hrs": agg.average_working_hrs,
                    "has_zero_punches": agg.has_zero_punches,
                }
                for agg in report.monthly_aggregates
            ],
        }

    async def commit(
        self,
        preview_data: dict,
        duplicate_action: str = "skip",  # "skip" | "update"
        employee_mappings: Optional[dict] = None,  # {unknown_code: employee_id}
        department_mappings: Optional[dict] = None,  # {unknown_name: dept_id}
    ) -> dict:
        """
        Commit the attendance records to the database.
        Called by POST /attendance/import/commit.

        Args:
            preview_data: The dict returned by preview()
            duplicate_action: What to do with duplicates ("skip" or "update")
            employee_mappings: Manual mappings from admin: {biometric_code: employee_id}
            department_mappings: Manual mappings from admin: {dept_name: dept_id}
        """
        employee_mappings = employee_mappings or {}
        department_mappings = department_mappings or {}

        # Load employee/dept maps again (with manual overrides)
        employee_map = await self._load_employee_map()
        dept_map = await self._load_department_map()
        shift_map, alias_target_window_map = await self._load_shift_map()

        # Merge manual mappings into employee_map (by code → Employee)
        for code_str, emp_id in employee_mappings.items():
            result = await self.db.execute(select(Employee).where(Employee.id == int(emp_id)))
            emp = result.scalar_one_or_none()
            if emp:
                employee_map[str(code_str)] = emp

        # Merge manual department mappings
        for dept_name, dept_id in department_mappings.items():
            result = await self.db.execute(select(Department).where(Department.id == int(dept_id)))
            dept = result.scalar_one_or_none()
            if dept:
                dept_map[dept_name.upper().strip()] = dept

        # Create the import session record
        import_session = AttendanceImport(
            filename=preview_data.get("filename", "attendance_report.pdf"),
            file_path=preview_data.get("_temp_path") or preview_data.get("pdf_path") or preview_data.get("filename", "attendance_report.pdf"),
            file_size_bytes=preview_data.get("file_size", 0),
            file_hash=preview_data.get("file_hash", ""),
            report_type=preview_data.get("report_type"),
            company_name=preview_data.get("company_name"),
            date_range_start=date.fromisoformat(preview_data["date_range_start"]) if preview_data.get("date_range_start") else None,
            date_range_end=date.fromisoformat(preview_data["date_range_end"]) if preview_data.get("date_range_end") else None,
            status=ImportStatus.PROCESSING,
            uploaded_by_id=self.user_id,
        )
        self.db.add(import_session)
        await self.db.flush()
        imported = 0
        skipped = 0
        updated = 0
        errors = 0

        is_skip = duplicate_action.lower() in ("skip", "ignore")
        is_update = not is_skip

        # Special handling for Monthly Status Report (Summary Report)
        if preview_data.get("report_type") == "Monthly Status Report (Summary Report)":
            from app.models.attendance import MonthlyAttendanceAggregate

            year_val = None
            month_val = None
            if preview_data.get("date_range_start"):
                try:
                    dt = date.fromisoformat(str(preview_data["date_range_start"]))
                    year_val = dt.year
                    month_val = dt.month
                except Exception:
                    pass

            for record_data in preview_data["records"]:
                emp_code = record_data.get("employee_code")
                dept_name = record_data.get("department_name", "")
                att_date_str = record_data.get("attendance_date")

                emp = employee_map.get(emp_code)
                if not emp and employee_mappings:
                    manual_id = employee_mappings.get(emp_code)
                    if manual_id:
                        result = await self.db.execute(select(Employee).where(Employee.id == int(manual_id)))
                        emp = result.scalar_one_or_none()

                dept_key = dept_name.upper().strip()
                dept = dept_map.get(dept_key)
                dept_id = dept.id if dept else None
                if not dept and department_mappings:
                    manual_dept_id = department_mappings.get(dept_name)
                    if manual_dept_id:
                        dept_id = int(manual_dept_id)

                is_dup = False
                if emp and year_val and month_val:
                    existing_agg = (await self.db.execute(
                        select(MonthlyAttendanceAggregate).where(
                            MonthlyAttendanceAggregate.employee_id == emp.id,
                            MonthlyAttendanceAggregate.year == year_val,
                            MonthlyAttendanceAggregate.month == month_val,
                        )
                    )).scalar_one_or_none()
                    if existing_agg:
                        is_dup = True

                if is_dup:
                    if is_skip:
                        skipped += 1
                    else:
                        updated += 1
                elif emp:
                    imported += 1
                else:
                    errors += 1

                ir = AttendanceImportRecord(
                    import_id=import_session.id,
                    raw_date=att_date_str,
                    raw_department=dept_name,
                    raw_employee_code=emp_code,
                    raw_employee_name=record_data.get("employee_name"),
                    raw_shift=record_data.get("shift_code"),
                    raw_in_time=record_data.get("in_time"),
                    raw_out_time=record_data.get("out_time"),
                    raw_work_duration=record_data.get("work_duration"),
                    raw_ot=record_data.get("ot"),
                    raw_status=record_data.get("status"),
                    mapped_employee_id=emp.id if emp else None,
                    mapped_department_id=dept_id,
                    is_duplicate=is_dup,
                    has_warning=bool(record_data.get("warnings")),
                    warning_message=",".join(record_data.get("warnings") or []),
                )
                self.db.add(ir)

            # Persist monthly aggregates
            monthly_aggs = preview_data.get("monthly_aggregates", [])
            if monthly_aggs:
                for agg_data in monthly_aggs:
                    emp_code = str(agg_data.get("employee_code", "")).strip()
                    emp = employee_map.get(emp_code)
                    if not emp and employee_mappings and emp_code in employee_mappings:
                        mapped_id = int(employee_mappings[emp_code])
                        emp_result = await self.db.execute(
                            select(Employee).where(Employee.id == mapped_id)
                        )
                        emp = emp_result.scalar_one_or_none()

                    if year_val and month_val:
                        if emp:
                            existing_agg = (await self.db.execute(
                                select(MonthlyAttendanceAggregate).where(
                                    MonthlyAttendanceAggregate.employee_id == emp.id,
                                    MonthlyAttendanceAggregate.year == year_val,
                                    MonthlyAttendanceAggregate.month == month_val,
                                )
                            )).scalar_one_or_none()
                            if existing_agg:
                                if is_skip:
                                    continue
                                await self.db.delete(existing_agg)

                        norm_dept_name = dept.name if dept else (emp.department.name if emp and emp.department else agg_data.get("department_name", ""))
                        if norm_dept_name and norm_dept_name.upper() in ("DR", "DR."):
                            norm_dept_name = "DOCTOR"

                        new_agg = MonthlyAttendanceAggregate(
                            import_id=import_session.id,
                            employee_id=emp.id if emp else None,
                            employee_code=emp_code,
                            employee_name=agg_data.get("employee_name", ""),
                            department_name=norm_dept_name,
                            company_name=agg_data.get("company_name", ""),
                            year=year_val,
                            month=month_val,
                            total_work_duration=agg_data.get("total_work_duration"),
                            total_ot=agg_data.get("total_ot"),
                            present_count=agg_data.get("present_count", 0),
                            absent_count=agg_data.get("absent_count", 0),
                            weekly_off_count=agg_data.get("weekly_off_count", 0),
                            holidays_count=agg_data.get("holidays_count", 0),
                            leaves_taken=agg_data.get("leaves_taken", 0),
                            late_by_hrs=agg_data.get("late_by_hrs"),
                            late_by_days=agg_data.get("late_by_days", 0),
                            late_days_device=agg_data.get("late_days_device", 0),
                            late_days_qualifying=agg_data.get("late_days_qualifying", 0),
                            lop_days=agg_data.get("lop_days", 0),
                            early_by_hrs=agg_data.get("early_by_hrs"),
                            early_going_by_days=agg_data.get("early_going_by_days", 0),
                            total_duration_with_ot=agg_data.get("total_duration_with_ot"),
                            average_working_hrs=agg_data.get("average_working_hrs"),
                            has_zero_punches=agg_data.get("has_zero_punches", False),
                        )
                        self.db.add(new_agg)

            import_session.report_type = preview_data.get("report_type")
            import_session.company_name = preview_data.get("company_name")
            import_session.records_imported = imported
            import_session.records_duplicate = skipped + updated
            import_session.records_error = errors
            import_session.total_records_in_pdf = len(preview_data["records"])
            import_session.status = ImportStatus.COMPLETED if errors == 0 else ImportStatus.COMPLETED_WITH_WARNINGS

            await log_audit(
                self.db, self.user_id, "IMPORT", "AttendanceImport",
                str(import_session.id),
                f"Imported attendance summary PDF: {preview_data['filename']} "
                f"({imported} summary records, {errors} errors)",
            )

            await self.db.commit()

            return {
                "import_id": import_session.id,
                "imported": imported,
                "updated": updated,
                "skipped": skipped,
                "duplicates": skipped + updated,
                "errors": errors,
                "total_in_file": len(preview_data["records"]),
                "status": import_session.status.value,
                "date_range_start": preview_data.get("date_range_start"),
                "date_range_end": preview_data.get("date_range_end"),
            }

        processed_emp_dates: set[tuple[int, date]] = set()

        for record_data in preview_data["records"]:
            attendance_record: Optional[Attendance] = None
            emp_code = record_data.get("employee_code")
            dept_name = record_data.get("department_name", "")
            att_date_str = record_data.get("attendance_date")

            if not att_date_str or not emp_code:
                errors += 1
                continue

            att_date = date.fromisoformat(att_date_str)

            # Resolve employee
            emp = employee_map.get(emp_code)
            if not emp:
                # Try manual mapping
                manual_id = employee_mappings.get(emp_code)
                if manual_id:
                    result = await self.db.execute(select(Employee).where(Employee.id == int(manual_id)))
                    emp = result.scalar_one_or_none()

            if not emp:
                # Log as import record with error
                ir = AttendanceImportRecord(
                    import_id=import_session.id,
                    raw_date=att_date_str,
                    raw_department=dept_name,
                    raw_employee_code=emp_code,
                    raw_employee_name=record_data.get("employee_name"),
                    raw_shift=record_data.get("shift_code"),
                    raw_in_time=record_data.get("in_time"),
                    raw_out_time=record_data.get("out_time"),
                    raw_work_duration=record_data.get("work_duration"),
                    raw_ot=record_data.get("ot"),
                    raw_status=record_data.get("status"),
                    has_error=True,
                    error_message=f"Unknown employee code: {emp_code}",
                )
                self.db.add(ir)
                errors += 1
                continue

            # Skip attendance rows before employee's joining date
            if emp.joining_date and att_date < emp.joining_date:
                skipped += 1
                ir = AttendanceImportRecord(
                    import_id=import_session.id,
                    raw_date=att_date_str,
                    raw_department=dept_name,
                    raw_employee_code=emp_code,
                    raw_employee_name=record_data.get("employee_name"),
                    raw_shift=record_data.get("shift_code"),
                    raw_in_time=record_data.get("in_time"),
                    raw_out_time=record_data.get("out_time"),
                    raw_work_duration=record_data.get("work_duration"),
                    raw_ot=record_data.get("ot"),
                    raw_status=record_data.get("status"),
                    mapped_employee_id=emp.id,
                    mapped_department_id=None,
                    has_warning=True,
                    warning_message=f"Before joining date ({emp.joining_date})",
                )
                self.db.add(ir)
                continue

            # Resolve department
            dept_key = dept_name.upper().strip()
            dept = dept_map.get(dept_key)
            dept_id = dept.id if dept else None
            if not dept:
                manual_dept_id = department_mappings.get(dept_name)
                if manual_dept_id:
                    dept_id = int(manual_dept_id)

            # Check for existing record in DB or in-memory batch
            existing_result = await self.db.execute(
                select(Attendance).where(
                    Attendance.employee_id == emp.id,
                    Attendance.attendance_date == att_date,
                )
            )
            existing = existing_result.scalar_one_or_none()
            is_in_batch_dup = (emp.id, att_date) in processed_emp_dates

            if (existing or is_in_batch_dup) and is_skip:
                skipped += 1
                ir = AttendanceImportRecord(
                    import_id=import_session.id,
                    raw_date=att_date_str,
                    raw_department=dept_name,
                    raw_employee_code=emp_code,
                    raw_employee_name=record_data.get("employee_name"),
                    raw_shift=record_data.get("shift_code"),
                    raw_in_time=record_data.get("in_time"),
                    raw_out_time=record_data.get("out_time"),
                    raw_work_duration=record_data.get("work_duration"),
                    raw_ot=record_data.get("ot"),
                    raw_status=record_data.get("status"),
                    mapped_employee_id=emp.id,
                    mapped_department_id=dept_id,
                    is_duplicate=True,
                    attendance_id=existing.id if existing else None,
                )
                self.db.add(ir)
                continue

            processed_emp_dates.add((emp.id, att_date))

            # Build datetimes
            is_overnight = record_data.get("is_overnight", False)
            in_dt = _parse_time_to_datetime(att_date, record_data.get("in_time"), False)
            out_dt = _parse_time_to_datetime(att_date, record_data.get("out_time"), is_overnight)

            # Parse minutes from duration strings (HH:MM)
            def parse_mins(s: Optional[str]) -> Optional[int]:
                if not s or s == "00:00":
                    return None
                try:
                    h, m = map(int, s.strip().split(":"))
                    return h * 60 + m
                except (ValueError, AttributeError):
                    return None

            status_val = record_data.get("status")
            try:
                att_status = AttendanceStatus(status_val) if status_val else AttendanceStatus.NO_DATA
            except ValueError:
                if status_val in ["A", "ABSENT"]:
                    att_status = AttendanceStatus.ABSENT
                elif status_val in ["P", "PRESENT"]:
                    att_status = AttendanceStatus.PRESENT
                elif status_val in ["NO_DATA", None, ""]:
                    att_status = AttendanceStatus.NO_DATA
                else:
                    att_status = AttendanceStatus.NO_DATA

            # Guard: A row with status = PRESENT and both in_time and out_time null should be impossible unless source status is explicit P
            if att_status == AttendanceStatus.PRESENT and not in_dt and not out_dt and not record_data.get("in_time") and record_data.get("status") not in ["P", "PRESENT"]:
                att_status = AttendanceStatus.NO_DATA

            # Determine shift expected duration and rule: prefer day's shift code from PDF first
            shift_code_str = (record_data.get("shift_code") or "").upper().strip()
            shift_obj = None
            if shift_code_str and shift_code_str not in ["NS", "SAM"]:
                shift_obj = shift_map.get(shift_code_str)
            if not shift_obj and emp and emp.shift:
                shift_obj = emp.shift

            pref_window = alias_target_window_map.get(shift_code_str)

            # Derive work duration, OT, and lateness from punches and shift rule
            from app.utils.shift_utils import evaluate_shift_punch
            shift_eval = evaluate_shift_punch(shift_obj, in_dt, preferred_window=pref_window)
            is_late = shift_eval["is_late"]
            late_minutes = shift_eval["late_minutes"]
            expected_shift_mins = shift_eval["expected_working_minutes"]

            warnings_list = list(record_data.get("warnings") or [])

            if in_dt and out_dt and att_status in [AttendanceStatus.PRESENT, AttendanceStatus.PRESENT_OVERNIGHT]:
                # Actual punch duration
                if out_dt < in_dt or is_overnight:
                    actual_out = out_dt if out_dt > in_dt else out_dt + timedelta(days=1)
                    dur_mins = int((actual_out - in_dt).total_seconds() / 60)
                else:
                    dur_mins = int((out_dt - in_dt).total_seconds() / 60)

                # Guard: Zero-length punches (e.g. 08:43 -> 08:43) are not payable days
                if dur_mins <= 0:
                    work_mins_effective = 0
                    ot_mins_effective = 0
                    att_status = AttendanceStatus.PRESENT_INCOMPLETE
                    if "SUSPECT_PUNCH" not in warnings_list:
                        warnings_list.append("SUSPECT_PUNCH")
                else:
                    work_mins_effective = min(dur_mins, expected_shift_mins)
                    ot_mins_effective = max(0, dur_mins - expected_shift_mins)
            else:
                work_mins_effective = 0
                ot_mins_effective = 0
                dur_mins = 0

            if existing:
                # Reconcile & update existing single row (Monthly Status Report supersedes Daily report)
                existing.source_import_id = import_session.id
                existing.source_department_name = dept_name
                existing.source_shift_code = record_data.get("shift_code")
                existing.shift_id = shift_obj.id if shift_obj else None
                existing.source_in_time = record_data.get("in_time")
                existing.source_out_time = record_data.get("out_time")
                existing.source_work_duration = record_data.get("work_duration")
                existing.source_ot = record_data.get("ot")
                existing.source_status = record_data.get("status")
                existing.check_in_datetime = in_dt
                existing.check_out_datetime = out_dt
                existing.work_minutes = work_mins_effective
                existing.ot_minutes = ot_mins_effective
                existing.status = att_status
                existing.is_late = is_late
                existing.late_minutes = late_minutes
                existing.is_corrected = False
                existing.has_exception = bool(warnings_list or record_data.get("errors"))
                attendance_record = existing
                updated += 1
            else:
                try:
                    async with self.db.begin_nested():
                        attendance_record = Attendance(
                            employee_id=emp.id,
                            attendance_date=att_date,
                            source_import_id=import_session.id,
                            source_department_name=dept_name,
                            source_shift_code=record_data.get("shift_code"),
                            shift_id=shift_obj.id if shift_obj else None,
                            source_in_time=record_data.get("in_time"),
                            source_out_time=record_data.get("out_time"),
                            source_work_duration=record_data.get("work_duration"),
                            source_ot=record_data.get("ot"),
                            source_status=record_data.get("status"),
                            check_in_datetime=in_dt,
                            check_out_datetime=out_dt,
                            work_minutes=work_mins_effective,
                            ot_minutes=ot_mins_effective,
                            status=att_status,
                            is_late=is_late,
                            late_minutes=late_minutes,
                            department_id=dept_id,
                            has_exception=bool(warnings_list or record_data.get("errors")),
                        )
                        self.db.add(attendance_record)
                        await self.db.flush()
                        imported += 1
                except IntegrityError:
                    skipped += 1
                    ir = AttendanceImportRecord(
                        import_id=import_session.id,
                        raw_date=att_date_str,
                        raw_department=dept_name,
                        raw_employee_code=emp_code,
                        raw_employee_name=record_data.get("employee_name"),
                        raw_shift=record_data.get("shift_code"),
                        raw_in_time=record_data.get("in_time"),
                        raw_out_time=record_data.get("out_time"),
                        raw_work_duration=record_data.get("work_duration"),
                        raw_ot=record_data.get("ot"),
                        raw_status=record_data.get("status"),
                        mapped_employee_id=emp.id,
                        mapped_department_id=dept_id,
                        is_duplicate=True,
                    )
                    self.db.add(ir)
                    continue

            # Create or update exception records idempotently
            is_partial = record_data.get("is_partial") or "PARTIAL_DAY" in warnings_list
            if not is_partial and att_status == AttendanceStatus.PRESENT_INCOMPLETE and "NO_OUT_PUNCH" not in warnings_list:
                warnings_list.append("NO_OUT_PUNCH")

            # Fetch existing exceptions for this employee on this date
            existing_excs_res = await self.db.execute(
                select(AttendanceException).where(
                    AttendanceException.employee_id == emp.id,
                    AttendanceException.exception_date == att_date,
                )
            )
            existing_excs = existing_excs_res.scalars().all()
            existing_excs_by_type = {e.exception_type: e for e in existing_excs}

            active_warning_types = set()
            for warning in warnings_list:
                if warning == "PARTIAL_DAY":
                    continue
                active_warning_types.add(warning)
                if warning == "NO_OUT_PUNCH":
                    reason_str = "Present (No OutPunch)"
                elif warning == "SUSPECT_PUNCH" and dur_mins <= 0:
                    reason_str = "Zero work duration (in = out)"
                elif warning == "SUSPECT_PUNCH" and dur_mins > 840:
                    reason_str = "Suspect post-midnight punch (>14h duration)"
                else:
                    reason_str = f"Warning during import: {warning}"

                orig_val = json.dumps({
                    "in": record_data.get("in_time"),
                    "out": record_data.get("out_time"),
                    "work": record_data.get("work_duration"),
                })

                if warning in existing_excs_by_type:
                    # Update existing exception idempotently
                    exc = existing_excs_by_type[warning]
                    exc.attendance_id = attendance_record.id
                    exc.import_id = import_session.id
                    exc.reason = reason_str
                    exc.original_value = orig_val
                else:
                    exc = AttendanceException(
                        attendance_id=attendance_record.id,
                        import_id=import_session.id,
                        employee_id=emp.id,
                        exception_date=att_date,
                        exception_type=warning,
                        reason=reason_str,
                        original_value=orig_val,
                        severity=ExceptionSeverity.WARNING,
                    )
                    self.db.add(exc)

            # If an unreviewed PENDING exception is no longer active on re-import, remove it
            for old_exc in existing_excs:
                if old_exc.exception_type not in active_warning_types and old_exc.review_status == ExceptionReviewStatus.PENDING:
                    await self.db.delete(old_exc)

            # Log import record
            ir = AttendanceImportRecord(
                import_id=import_session.id,
                raw_date=att_date_str,
                raw_department=dept_name,
                raw_employee_code=emp_code,
                raw_employee_name=record_data.get("employee_name"),
                raw_shift=record_data.get("shift_code"),
                raw_in_time=record_data.get("in_time"),
                raw_out_time=record_data.get("out_time"),
                raw_work_duration=record_data.get("work_duration"),
                raw_ot=record_data.get("ot"),
                raw_status=record_data.get("status"),
                mapped_employee_id=emp.id,
                mapped_department_id=dept_id,
                is_duplicate=bool(existing is not None or is_in_batch_dup),
                has_warning=bool(record_data.get("warnings")),
                warning_message=",".join(record_data.get("warnings") or []),
                attendance_id=getattr(attendance_record, "id", None),
            )
            self.db.add(ir)

        # Update import session stats
        import_session.report_type = preview_data.get("report_type")
        import_session.company_name = preview_data.get("company_name")
        import_session.records_imported = imported
        import_session.records_duplicate = skipped + updated
        import_session.records_error = errors
        import_session.total_records_in_pdf = len(preview_data["records"])
        import_session.unknown_employee_codes = json.dumps(preview_data.get("unknown_employee_codes", []))
        import_session.unknown_department_names = json.dumps(preview_data.get("unknown_department_names", []))
        import_session.unmatched_row_count = errors + (len(preview_data.get("unknown_employee_codes", [])) * 25 if preview_data.get("unknown_employee_codes") else 0)
        import_session.unknown_employees = len(preview_data.get("unknown_employee_codes", []))
        import_session.unknown_departments = len(preview_data.get("unknown_department_names", []))
        import_session.status = ImportStatus.COMPLETED if errors == 0 else ImportStatus.COMPLETED_WITH_WARNINGS

        await log_audit(
            self.db, self.user_id, "IMPORT", "AttendanceImport",
            str(import_session.id),
            f"Imported attendance PDF: {preview_data['filename']} "
            f"({imported} new records, {updated} updated, {skipped} skipped, {errors} errors)",
        )

        # Persist monthly aggregates if present
        monthly_aggs = preview_data.get("monthly_aggregates", [])
        if monthly_aggs:
            from app.models.attendance import MonthlyAttendanceAggregate
            for agg_data in monthly_aggs:
                emp_code = str(agg_data.get("employee_code", "")).strip()
                emp = employee_map.get(emp_code)
                if not emp:
                    # Try manual mapping
                    if employee_mappings and emp_code in employee_mappings:
                        mapped_id = int(employee_mappings[emp_code])
                        emp_result = await self.db.execute(
                            select(Employee).where(Employee.id == mapped_id)
                        )
                        emp = emp_result.scalar_one_or_none()
                
                # Determine year/month from import date range
                year = preview_data.get("date_range_start")
                month_val = None
                if year:
                    from datetime import date as date_type
                    if isinstance(year, str):
                        dt = date_type.fromisoformat(year)
                    else:
                        dt = year
                    year = dt.year
                    month_val = dt.month
                
                if year and month_val:
                    # Upsert: delete existing for same employee/year/month, then insert
                    if emp:
                        await self.db.execute(
                            delete(MonthlyAttendanceAggregate).where(
                                MonthlyAttendanceAggregate.employee_id == emp.id,
                                MonthlyAttendanceAggregate.year == year,
                                MonthlyAttendanceAggregate.month == month_val,
                            )
                        )
                    
                    norm_dept_name = emp.department.name if emp and emp.department else agg_data.get("department_name", "")
                    if norm_dept_name and norm_dept_name.upper() in ("DR", "DR."):
                        norm_dept_name = "DOCTOR"

                    new_agg = MonthlyAttendanceAggregate(
                        import_id=import_session.id,
                        employee_id=emp.id if emp else None,
                        employee_code=emp_code,
                        employee_name=agg_data.get("employee_name", ""),
                        department_name=norm_dept_name,
                        company_name=agg_data.get("company_name", ""),
                        year=year,
                        month=month_val,
                        total_work_duration=agg_data.get("total_work_duration"),
                        total_ot=agg_data.get("total_ot"),
                        present_count=agg_data.get("present_count", 0),
                        absent_count=agg_data.get("absent_count", 0),
                        weekly_off_count=agg_data.get("weekly_off_count", 0),
                        holidays_count=agg_data.get("holidays_count", 0),
                        leaves_taken=agg_data.get("leaves_taken", 0),
                        late_by_hrs=agg_data.get("late_by_hrs"),
                        late_by_days=agg_data.get("late_by_days", 0),
                        late_days_device=agg_data.get("late_days_device", 0),
                        late_days_qualifying=agg_data.get("late_days_qualifying", 0),
                        lop_days=agg_data.get("lop_days", 0),
                        early_by_hrs=agg_data.get("early_by_hrs"),
                        early_going_by_days=agg_data.get("early_going_by_days", 0),
                        total_duration_with_ot=agg_data.get("total_duration_with_ot"),
                        average_working_hrs=agg_data.get("average_working_hrs"),
                        has_zero_punches=agg_data.get("has_zero_punches", False),
                    )
                    self.db.add(new_agg)

        await self.db.commit()

        return {
            "import_id": import_session.id,
            "imported": imported,
            "skipped": skipped,
            "updated": updated,
            "duplicates": skipped + updated,
            "errors": errors,
            "status": import_session.status.value,
        }
