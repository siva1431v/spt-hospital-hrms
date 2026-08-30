from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class DashboardStats(BaseModel):
    total_employees: int
    present_today: int
    absent_today: int
    incomplete: int
    late: int
    on_leave: int
    ot_hours_today: float
    monthly_payroll_amount: float

class AttendanceTrendPoint(BaseModel):
    date: date
    present: int
    absent: int
    incomplete: int

class DeptAttendancePoint(BaseModel):
    department: str
    present_count: int
    absent_count: int

class RecentActivity(BaseModel):
    id: int
    action: str
    description: str
    user_name: Optional[str] = None
    created_at: datetime
    entity_type: str

    model_config = ConfigDict(from_attributes=True)
