"""
SPT Hospital HRMS — Shift Evaluation Utilities
Evaluates check-in time against assigned shift windows (including split shifts).
"""
from datetime import time, datetime
from typing import Optional, Dict, Any
from app.models.shift import Shift


def evaluate_shift_punch(
    shift: Optional[Shift],
    check_in_dt: Optional[datetime],
    preferred_window: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Evaluates check-in datetime against assigned Shift.
    For split shifts (is_split=True):
    - If preferred_window is provided (1 or 2, e.g. from HKN/SNS device code aliases), it selects that window.
    - Otherwise, picks the window whose start is nearest to the check-in time.

    Returns:
      {
         "matched_window": 1 or 2,
         "shift_start": time,
         "shift_end": time,
         "is_overnight": bool,
         "is_late": bool,
         "late_minutes": int,
         "expected_working_minutes": int,
      }
    """
    if not shift:
        return {
            "matched_window": 1,
            "shift_start": None,
            "shift_end": None,
            "is_overnight": False,
            "is_late": False,
            "late_minutes": 0,
            "expected_working_minutes": 480,
        }

    # Window 1 defaults
    start_t = shift.start_time
    end_t = shift.end_time
    is_overnight = shift.is_overnight
    matched_window = 1

    # Default expected working minutes for window 1
    w1_start_mins = shift.start_time.hour * 60 + shift.start_time.minute
    w1_end_mins = shift.end_time.hour * 60 + shift.end_time.minute
    if is_overnight or w1_end_mins <= w1_start_mins:
        w1_expected_mins = (w1_end_mins + 1440 - w1_start_mins)
    else:
        w1_expected_mins = (w1_end_mins - w1_start_mins)
    
    # Use shift.expected_working_minutes if set, otherwise computed duration
    expected_working_minutes = shift.expected_working_minutes or w1_expected_mins

    if shift.is_split and shift.start_time_2 and shift.end_time_2:
        w2_start_mins = shift.start_time_2.hour * 60 + shift.start_time_2.minute
        w2_end_mins = shift.end_time_2.hour * 60 + shift.end_time_2.minute
        if shift.is_overnight_2 or w2_end_mins <= w2_start_mins:
            w2_expected_mins = (w2_end_mins + 1440 - w2_start_mins)
        else:
            w2_expected_mins = (w2_end_mins - w2_start_mins)

        if preferred_window == 2:
            matched_window = 2
            start_t = shift.start_time_2
            end_t = shift.end_time_2
            is_overnight = shift.is_overnight_2
            expected_working_minutes = w2_expected_mins
        elif preferred_window == 1:
            matched_window = 1
            start_t = shift.start_time
            end_t = shift.end_time
            is_overnight = shift.is_overnight
            expected_working_minutes = shift.expected_working_minutes or w1_expected_mins
        elif check_in_dt:
            in_time = check_in_dt.time()
            in_mins = in_time.hour * 60 + in_time.minute

            def minute_distance(m1: int, m2: int) -> int:
                d = abs(m1 - m2)
                return min(d, 1440 - d)

            diff1 = minute_distance(in_mins, w1_start_mins)
            diff2 = minute_distance(in_mins, w2_start_mins)
            if diff2 < diff1:
                matched_window = 2
                start_t = shift.start_time_2
                end_t = shift.end_time_2
                is_overnight = shift.is_overnight_2
                expected_working_minutes = w2_expected_mins

    if not check_in_dt:
        return {
            "matched_window": matched_window,
            "shift_start": start_t,
            "shift_end": end_t,
            "is_overnight": is_overnight,
            "is_late": False,
            "late_minutes": 0,
            "expected_working_minutes": expected_working_minutes,
        }

    in_time = check_in_dt.time()
    in_mins = in_time.hour * 60 + in_time.minute
    start_mins = start_t.hour * 60 + start_t.minute
    grace_mins = shift.grace_period_minutes if shift.grace_period_minutes is not None else 5

    # Circular delay in minutes from shift start
    delay_mins = (in_mins - start_mins) % 1440

    is_late = False
    late_minutes = 0

    # If punch arrived within 6 hours (360 mins) after scheduled start
    if 0 < delay_mins <= 360:
        if delay_mins > grace_mins:
            is_late = True
            late_minutes = delay_mins

    return {
        "matched_window": matched_window,
        "shift_start": start_t,
        "shift_end": end_t,
        "is_overnight": is_overnight,
        "is_late": is_late,
        "late_minutes": late_minutes,
        "expected_working_minutes": expected_working_minutes,
    }
