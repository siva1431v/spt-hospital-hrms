import re
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


def _validate_indian_phone(v: Optional[str]) -> Optional[str]:
    if not v or not v.strip():
        return None
    cleaned = re.sub(r'[\s\-]', '', v.strip())
    if not re.match(r'^(?:\+91|91|0)?[6-9]\d{9}$', cleaned):
        raise ValueError('Invalid Indian mobile number. Must be 10 digits starting with 6-9, optionally prefixed with +91 or 91.')
    return v.strip()


class EmployeeCreate(BaseModel):
    """Schema for creating a new employee. Only first_name and employee_id are required."""
    # Required
    employee_id: str
    first_name: str

    # Optional — can be filled in later
    last_name: Optional[str] = None
    biometric_code: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    shift_id: Optional[int] = None
    joining_date: Optional[date] = None
    employment_type: Optional[str] = "FULL_TIME"
    basic_salary: Optional[float] = Field(None, ge=0)
    salary_verified: Optional[bool] = None
    security_fund_deduction: Optional[float] = Field(0.0, ge=0)
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    pan_number: Optional[str] = None
    pf_number: Optional[str] = None
    esi_number: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_indian_phone(v)


class EmployeeUpdate(BaseModel):
    """Schema for updating an employee. All fields optional."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    biometric_code: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    department_id: Optional[int] = None
    designation_id: Optional[int] = None
    shift_id: Optional[int] = None
    joining_date: Optional[date] = None
    employment_type: Optional[str] = None
    is_active: Optional[bool] = None
    basic_salary: Optional[float] = Field(None, ge=0)
    salary_verified: Optional[bool] = None
    security_fund_deduction: Optional[float] = Field(None, ge=0)
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_ifsc: Optional[str] = None
    pan_number: Optional[str] = None
    pf_number: Optional[str] = None
    esi_number: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_indian_phone(v)


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: str
    biometric_code: Optional[str]
    first_name: str
    last_name: Optional[str] = None
    full_name: str
    gender: Optional[str]
    date_of_birth: Optional[date]
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    department_id: Optional[int]
    department_name: Optional[str] = None
    designation_id: Optional[int]
    designation_name: Optional[str] = None
    shift_id: Optional[int]
    shift_code: Optional[str] = None
    shift_name: Optional[str] = None
    joining_date: Optional[date]
    employment_type: str
    is_active: bool
    basic_salary: Optional[float]
    salary_verified: bool = False
    security_fund_deduction: Optional[float] = 0.0
    bank_name: Optional[str]
    bank_account_number: Optional[str]
    bank_ifsc: Optional[str]
    pan_number: Optional[str]
    pf_number: Optional[str]
    esi_number: Optional[str]
    created_at: datetime
    updated_at: datetime


class BulkSetSavingsRequest(BaseModel):
    employee_ids: list[int]
    amount: float = Field(0.0, ge=0)


class SavingsFundTransactionCreate(BaseModel):
    transaction_type: str = Field(..., description="DEPOSIT, WITHDRAWAL, REFUND, SETTLEMENT")
    amount: float = Field(..., gt=0, description="Transaction amount (must be positive)")
    notes: Optional[str] = Field(None, max_length=500)


class SavingsFundTransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    transaction_type: str
    amount: float
    notes: Optional[str] = None
    created_at: datetime


class EmployeeListResponse(BaseModel):
    items: list[EmployeeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
