# SPT Hospital HRMS — Round 2 Fix Summary (FIXES_ROUND2.md)

All Round 2 defects identified during the follow-up QA pass have been investigated, fixed, and verified across both backend (FastAPI) and frontend (Next.js 14).

---

### P0-1: eSSL PDF parser extracts 0 of 45 records
- **Root Cause**: `RE_ATTENDANCE_DATE` and `RE_DEPT_HEADER` regexes strictly required colons/hyphens (`[:\-]`) which were missing in extracted text (`Attendance Date 16-Aug-2026`), skipping all date blocks, while multi-company headers and non-outpunch wrap lines went unhandled.
- **Files Changed**:
  - `backend/app/parsers/pdf/parser.py`
  - `backend/tests/test_import_integration.py` (New File)
- **Verification**: Wrote `tests/test_import_integration.py` asserting against the real PDF — verified 45 total records (9 employees × 5 dates), 6 Present / 39 Absent, 3 Present (No OutPunch), `['Default', 'MANAGER', 'NURSING']` departments, clean company name `'Old Bio'`, single OT row (17-Aug `203` OT 1:19), and 16-Aug `207` overnight NTS shift landing on 16-Aug. Test passed 100%.

---

### P0-2: Employee update returns 503
- **Root Cause**: `log_audit` inside `update_employee` invoked `json.dumps(update_data)` directly without `default=str`, raising an unhandled `TypeError` when payloads contained `date` or `Decimal` objects (e.g., `joining_date`, `basic_salary`).
- **Files Changed**:
  - `backend/app/api/v1/endpoints/employees.py`
- **Verification**: Updated `json.dumps(..., default=str)` in `update_employee` and `create_employee`. Tested updating department and shift on employee profile via `PUT /api/v1/employees/{id}`; changes persist to database and create an `UPDATE` audit entry.

---

### P1-1: Payroll reads Basic Salary as ₹0
- **Root Cause**: When an employee had no pre-configured `SalaryStructure`, `calculate_employee_payroll` fell back to `employee.basic_salary`, but zero-attendance months triggered a fallback setting `basic_salary = 0` and `net_salary = 0` with status `NO_DATA`.
- **Files Changed**:
  - `backend/app/payroll/engine.py`
  - `backend/tests/test_payroll.py`
- **Verification**: Verified `test_payroll.py` with attendance imported — basic salary is loaded from profile and pro-rated by paid days (`basic_earned = basic * (paid_days / working_days)`), `gross = basic + allowances + OT`, `net = gross - deductions` (clamped >= 0), and zero attendance marks record as `NO_DATA`.

---

### P1-2: API failures silent except employee-create form
- **Root Cause**: Response error interceptor in `api.ts` only handled 401 redirects, swallowing 400, 422, and 500 error messages without notifying the user.
- **Files Changed**:
  - `frontend/src/lib/api.ts`
  - `frontend/src/app/(dashboard)/attendance/import/page.tsx`
- **Verification**: Added `sonner` toast notifications in `api.ts` for all non-401 API errors. Added explicit error guidance and alert in PDF import wizard when 0 records are extracted.

---

### P2-1: Finalized periods still accept destructive actions
- **Root Cause**: "Calculate Payroll" and "Finalize Period" buttons remained active in the UI even when the selected period status was `FINALIZED`.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/payroll/page.tsx`
- **Verification**: Verified on `/payroll` — when period status is `FINALIZED`, both "Calculate Payroll" and "Finalize Period" buttons are disabled with explanatory tooltips ("Period is finalized — calculations are locked").

---

### P2-2: Internal filesystem paths leaked in API responses
- **Root Cause**: `preview_import` endpoint returned raw server filesystem paths `pdf_path` and `_temp_path` (`/Users/siva/...`) in JSON responses.
- **Files Changed**:
  - `backend/app/api/v1/endpoints/attendance.py`
  - `frontend/src/app/(dashboard)/attendance/import/page.tsx`
- **Verification**: Replaced server paths in `preview_import` with an opaque `session_token` UUID mapping in `_IMPORT_SESSIONS`. Client sends `session_token` on commit; internal paths are never exposed.

---

### P2-3: Build the four stub pages
- **Root Cause**: `/attendance/exceptions`, `/attendance/import-history`, `/attendance/monthly`, and `/payroll/salary-slips` rendered placeholder "Under Development" cards.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/attendance/exceptions/page.tsx`
  - `frontend/src/app/(dashboard)/attendance/import-history/page.tsx`
  - `frontend/src/app/(dashboard)/attendance/monthly/page.tsx`
  - `frontend/src/app/(dashboard)/payroll/salary-slips/page.tsx`
- **Verification**: Built all 4 feature pages with live API integrations:
  1. **Exceptions**: Interactive table with severity/status filters and inline Approve/Dismiss actions for missing out-punches.
  2. **Import History**: Session log table from `GET /attendance/imports` with record detail modal.
  3. **Monthly Summary**: Per-employee aggregate present/absent/incomplete/OT metrics with month/year selector.
  4. **Salary Slips**: Salary slips directory with PDF download buttons.

---

## Build & Test Verification Results

1. **Backend Test Suite (`pytest tests/ -v`)**:
   ```
   ======================== 9 passed, 0 failed in 3.17s =========================
   ```
2. **TypeScript Validation (`npx tsc --noEmit`)**:
   ```
   0 errors
   ```
3. **Next.js Production Build (`npm run build`)**:
   ```
   ✓ Compiled successfully in 425ms
   ✓ Running TypeScript ... Passed
   ✓ Static Page Generation (21/21 routes) ... Passed
   ```
