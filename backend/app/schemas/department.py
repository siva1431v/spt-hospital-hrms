from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class DepartmentBase(BaseModel):
    name: str
    code: Optional[str] = None
    is_active: bool = True

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    is_active: Optional[bool] = None

class DepartmentResponse(DepartmentBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

class DesignationBase(BaseModel):
    name: str
    department_id: int
    is_active: bool = True

class DesignationCreate(DesignationBase):
    pass

class DesignationUpdate(BaseModel):
    name: Optional[str] = None
    department_id: Optional[int] = None
    is_active: Optional[bool] = None

class DesignationResponse(DesignationBase):
    id: int
    department_name: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)
