# SPT Hospital HRMS — LOP & Savings Fund Payroll Deductions Integration

## 1. Executive Summary

Loss of Pay (LOP) resulting from qualifying late arrivals (beyond the 15-minute grace period) and the Staff Savings Fund (retention scheme) deductions have been directly integrated into the payroll calculation engine, API endpoints, salary slip PDF generator, and frontend payroll directory.

---

## 2. Salary Calculation Formula

The verified hospital salary formula has been extended with deductions:

### Step 1: Per-Day Rate & Payable Days (Unchanged from Manual Calculator)
$$\text{daysInMonth} = \text{calendar days in the period's month } (28, 29, 30, 31)$$
$$\text{perDay} = \frac{\text{basicSalary}}{\text{daysInMonth}}$$
$$\text{payableDays} = \min(\text{presentDays}, \text{daysInMonth}) + (\text{halfDays} \times 0.5) + \min(\text{leaveDays}, \text{paidLeaveCap}) + \text{offDutyDays}$$
$$\text{salaryPart} = \min(\text{payableDays} \times \text{perDay}, \text{basicSalary})$$

### Step 2: LOP and Savings Fund Deductions
$$\text{lopDays} = \lfloor \frac{\text{qualifyingLateDays}}{\text{lateDaysPerLop}} \rfloor$$
$$\text{lopDeduction} = \min(\text{lopDays} \times \text{perDay}, \text{salaryPart})$$
$$\text{fundDeduction} = \text{employee.security\_fund\_deduction } (0 \text{ if unset})$$
$$\text{totalDeductions} = \text{lopDeduction} + \text{fundDeduction}$$

### Step 3: Payout Net Salary
$$\text{netSalary} = \max(0, \text{salaryPart} - \text{totalDeductions}) + \text{collection}$$

---

## 3. Key Design Decisions

1. **Equal Per-Day Rate**: LOP days are deducted at the exact same daily rate as payable days are earned ($\frac{\text{basic}}{\text{calendarDays}}$).
2. **Loss-Prevention Clamping**: $\text{lopDeduction}$ is clamped so it can never exceed $\text{salaryPart}$ earned in the month. An employee who was present 4 days but has 7 LOP days cannot owe money to the hospital.
3. **Collection Protection**: Collection is added after deductions ($\max(0, \text{salaryPart} - \text{totalDeductions}) + \text{collection}$), matching the manual calculator where collection is paid even if net earned days are zero.
4. **Deposit on Finalize**: Staff Savings Fund withholdings are automatically deposited into `security_fund_transactions` with `transaction_type = "DEPOSIT"` only when a period is finalized (`POST /api/v1/payroll/periods/{id}/finalize`), never on intermediate calculations.
5. **Configurable Policy**: Late threshold (3 late arrivals per LOP day), paid leave cap (3 days per month), and grace period (15 minutes) are read dynamically from `system_settings`.
6. **Manual Override Support**: Manual overrides for `lop_days`, `qualifying_late_days`, `present_days`, `half_days`, `leave_days`, `off_duty_days`, and `collection` are fully preserved during recalculation.

---

## 4. Test Results & Verification

### August 2026 Dataset Verification:
- **Total Staff**: 66 active employees
- **Staff with LOP**: 30 employees
- **Total LOP Days**: 78.0 days
- **Total Late Arrivals (past grace period)**: 286 qualifying late arrivals

### Six Spot Checks Asserted in Pytest:

| Employee | Base Salary | LOP Days | Deduction (₹) | Salary Part (₹) | Net Salary (₹) |
|---|---|---|---|---|---|
| **SPT1 Dr Manoj** | 25,000 | 5 | 4,032.26 | 18,548.39 | **14,516.13** |
| **SPT62 Selladurai** | 25,000 | 5 | 4,032.26 | 18,548.39 | **14,516.13** |
| **SPT6 Senthil Murugan** | 20,000 | 6 | 3,870.97 | 14,838.71 | **10,967.74** |
| **SPT46 Sarala** | 13,000 | 7 | 2,935.48 | 10,064.52 | **7,129.04** |
| **SPT15 Syed Sajith** | 13,000 | 7 | 2,935.48 | 9,225.81 | **6,290.33** |
| **SPT56 Gnanasundari** | 9,500 | 7 | 2,145.16 | 7,048.39 | **4,903.23** |

*All 6 spot checks pass 100% in `backend/tests/test_lop_payroll.py`.*

---

## 5. Files Changed

1. **Database Schema & Models**:
   - `backend/app/models/payroll.py`: Added `qualifying_late_days`, `lop_days`, `lop_deduction`, `security_fund_deduction`, `total_deductions` to `PayrollRecord`.
2. **Payroll Engine**:
   - `backend/app/payroll/engine.py`: Updated `calculate_employee_payroll` and `calculate_all_employees` to apply the LOP deduction formula, integrate savings fund deductions, generate itemized salary slip line items (`Lateness LOP (X days from Y late arrivals)` and `Staff Savings Fund`), and read settings from DB.
3. **API Schemas & Endpoints**:
   - `backend/app/schemas/payroll.py`: Updated `PayrollRecordUpdate` and `PayrollRecordResponse`.
   - `backend/app/api/v1/endpoints/payroll.py`: Updated `get_payroll_records`, `update_payroll_record`, `get_payroll_record`, and `finalize_payroll`.
4. **Frontend UI**:
   - `frontend/src/app/(dashboard)/payroll/page.tsx`: Updated table with `Payable Days`, `Salary Part`, `LOP (Days & Ded)`, `Savings Fund`, `Collection`, `Net Salary`, and updated live preview modal.
   - `frontend/src/app/(dashboard)/payroll/salary-slips/page.tsx`: Updated number formatting to prevent blank `₹` rendering for gross and deductions.
5. **Test Suite**:
   - `backend/tests/test_lop_payroll.py`: Added 4 automated integration test suites covering spot checks, aggregate counts, clamping, and 30-day calendar months.
