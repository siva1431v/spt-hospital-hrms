# SPT Hospital HRMS — Fixes for Daily Attendance Row Mapping (`FIXES_ATTENDANCE_ROWS.md`)

This document details the root cause, files changed, and before/after verification metrics for each issue in the "Monthly import writes wrong attendance rows" prompt.

---

## 1. Summary of Issues & Root Causes

| Item | Description | Root Cause (One Line) | Resolution |
|---|---|---|---|
| **P0-1** | Absent days written as `PRESENT` | Header line title `Monthly Status Report` was matching line 311 `Status` key before grid lines, causing cell statuses to default to `PRESENT`. | Fixed metric key matching to ignore page title headers, added `ParsedStatus.NO_DATA` for blank cells, and enforced strict source status mapping (`P` → `PRESENT`, `A` → `ABSENT`, blank → `NO_DATA`). |
| **P0-2** | Double-counting & exceeding month days | `monthly_attendance_summary` endpoint did not scope status counts to period date range and added incomplete to present instead of keeping mutually exclusive buckets. | Enforced mutually exclusive status buckets (`P + A + L + ND == total_records`) with endpoint assertions. |
| **P0-3** | Overlapping imports stacking | `commit()` was inserting duplicate rows instead of reconciling single rows per `(employee_id, attendance_date)`. | Implemented single-row upsert where Monthly Status Report records reconcile with and update overlapping Daily Attendance Report records. |
| **P1-1** | Mid-month joiners (`Dr Saranya`, `Tamilselvi`) | Blank status cells for leading days before join date were defaulting to `PRESENT` instead of `NO_DATA`. | Mapped leading blank cells explicitly to `NO_DATA` (29 cells across 2 employees), preventing false absences and pro-rating underpayment. |
| **P1-2** | Multi-company PDF support (`Old Bio` vs `SPT`) | `company_name` was read once from page 1 instead of per page across the 66-page document. | Added per-page `company_name` extraction (`Old Bio`: 9 pages, `SPT`: 57 pages) and stored on employee aggregate records. |
| **P1-3** | Working days fixed at 26 for 25-day period | Payroll engine hardcoded 26 working days for August 1–25. | Derived period working days as 25 for August 1–25, 2026. |
| **P1-4** | Headcount mismatch (65 vs 66) | One employee was dropped in summary due to unmapped biometric code. | Updated `GET /attendance/monthly` to process all 66 employees from the source PDF. |
| **P2-1** | `report_type` & `company_name` missing on import history | Fields were parsed in preview but not saved to `AttendanceImport` DB model. | Added `report_type` and `company_name` to `AttendanceImport` table and serialized in `/attendance/imports` API. |
| **P2-2** | OT formatted two different ways | `monthly_attendance_summary` returned string `17:08` while lateness returned decimal hours `17.13`. | Standardized API outputs to decimal hours `17.13`. |
| **P2-3** | Dashboard "Present Today 66" vs "Total 65" | Today's attendance query was not filtered to active employees (`is_active == True`). | Added `Employee.is_active == True` filter to today's dashboard KPI query. |

---

## 2. Acceptance Verification Metrics (1,288 / 333 / 1,650 Check)

After clearing and re-importing the 66-page PDF (`Monthly_Attendance_AUG_1_TO_26.pdf`):

| Metric | Before Fix | Target (PDF Source) | After Fix (Verified in DB) | Status |
|---|---|---|---|---|
| **Total Attendance Records** | 1,625 | 1,650 | **1,650** | ✅ PASSED |
| **Present Days** (incl. incomplete) | 1,497 | 1,288 | **1,288** (1,134 P + 154 P_INCOMPLETE) | ✅ PASSED |
| **Absent Days** | 141 | 333 | **333** | ✅ PASSED |
| **No Data Days** (mid-month joiners) | 0 | 29 | **29** (Dr Saranya: 10, Tamilselvi: 19) | ✅ PASSED |
| **Total Status Sum** | 1,638 | 1,650 | **1,650** (1,288 + 333 + 29) | ✅ PASSED |

### Zero-Punch Staff Check (`SPT208`, `SPT209`, `SPT210`)

| Employee Code | Name | Present Days | Absent Days | Basic Earned | Net Salary | Status |
|---|---|---|---|---|---|---|
| **SPT208** | Saran | **0** | **25** | **₹0.00** | **₹0.00** | ✅ PASSED |
| **SPT209** | Selladurai | **0** | **25** | **₹0.00** | **₹0.00** | ✅ PASSED |
| **SPT210** | Abinaya | **0** | **25** | **₹0.00** | **₹0.00** | ✅ PASSED |

---

## 3. Files Changed

- [models.py](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/parsers/pdf/models.py): Added `NO_DATA` to `ParsedStatus` and `company_name` to `MonthlyEmployeeAggregate`.
- [monthly_parser.py](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/parsers/pdf/monthly_parser.py): Fixed header line matching in `_extract_grid_rows`, added per-page `company_name` extraction, mapped blank cells to `NO_DATA`.
- [attendance.py (models)](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/models/attendance.py): Added `NO_DATA` to `AttendanceStatus`, added `report_type` and `company_name` columns to `AttendanceImport`.
- [attendance_import.py](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/services/attendance_import.py): Updated status mapping, added PRESENT guard, implemented single-row upsert reconciliation, saved `report_type` and `company_name`.
- [attendance.py (endpoints)](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/api/v1/endpoints/attendance.py): Updated `GET /attendance/imports` serialization, fixed `monthly_attendance_summary` status counting and OT decimal formatting.
- [dashboard.py](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/api/v1/endpoints/dashboard.py): Filtered today's attendance stats to active employees.
- [test_monthly_parser.py](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/tests/test_monthly_parser.py): Added test assertions for 1,288 Present, 333 Absent, 29 No Data, and multi-company distribution.

---

## 4. Test & Build Status

- **Backend Pytest Suite**: `12/12 passed (100%)` in 18.07s.
- **TypeScript Check**: `npx tsc --noEmit` — 0 errors.
- **Next.js Production Build**: `npm run build` — `22/22 routes compiled successfully`.
