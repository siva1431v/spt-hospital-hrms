# SPT Hospital HRMS — Round 7 Fixes & Feature Sweep Verification

All items from the Round 7 full feature sweep have been resolved and verified.

---

## Root Causes & Files Changed

### P0-1 — Exceptions Review Workflow & Bulk Action
- **Root Cause**: `PUT /attendance/exceptions/{id}/review` and `POST /attendance/exceptions/bulk-review` were never implemented in the backend API router. The frontend header badge was displaying page size (`exceptions.length`) rather than the actual pending count from the database.
- **Files Changed**:
  - `backend/app/schemas/attendance.py`
  - `backend/app/api/v1/endpoints/attendance.py`
  - `frontend/src/app/(dashboard)/attendance/exceptions/page.tsx`
- **Verification**: Built single review `PUT /attendance/exceptions/{id}/review` and bulk action `POST /attendance/exceptions/bulk-review`. Verified with automated pytest asserting review status transitions to `APPROVED` and `DISMISSED`. Fixed badge to reflect actual pending count from DB.

---

### P0-2 — Savings-Fund (Retention) Scheme Single Write & Payroll Integration
- **Root Cause**: Unvalidated transaction payload and lack of strict Pydantic model (`extra="forbid"`) coupled with missing withdrawal over-draft protection and manual double-calling in test flows. Savings fund deductions were also not automatically deposited on period finalization.
- **Files Changed**:
  - `backend/app/schemas/employee.py`
  - `backend/app/api/v1/endpoints/employees.py`
  - `backend/app/payroll/engine.py`
  - `backend/app/api/v1/endpoints/payroll.py`
  - `frontend/src/app/(dashboard)/employees/[id]/page.tsx`
  - `backend/tests/test_round7_integrity.py`
- **Verification**: Created strict `SavingsFundTransactionCreate` (`extra="forbid"`). Tested with pytest asserting that sending 1 `POST /employees/{id}/savings-fund/transactions` creates **exactly 1 row** (`count_after == count_before + 1`). Added balance validation preventing over-drafts (asserted 400 Bad Request). Connected `security_fund_deduction` into payroll calculation and automatic `DEPOSIT` generation on `POST /payroll/periods/{id}/finalize`. Added Resignation Settlement workflow in frontend.

---

### P0-3 — Base Salary Matching & Ambiguous Same-Department Pairs Guard
- **Root Cause**: Blind name matching collided Dr. Periyasamy (Doctor) with Security Periyasamy (₹13,000), and arbitrarily set duplicate same-name candidates sitting in the same department (e.g. Abinaya, Ganesh, Madesh, Naveen, Saran, Selladurai, Senthil Murugan, Jagathish, Murugesan).
- **Files Changed**:
  - `backend/database/seeds/reconcile_round7_salaries.py`
  - `backend/app/api/v1/endpoints/payroll.py`
- **Verification**: Reconciled salaries on `Name + Department`: Lavanya (Lab bio 18) = ₹14,000; Lavanya (Reception bio 10) = ₹12,000; Periyasamy (Security bio 58) = ₹13,000; DR Periyasamy (Doctor bio 2) = `PLACEHOLDER`. Ambiguous duplicate pairs set to `PLACEHOLDER` for owner decision. Added check in `POST /payroll/periods/{id}/finalize` blocking payroll finalization if any employee contains a placeholder/unset salary.

---

### P1-1 — Fix `GET /api/v1/leaves/balances` Hard Failure
- **Root Cause**: `selectinload(LeaveBalance.employee if hasattr(...) else None)` passed `None` to `selectinload` because `LeaveBalance` model lacked the `employee` and `leave_type` relationships.
- **Files Changed**:
  - `backend/app/models/leave.py`
  - `backend/app/api/v1/endpoints/leaves.py`
  - `backend/tests/test_round7_integrity.py`
- **Verification**: Added `employee` and `leave_type` relationships to `LeaveBalance`. Tested `GET /leaves/balances` returning 200 with rich employee and leave type names without connection crashes.

---

### P1-2 — Guard Shift Deletion with Active Reference Check
- **Root Cause**: `DELETE /shifts/{id}` performed soft deletion without checking if active employees were currently assigned to the shift.
- **Files Changed**:
  - `backend/app/api/v1/endpoints/shifts.py`
  - `backend/tests/test_round7_integrity.py`
- **Verification**: Added reference count query returning `409 Conflict` if active employees are assigned, with optional `?reassign_to_id=` support. Tested with pytest.

---

### P1-3 — Guard Department Deletion & Remove Stray `QA DEPT EDITED`
- **Root Cause**: `DELETE /departments/{id}` lacked foreign key checks against active employees.
- **Files Changed**:
  - `backend/app/api/v1/endpoints/departments.py`
  - `backend/database/seeds/populate_designations_and_shift_fixes.py`
- **Verification**: Added active employee reference check returning `409 Conflict`. Removed stray `QA DEPT EDITED` (id 17) directly from the database.

---

### P1-4 — Fix Table Field-Name Mismatches on Daily Attendance & Salary Slips
- **Root Cause**: Daily Attendance checked `rec.department_name` while serializer returned `rec.department`. Salary Slips lacked fallback for `gross_salary` and `deductions`.
- **Files Changed**:
  - `backend/app/api/v1/endpoints/attendance.py`
  - `backend/app/api/v1/endpoints/payroll.py`
  - `frontend/src/app/(dashboard)/attendance/page.tsx`
  - `frontend/src/app/(dashboard)/payroll/salary-slips/page.tsx`
- **Verification**: Serializer now supplies both `department` and `department_name` along with `gross_salary` and `total_deductions`. Frontend templates use fallback chains displaying all numbers properly.

---

### P1-5 — Salary Slips Pagination & Total Count Display
- **Root Cause**: Frontend used `filteredRecords.length` from a capped 50-row page without pagination parameters.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/payroll/salary-slips/page.tsx`
- **Verification**: Changed records fetch to `page_size=200` and bound total slips badge to `res.data.total`.

---

### P2-1 — Settings: LOP, Paid Leave, Grace Period Configuration
- **Root Cause**: System settings UI showed obsolete hardcoded 26 working days instead of surfacing LOP threshold, paid leave monthly cap, and grace period.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/settings/page.tsx`
- **Verification**: Added LOP threshold (3 late days), paid leave monthly cap (3 days), grace period (15 min) inputs, and informative notice on dynamic calendar days.

---

### P2-2 — Leave Rejection & Approval Status Rules
- **Root Cause**: Rejection endpoint allowed rejecting non-pending leaves without status validation.
- **Files Changed**:
  - `backend/app/api/v1/endpoints/leaves.py`
- **Verification**: Added validation ensuring only `PENDING` leaves can be approved or rejected.

---

### P2-3 — Housekeeping (Designations, Chinnadurai Shift, Lateness Export & QA Cleanup)
- **Root Cause**: 66 staff lacked explicit `designation_id` links; Chinnadurai was assigned to `HK_SPLIT` instead of `SEC_SPLIT`; Lateness & LOP Excel export was missing.
- **Files Changed**:
  - `backend/database/seeds/populate_designations_and_shift_fixes.py`
  - `backend/app/api/v1/endpoints/reports.py`
  - `frontend/src/app/(dashboard)/reports/page.tsx`
- **Verification**: Assigned designations to all 66 staff; updated Chinnadurai to `SEC_SPLIT`; added `GET /api/v1/reports/lateness-lop` with openpyxl Excel formatting and period selector in Reports Hub; deleted QA test rows.
