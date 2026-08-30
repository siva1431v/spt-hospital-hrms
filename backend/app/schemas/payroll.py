from datetime import date
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict

class SalaryComponentBase(BaseModel):
    name: str
    code: str
    type: str # EARNING, DEDUCTION
    is_taxable: bool = True
    is_active: bool = True

class SalaryComponentCreate(SalaryComponentBase):
    pass

class SalaryComponentResponse(SalaryComponentBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class SalaryStructureItemCreate(BaseModel):
    component_id: int
    amount: float
    type: str

class SalaryStructureItemResponse(BaseModel):
    id: int
    component_id: int
    component_name: str
    type: str
    amount: float

    model_config = ConfigDict(from_attributes=True)

class SalaryStructureCreate(BaseModel):
    employee_id: int
    basic_salary: float
    ot_rate: float = 0.0
    items: List[SalaryStructureItemCreate] = []

class SalaryStructureResponse(BaseModel):
    id: int
    employee_id: int
    basic_salary: float
    ot_rate: float
    effective_from: date
    is_active: bool
    items: List[SalaryStructureItemResponse]

    model_config = ConfigDict(from_attributes=True)

class PayrollPeriodBase(BaseModel):
    year: int
    month: int
    working_days: float

class PayrollPeriodCreate(PayrollPeriodBase):
    pass

class PayrollPeriodResponse(PayrollPeriodBase):
    id: int
    status: str # DRAFT, GENERATED, FINALIZED, PAID
    created_at: date
    processed_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)

class PayrollCalculationRequest(PayrollPeriodBase):
    pass

class PayrollCalculateMonthRequest(BaseModel):
    year: int
    month: int
    working_days: Optional[int] = None

class PayrollRecordItemResponse(BaseModel):
    id: int
    component_id: Optional[int]
    component_name: str
    type: str
    amount: float

    model_config = ConfigDict(from_attributes=True)

class PayrollRecordUpdate(BaseModel):
    present_days: Optional[float] = None
    half_days: Optional[float] = None
    leave_days: Optional[float] = None
    off_duty_days: Optional[float] = None
    qualifying_late_days: Optional[int] = None
    loss_of_pay_days: Optional[float] = None
    lop_days: Optional[float] = None
    collection: Optional[float] = None
    is_manual_override: Optional[bool] = None

class PayrollRecordResponse(BaseModel):
    id: int
    payroll_period_id: Optional[int] = None
    employee_id: int
    employee_name: Optional[str] = None
    employee_code: Optional[str] = None
    biometric_code: Optional[str] = None
    department: Optional[str] = None
    basic_salary: float = 0.0
    present_days: float = 0.0
    absent_days: float = 0.0
    half_days: float = 0.0
    leave_days: float = 0.0
    paid_leave_days: float = 0.0
    off_duty_days: float = 0.0
    qualifying_late_days: int = 0
    loss_of_pay_days: float = 0.0
    lop_days: float = 0.0
    payable_days: float = 0.0
    salary_part: float = 0.0
    collection: float = 0.0
    lifetime_collection: float = 0.0
    gross_salary: float = 0.0
    lop_deduction: float = 0.0
    security_fund_deduction: float = 0.0
    total_deductions: float = 0.0
    total_salary: float = 0.0
    net_salary: float = 0.0
    is_manual_override: bool = False
    items: List[PayrollRecordItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
