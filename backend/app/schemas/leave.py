from datetime import date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class LeaveTypeBase(BaseModel):
    name: str
    code: str
    days_per_year: float
    is_paid: bool = True
    is_active: bool = True

class LeaveTypeCreate(LeaveTypeBase):
    pass

class LeaveTypeResponse(LeaveTypeBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class LeaveRequestBase(BaseModel):
    employee_id: int
    leave_type_id: int
    start_date: date
    end_date: date
    reason: str
    half_day: bool = False

class LeaveRequestCreate(LeaveRequestBase):
    pass

class LeaveRequestResponse(LeaveRequestBase):
    id: int
    status: str
    applied_on: date
    approved_by: Optional[int] = None
    approved_on: Optional[date] = None
    rejection_reason: Optional[str] = None
    employee_name: Optional[str] = None
    leave_type_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class LeaveApprovalRequest(BaseModel):
    status: str # APPROVED, REJECTED, CANCELLED
    reason: Optional[str] = None

class LeaveBalanceResponse(BaseModel):
    employee_id: int
    leave_type_id: int
    leave_type_name: str
    year: int
    allocated_days: float
    used_days: float
    balance_days: float

    model_config = ConfigDict(from_attributes=True)
