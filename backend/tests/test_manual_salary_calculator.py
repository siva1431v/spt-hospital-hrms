"""
SPT Hospital HRMS — Unit Tests for Live Manual Salary Calculator Formula
Validates all reverse-engineered test cases from the hospital's live calculator.
"""
import calendar
import pytest


def calculate_manual_salary(
    base_salary: float,
    year: int,
    month: int,
    present_days: float,
    half_days: float = 0.0,
    leave_days: float = 0.0,
    off_duty_days: float = 0.0,
    collection: float = 0.0,
) -> dict:
    """
    Formula reverse-engineered from live manual salary calculator:
      daysInMonth = calendar days in selected month (28 / 29 / 30 / 31)
      perDay      = base_salary / daysInMonth
      payableDays = min(present_days, daysInMonth) + (half_days * 0.5) + min(leave_days, 3) + off_duty_days
      salaryPart  = min(payableDays * perDay, base_salary)
      totalSalary = salaryPart + collection
    """
    days_in_month = calendar.monthrange(year, month)[1]
    per_day = base_salary / days_in_month

    effective_present = min(present_days, days_in_month)
    effective_leave = min(leave_days, 3.0)

    payable_days = round(effective_present + (half_days * 0.5) + effective_leave + off_duty_days, 2)
    salary_part = min(payable_days * per_day, base_salary)
    salary_part_rounded = round(salary_part, 2)
    total_salary = round(salary_part_rounded + collection, 2)

    return {
        "days_in_month": days_in_month,
        "per_day": round(per_day, 4),
        "payable_days": payable_days,
        "salary_part": salary_part_rounded,
        "collection": collection,
        "total_salary": total_salary,
    }


# Test Cases from Live Manual Calculator (Base Salary ₹20,000)
TEST_CASES = [
    # (month, days, present, half, leave, off_duty, collection, expected_payable, expected_total)
    (8, 31, 30, 0, 0, 0, 0, 30.0, 19354.84),
    (8, 31, 20, 0, 0, 0, 0, 20.0, 12903.23),
    (8, 31, 20, 2, 0, 0, 0, 21.0, 13548.39),
    (8, 31, 20, 1, 0, 0, 0, 20.5, 13225.81),
    (8, 31, 20, 0, 3, 0, 0, 23.0, 14838.71),
    (8, 31, 20, 0, 5, 0, 0, 23.0, 14838.71),
    (8, 31, 20, 0, 0, 4, 0, 24.0, 15483.87),
    (8, 31, 20, 0, 0, 0, 1000, 20.0, 13903.23),
    (8, 31, 31, 0, 0, 0, 0, 31.0, 20000.00),
    (8, 31, 40, 0, 0, 0, 0, 31.0, 20000.00),
    (8, 31, 25, 3, 3, 2, 500, 31.5, 20500.00),
    (8, 31, 0, 0, 3, 0, 0, 3.0, 1935.48),  # 3 * 20000 / 31 = 1935.48
    (8, 31, 0, 0, 0, 0, 2500, 0.0, 2500.00),
    (9, 30, 30, 0, 0, 0, 0, 30.0, 20000.00),
    (9, 30, 15, 0, 0, 0, 0, 15.0, 10000.00),
    (9, 30, 31, 0, 0, 0, 0, 30.0, 20000.00),
]


@pytest.mark.parametrize(
    "month,days,present,half,leave,off_duty,collection,expected_payable,expected_total",
    TEST_CASES,
)
def test_manual_calculator_test_cases(
    month, days, present, half, leave, off_duty, collection, expected_payable, expected_total
):
    res = calculate_manual_salary(
        base_salary=20000.0,
        year=2026,
        month=month,
        present_days=present,
        half_days=half,
        leave_days=leave,
        off_duty_days=off_duty,
        collection=collection,
    )
    assert res["days_in_month"] == days
    assert res["payable_days"] == expected_payable
    assert res["total_salary"] == expected_total


def test_february_leap_year():
    """Verify February leap year (29 days e.g., 2028) and non-leap year (28 days e.g., 2027)."""
    # 2028 is a leap year (29 days)
    res_leap = calculate_manual_salary(20000.0, 2028, 2, present_days=29)
    assert res_leap["days_in_month"] == 29
    assert res_leap["payable_days"] == 29.0
    assert res_leap["total_salary"] == 20000.0

    res_leap_half = calculate_manual_salary(20000.0, 2028, 2, present_days=14.5)
    assert res_leap_half["payable_days"] == 14.5
    assert res_leap_half["total_salary"] == 10000.0

    # 2027 is non-leap (28 days)
    res_non_leap = calculate_manual_salary(20000.0, 2027, 2, present_days=28)
    assert res_non_leap["days_in_month"] == 28
    assert res_non_leap["payable_days"] == 28.0
    assert res_non_leap["total_salary"] == 20000.0
