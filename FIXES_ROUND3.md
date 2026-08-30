# SPT Hospital HRMS — Round 3 Fixes Summary

This document details all fixes implemented in Round 3 in response to QA testing feedback.

---

### P0-1 — Exceptions page route precedence & record generation

- **Root Cause (1 line)**: FastAPI route definition order placed parameterized `GET /{attendance_id}` before static `GET /exceptions`, causing requests to `/attendance/exceptions` to fail with HTTP 422 ("path -> attendance_id expected integer"), while incomplete punch records lacked `AttendanceException` rows.
- **Files Changed**:
  - `backend/app/api/v1/endpoints/attendance.py`
  - `backend/app/services/attendance_import.py`
- **Verification**: `GET /attendance/exceptions?review_status=PENDING` returns **HTTP 200 OK** with 161 total exceptions (50 missing out-punch records, overnight shift flags, zero times).

---

### P0-2 — Payroll basic salary calculation & pro-rating

- **Root Cause (1 line)**: `PayrollEngine` dropped basic salary to ₹0 for employees without attendance records for the month instead of reading their profile `basic_salary` and pro-rating by absent days.
- **Files Changed**:
  - `backend/app/payroll/engine.py`
  - `backend/tests/test_payroll.py`
- **Verification**: Running payroll for all 66 employees yields 66/66 non-zero `basic_salary` records. Unit tests in `test_payroll.py` for zero-records fallback, partial attendance, zero attendance, and OT passed 100%.

---

### P0-3 — Reopen finalized payroll period & create new periods

- **Root Cause (1 line)**: `reopen_payroll` endpoint restricted permissions to `SUPER_ADMIN` only and set status to `UNDER_REVIEW` instead of `DRAFT`, leaving periods locked in the UI.
- **Files Changed**:
  - `backend/app/api/v1/endpoints/payroll.py`
  - `frontend/src/app/(dashboard)/payroll/page.tsx`
- **Verification**: Added "Reopen Period" button to frontend payroll view (resets period & records status to `DRAFT`) and a "+ New Period" dialog to create new monthly periods. Tested reopening period 1 via API and UI.

---

### P1-1 — Junk department normalization (`Dt HR` -> `HR`)

- **Root Cause (1 line)**: The PDF header regex extracted raw string `"Dt HR"` from section headers which was saved as a distinct department rather than normalizing to `"HR"`.
- **Files Changed**:
  - `backend/app/parsers/pdf/parser.py`
  - `backend/app/services/attendance_import.py`
  - Database updated via migration script to reassign records to department ID 11 (`HR`).
- **Verification**: Verified `Dt HR` department is merged into `HR` and deactivated. PDF parser maps `"Dt HR"` section headers directly to `"HR"`.

---

### P1-2 — Total PDF Records fixed count

- **Root Cause (1 line)**: `total_records_in_pdf` in early test runs reflected page-limited extraction counts before multi-page parsing was enabled.
- **Files Changed**:
  - `backend/app/services/attendance_import.py`
  - `backend/app/api/v1/endpoints/attendance.py`
- **Verification**: Verified `GET /attendance/imports` reports `total_records = 326` consistently across all import logs for `Daily Attendance Report AUG.pdf`.

---

### P1-3 — Import log detail DATE column empty key mismatch

- **Root Cause (1 line)**: The backend API returned `"date": r.raw_date` in `GET /imports/{import_id}`, whereas the frontend modal table expected `r.attendance_date`.
- **Files Changed**:
  - `backend/app/api/v1/endpoints/attendance.py`
  - `frontend/src/app/(dashboard)/attendance/import-history/page.tsx`
- **Verification**: `GET /imports/{import_id}` response now includes both `"attendance_date"` and `"date"` keys. Verified dates render in the View Log modal.

---

### P2-1 — Duplicate/overlapping leave request validation

- **Root Cause (1 line)**: `apply_leave` endpoint lacked a date range overlap check for existing non-rejected leave requests of the same employee.
- **Files Changed**:
  - `backend/app/api/v1/endpoints/leaves.py`
- **Verification**: `POST /leaves` with overlapping date range returns **HTTP 400 Bad Request** with `"Employee already has an active or pending leave request overlapping with this date range."`.

---

### Demo Account Data Hygiene Note (`EMP12`)

- **Resolution**: Updated `EMP12` demo account biometric code from `"12"` to `"9912"` and deactivated it. Restored biometric code `"12"` to Bhuvaneshwari in Pharmacy (`SPT12`).

---

## Verification Results Summary

1. **Backend Unit & Integration Test Suite**: `9 passed in 2.97s` (`PYTHONPATH=. pytest tests/ -v`).
2. **TypeScript Compilation**: `npx tsc --noEmit` exited cleanly with 0 errors.
3. **Next.js Production Build**: `21/21 routes compiled successfully` (`npm run build`).
