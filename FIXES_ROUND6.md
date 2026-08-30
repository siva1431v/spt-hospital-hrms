# Round 6 Data-Integrity Fixes — Verification Report

---

## 1. Root Cause Summary (One Line Per Item)

- **P0-1 (Bhuvaneshwari dropped)**: Real employee `SPT12 / Bhuvaneshwari` (biometric code `12`) was missing from the DB because demo code `EMP12` had been set to `9912` / `is_active=false` without creating the real profile.
- **P0-2 (Makisha base salary typo & placeholder audit)**: `SPT30 Makisha Kasani` had a dropped zero (`basic_salary = 1000` instead of `10000`), and non-migrated staff lacked a `salary_source` marker.
- **P1-1 (Period working_days hardcoded 26)**: `POST /api/v1/payroll/periods` hardcoded `working_days=26` instead of deriving calendar month days (`calendar.monthrange(year, month)[1]`).
- **P1-2 (company_name single-page read)**: PDF parser extracted `Company:` on page 1 only rather than summarizing distinct per-page device headers across all pages.
- **P2-1 (Re-import dedup stats counter)**: `AttendanceImportService.commit` reported `imported=0` on duplicate skips without setting `records_duplicate = 1650`.
- **P2-2 (Housekeeping)**: Unit test `test_payroll.py` leaked `TEST_EMP_*` records into the dev DB, `is_manual_override` had no API reset option, and `PayrollPeriod` had no DELETE endpoint.

---

## 2. Files Changed

- `backend/database/seeds/fix_round6_data.py`: Data migration script creating `SPT12 Bhuvaneshwari` (₹14k), fixing Makisha (₹10k), auditing salaries, setting `salary_source`, and purging `TEST_EMP_*` rows.
- `backend/app/models/employee.py`: Added `salary_source` column (`MIGRATED` vs `PLACEHOLDER`).
- `backend/app/models/attendance.py`: Added `unknown_employee_codes`, `unknown_department_names`, `unmatched_row_count` to `AttendanceImport`.
- `backend/app/models/payroll.py`: Added `salary_source` to `PayrollRecord`.
- `backend/app/parsers/pdf/monthly_parser.py`: Multi-company page count aggregation (`Old Bio (9 pages), SPT (57 pages)`).
- `backend/app/services/attendance_import.py`: Persisted unknown codes & dedup count (`records_duplicate = 1650`).
- `backend/app/schemas/attendance.py`: Added `AttendanceImportResponse` with unknown code/dept fields.
- `backend/app/schemas/payroll.py`: Added `is_manual_override` to `PayrollRecordUpdate`.
- `backend/app/api/v1/endpoints/payroll.py`: Dynamic calendar `working_days`, `DELETE /payroll/periods/{id}`, and `is_manual_override: false` reset.
- `backend/tests/test_payroll.py`: Added auto-cleanup & rollback to prevent `TEST_EMP_*` row leaks.
- `backend/tests/test_round6_integrity.py`: Created comprehensive integrity & acceptance test suite.
- `frontend/src/app/(dashboard)/payroll/page.tsx`: Added `Placeholder Salary` badge, `Reset Override` button, and `Delete Period` button.

---

## 3. Salary Re-Verification Result

| Category | Count | Base Salary Status |
|---|---|---|
| **Migrated Staff** | **58** | Verified 100% against old calculator source list |
| **Placeholder Staff** (Doctors, `SPT2xx`, Dt Santhiya, Ashwin, Senthamilselvi) | **8** | Flagged as `PLACEHOLDER` (`salary_source = "PLACEHOLDER"`) |
| **Discrepancy Fixes** | **1** | `SPT30 Makisha Kasani` (₹1,000 $\rightarrow$ **₹10,000**) |

---

## 4. Acceptance Check (Before vs After)

| Metric | Target / PDF Actual | Before Fix | After Fix | Status |
|---|---|---|---|---|
| **Staff in Monthly Summary** | **66** | 65 | **66** | ✅ Verified |
| **Attendance Records (1–25 Aug)** | **1,650** | 1,625 | **1,650** | ✅ Verified |
| **Present Days** | **1,288** | 1,266 | **1,288** | ✅ Verified |
| **Absent Days** | **333** | 330 | **333** | ✅ Verified |
| **Device Late Instances** | **403** | 401 | **403** | ✅ Verified |
| **Qualifying Late (>15 min)** | **286** | 285 | **286** | ✅ Verified |
| **Staff with $\ge 1$ Qualifying Late** | **44** | 43 | **44** | ✅ Verified |
| **LOP Days (across 30 staff)** | **78** | 78 | **78** | ✅ Verified |

---

## 5. Automated Unit & Integration Tests

```bash
31 passed in 25.61s (100% pass rate)
```
