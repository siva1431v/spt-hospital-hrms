# SPT Hospital HRMS — Auto-fill LOP & Day-Level Leave Reclassification

## 1. Summary of Changes

This round resolves the missing links between attendance lateness, leave management, and monthly payroll:
1. **LOP Auto-Fill & Deductions in Payroll**: `calculate_employee_payroll` and `calculate_all_employees` automatically derive `qualifying_late_days` and `lop_days` ($\lfloor \frac{\text{qualifyingLateDays}}{3} \rfloor$), persisting them alongside `lop_deduction`, `security_fund_deduction`, and `total_deductions` on `PayrollRecord`.
2. **Interactive Lateness Breakdown**: The `LOP (DAYS & DED)` column in `/payroll` is interactive; clicking on it presents a modal displaying the exact dates, in-times, shifts, late minutes, and excess minutes past the 15-minute grace period.
3. **Day-Level Leave Reclassification**: On Daily Attendance (`/attendance`), admins can reclassify individual `ABSENT` days or bulk date ranges to `LEAVE` (selecting Casual, Sick, Earned, LOP, Maternity, Compensatory, or Emergency), and revert if needed. Reclassified days automatically flow into payroll records and are capped at 3 paid leave days per month.
4. **Base Salary Reconciliation**: Re-run on Name + Department disambiguated the 52 migrated staff with verified wages while isolating the 14 ghost duplicate / non-migrated placeholder records with `salary_source = 'PLACEHOLDER'`.
5. **Staff Count Fix**: Payroll page table queries with `page_size=200` and displays the true active headcount of 66 staff in the header badge.

---

## 2. August 2026 Payroll Totals & Spot Checks

### Summary Metrics:
- **Total Active Staff**: 66
- **Staff with LOP**: 30 employees
- **Total LOP Days**: 78.0 days
- **Payroll before LOP (`salary_part` sum)**: ₹6,30,629.02
- **Total LOP Deducted**: ₹40,596.75
- **Payroll after LOP**: ₹5,90,032.27
- **Total Net Salary Payout (including Fund & Collection)**: ₹5,58,532.27

### Six Verified Spot Checks:

| Employee Code & Name | Base Salary | LOP Days | LOP Deduction | Salary Part | Net Salary Payout |
|---|---|---|---|---|---|
| **SPT1 DR Manoj** | ₹25,000 | 5.0 d | ₹4,032.26 | ₹18,548.39 | **₹14,016.13** (₹14,516.13 before ₹500 Fund) |
| **SPT62 Selladurai** | ₹25,000 | 5.0 d | ₹4,032.26 | ₹18,548.39 | **₹14,016.13** (₹14,516.13 before ₹500 Fund) |
| **SPT6 Senthil Murugan** | ₹20,000 | 6.0 d | ₹3,870.97 | ₹14,838.71 | **₹10,467.74** (₹10,967.74 before ₹500 Fund) |
| **SPT46 Sarala** | ₹13,000 | 7.0 d | ₹2,935.48 | ₹10,064.52 | **₹6,629.04** (₹7,129.04 before ₹500 Fund) |
| **SPT15 Syed Sajith** | ₹13,000 | 7.0 d | ₹2,935.48 | ₹9,225.81 | **₹5,790.33** (₹6,290.33 before ₹500 Fund) |
| **SPT56 Gnanasundari** | ₹9,500 | 7.0 d | ₹2,145.16 | ₹7,048.39 | **₹4,403.23** (₹4,903.23 before ₹500 Fund) |

---

## 3. Day-Level Leave Reclassification Flow

1. **Daily Attendance Selection (`/attendance`)**:
   - Single row: Click **Mark Leave** on any `ABSENT` day to open modal.
   - Bulk rows: Check multiple rows to open bulk reclassification bar.
2. **Leave Type & Policy**:
   - Supported leave types: Casual Leave (`CL`), Sick Leave (`SL`), Earned Leave (`EL`), Loss of Pay (`LOP`), Maternity Leave (`ML`), Compensatory Off (`CO`), Emergency (`EM`).
   - Modal surfaces paid cap note: *"Hospital Paid Leave Policy: Up to 3 leave days per month are counted as paid in payroll. Any leave days beyond 3 remain unpaid."*
3. **Database & Audit Trail**:
   - Attendance status transitions from `ABSENT` $\to$ `LEAVE`.
   - `is_corrected = True`, `correction_reason` logged in `AttendanceCorrection` and `AuditLog`.
4. **Payroll Synchronization**:
   - `calculate_employee_payroll` automatically aggregates `Attendance.status == AttendanceStatus.LEAVE`.
   - Formula calculates `effective_leave = min(leave_days, paid_leave_cap)` (3 days max paid).
   - Monthly summary table (`/attendance/monthly`) includes dedicated **Leave** column.

---

## 4. Test Results

- **Automated Pytest Suite**: 42 passed, 0 failed in 28.21s
  - `tests/test_lop_autofill_and_leave.py`
  - `tests/test_lop_payroll.py`
  - `tests/test_round6_integrity.py`
  - `tests/test_round7_integrity.py`
  - `tests/test_monthly_parser.py`
  - `tests/test_e2e.py`
- **Next.js Production Build**: 22/22 routes generated statically with zero errors.
