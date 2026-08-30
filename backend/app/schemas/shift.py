from datetime import time
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

class ShiftBase(BaseModel):
    name: str
    code: str
    start_time: time
    end_time: time
    grace_period_minutes: int = 5
    expected_working_minutes: int = 480
    ot_threshold_minutes: int = 60
    is_overnight: bool = False
    is_split: bool = False
    start_time_2: Optional[time] = None
    end_time_2: Optional[time] = None
    is_overnight_2: bool = False
    is_active: bool = True

class ShiftCreate(ShiftBase):
    pass

class ShiftUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    grace_period_minutes: Optional[int] = None
    expected_working_minutes: Optional[int] = None
    ot_threshold_minutes: Optional[int] = None
    is_overnight: Optional[bool] = None
    is_split: Optional[bool] = None
    start_time_2: Optional[time] = None
    end_time_2: Optional[time] = None
    is_overnight_2: Optional[bool] = None
    is_active: Optional[bool] = None

class ShiftResponse(ShiftBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
