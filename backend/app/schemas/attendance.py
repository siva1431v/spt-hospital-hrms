from datetime import date, time, datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

class AttendanceResponse(BaseModel):
    id: int
    employee_id: int
    attendance_date: date
    shift_id: Optional[int] = None
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    status: str
    working_minutes: int = 0
    ot_minutes: int = 0
    late_minutes: int = 0
    is_corrected: bool = False
    notes: Optional[str] = None
    employee_name: Optional[str] = None
    department_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class AttendanceLeaveReclassifyRequest(BaseModel):
    attendance_id: Optional[int] = None
    employee_id: Optional[int] = None
    attendance_date: Optional[date] = None
    action: str = "MARK_LEAVE" # MARK_LEAVE or REVERT_ABSENT
    leave_type_id: Optional[int] = None
    leave_type_code: Optional[str] = None
    reason: Optional[str] = None

class AttendanceBulkLeaveReclassifyRequest(BaseModel):
    employee_id: Optional[int] = None
    attendance_ids: Optional[List[int]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    action: str = "MARK_LEAVE" # MARK_LEAVE or REVERT_ABSENT
    leave_type_id: Optional[int] = None
    leave_type_code: Optional[str] = None
    reason: Optional[str] = None

class AttendanceCorrectionCreate(BaseModel):
    corrected_in: Optional[datetime] = None
    corrected_out: Optional[datetime] = None
    reason: str

class MonthlyAttendanceSummary(BaseModel):
    employee_id: int
    employee_name: str
    total_present: float
    total_absent: float
    total_leaves: float
    total_late: int
    total_incomplete: int
    total_working_minutes: int
    total_ot_minutes: int
    records: List[AttendanceResponse]

    model_config = ConfigDict(from_attributes=True)

class ImportPreviewRecord(BaseModel):
    employee_code: Optional[str] = None
    employee_name: Optional[str] = None
    attendance_date: Optional[date] = None
    in_time: Optional[datetime] = None
    out_time: Optional[datetime] = None
    shift_code: Optional[str] = None
    status: str = "PENDING"
    warnings: List[str] = []
    raw_data: Dict[str, Any] = {}

class AttendanceImportPreviewResponse(BaseModel):
    total_records: int
    valid_records: int
    warning_records: int
    error_records: int
    preview_records: List[ImportPreviewRecord]
    import_session_token: str

class AttendanceExceptionReviewRequest(BaseModel):
    status: str
    notes: Optional[str] = None

class AttendanceExceptionBulkReviewRequest(BaseModel):
    exception_ids: List[int]
    status: str
    notes: Optional[str] = None

class AttendanceExceptionResponse(BaseModel):
    id: int
    import_id: int
    employee_id: Optional[int] = None
    employee_code: Optional[str] = None
    attendance_date: date
    exception_type: str
    details: Dict[str, Any]
    review_status: str
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class AttendanceImportResponse(BaseModel):
    id: int
    filename: str
    uploaded_by_id: int
    imported_at: datetime
    report_type: Optional[str] = None
    company_name: Optional[str] = None
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    total_records_in_pdf: int = 0
    records_imported: int = 0
    records_duplicate: int = 0
    records_error: int = 0
    unknown_employees: int = 0
    unknown_employee_codes: Optional[str] = None
    unknown_department_names: Optional[str] = None
    unmatched_row_count: int = 0
    status: str

    model_config = ConfigDict(from_attributes=True)
