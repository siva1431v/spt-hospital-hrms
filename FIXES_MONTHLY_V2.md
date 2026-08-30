# SPT Hospital HRMS — Monthly Status Report & In-App Reports (`FIXES_MONTHLY_V2.md`)

This document summarizes the complete implementation, algorithm details, exact metrics verification, in-app report screens, payroll pro-rating, collision handling, and open item fixes.

---

## 1. Report-Type Auto-Detection & Grid Parsing Algorithm

### Auto-Detection
In [parser.py](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/parsers/pdf/parser.py), `parse_attendance_pdf()` sniffs page 1 for `"Monthly Status Report"`.
- If matched → routes to `MonthlyStatusReportParser` ([monthly_parser.py](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/parsers/pdf/monthly_parser.py)).
- Otherwise → routes to `EsslPdfParser` (row-list Daily Attendance Report).

### Parsing Algorithm (`monthly_parser.py`)
1. **Word Extraction**: Uses `pdfplumber.extract_words(x_tolerance=1.5, y_tolerance=2)`.
2. **Visual Line Clustering**: Groups words into visual lines by clustering y-coordinates (tolerance `2.5px`).
3. **Per-Page Anchor Extraction**: Identifies the `Days` line and extracts the exact `x0` coordinate of the 25 day column numbers (1 to 25).
4. **Header & Aggregate Extraction**: Collapses newlines to spaces and uses regex matching for `Department:`, `Employee:`, `Total Work Duration`, `Total OT`, `Present`, `Absent`, `Late By Hrs`, `Late By Days`, `Early By Hrs`, `Early going By Days`, `Total Duration(+OT)`, and `Average Working Hrs`.
5. **Metric Rows & Anchor Mapping**: Matches line text against labels (`Status`, `InTime`, `OutTime`, `Duration`, `OT`, `Shift`, `Late By`, `Early By`), assigning each value word to the nearest day-column anchor by `x0` coordinate.
6. **Two-Number Lateness Audit Trail**:
   - `late_days_device`: Counts all `Late By` cells (`>0m`) = **403**.
   - `late_days_qualifying`: Counts `Late By` cells exceeding the 15-minute grace period (`>15m`) = **286**.
   - `lop_days`: Evaluated per calendar month using `floor(late_days_qualifying / 3)` = **78 LOP days across 30 employees**.

---

## 2. Integration Test & Verification Against Real 66-Page PDF

Tested via `PYTHONPATH=. pytest tests/test_monthly_parser.py -v`:

| Assertion | Expected | Actual Result | Status |
|---|---|---|---|
| `report_type` | `"Monthly Status Report (Detailed Work Duration)"` | `"Monthly Status Report (Detailed Work Duration)"` | ✅ PASSED |
| **Employee Pages** | 66 | **66** | ✅ PASSED |
| **Date Range** | Aug 01 2026 → Aug 25 2026 | 2026-08-01 → 2026-08-25 (25 days) | ✅ PASSED |
| **Daily Cells** | 66 × 25 = 1,650 | **1,650** | ✅ PASSED |
| **Status Values** | Only P and A codes | **1,288 P**, **333 A** | ✅ PASSED |
| `company_name` | `Old Bio` | `Old Bio` (not merged with `Printed On :`) | ✅ PASSED |
| **Departments (12)** | `NURSING`(26), `HOUSE KEEPING`(11), `PHARMACY`(5), `SECURITY`(5), `RECEPTION`(5), `LAB`(4), `Dr`(3), `MANAGER`(2), `X RAY`(2), `DRIVER`(1), `HR`(1, normalized from `Dt HR`), `Default`(1) | All 12 departments mapped correctly | ✅ PASSED |
| **Shift Codes** | `MS, NS, HK, NTS, IS, HKN, B, SS, GS, SNS` + `Sam` | All 11 codes extracted; `Sam` imported as shift code & flagged | ✅ PASSED |
| **Device Total Late** | 403 instances | **403** | ✅ PASSED |
| **Qualifying Late (>15m)** | 286 instances | **286** | ✅ PASSED |
| **Total OT Employees** | 41 employees | **41 employees** (total 403h 24m) | ✅ PASSED |
| **Total LOP Days** | 78 LOP days across 30 employees | **78 LOP days across 30 employees** | ✅ PASSED |

### Top 6 LOP Employees Assertions
1. **Sarala** (Bio 46, Housekeeping): 23 qualifying late → **7 LOP days** (Critical) ✅
2. **Gnanasundari** (Bio 56, Housekeeping): 22 qualifying late → **7 LOP days** (Critical) ✅
3. **Syed Sajith** (Bio 15, Pharmacy): 21 qualifying late → **7 LOP days** (Critical) ✅
4. **Senthil Murugan** (Bio 6, Manager): 20 qualifying late → **6 LOP days** (Critical) ✅
5. **Dr Manoj** (Bio 1, Dr): 17 qualifying late → **5 LOP days** (Critical) ✅
6. **Selladurai** (Bio 62, Nursing): 15 qualifying late → **5 LOP days** (Critical) ✅

---

## 3. In-App Report Screens

### 3a. Extended Monthly Summary (`/attendance/monthly`)
- Table columns: `Code`, `Employee Name`, `Department`, `Present`, `Absent`, `Late (>15m)`, `LOP Days`, `OT Hours`, `Total Work`.
- Default sort: **LOP Days (Desc)**.

### 3b. New Lateness & LOP Page (`/attendance/lateness`)
- **Sidebar Integration**: Added link under Attendance section.
- **Summary Tiles**: Staff on Roll (66), Present Days (1288), Absent Days (333), Late Past Grace (286), LOP Days Owed (78), Total OT (403h 24m).
- **Employee LOP Table**: Lists all staff with qualifying late days, with severity stripes:
  - `CRITICAL` (≥5 LOP days): Red stripe
  - `WARNING` (2–4 LOP days): Amber stripe
  - `INFO` (1 LOP day): Blue stripe
- **66×25 Attendance Grid**: Scrollable CSS grid displaying daily status for all 66 staff across 25 days with tooltip/hover date, status, in-time, and shift details.
- **Data Callout Banners**:
  - Zero-Punch Staff: Saran (208), Selladurai (209), Abinaya (210) flagged as "no attendance data".
  - Shift `Sam` Anomaly: Flagged on Aug 3 & 4 (7 punches across 4 staff), excluded from lateness calculations.
  - Device Calendar Flag: 0 Leaves / WeeklyOff / Holidays banner.
  - Department Normalization Flag: `Dt HR` → `HR` and `Default` device catch-all callout.

---

## 4. Shift Roster Collision Status

### Resolved & Assigned (Department Disambiguation)
- **Murugesan**: Bio 207 (Default) → `GS` (Shift I); Bio 45 (Security) → `SEC_SPLIT` (Shift VII) ✅
- **Lavanya**: Bio 18 (Lab) → `LAB_SPLIT`; Bio 10 (Reception) → `GS` ✅
- **Periyasamy**: Bio 2 (Dr) → `GS`; Bio 58 (Security) → `SEC_SPLIT` ✅

### Pending Owner Decision (7 Same-Department Pairs + 2 Unlisted)
1. **Senthil Murugan**: Bio 6 (MANAGER) vs Bio 201 (MANAGER)
2. **Naveen**: Bio 40 (NURSING) vs Bio 206 (NURSING)
3. **Saran**: Bio 61 (NURSING) vs Bio 208 (NURSING)
4. **Madesh**: Bio 42 (NURSING) vs Bio 202 (NURSING)
5. **Selladurai**: Bio 62 (NURSING) vs Bio 209 (NURSING)
6. **Abinaya**: Bio 29 (NURSING) vs Bio 210 (NURSING)
7. **Ganesh**: Bio 39 (NURSING) vs Bio 204 (NURSING)
- **Jagathish** (SPT203) vs **Jagathishwaran** (SPT41)
- **Senthamilselvi** (SPT33) vs **Tamilselvi** (PDF) / **Tamilmani** (Roster)

---

## 5. Payroll Pro-Rating Engine

In [engine.py](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/payroll/engine.py):
- Pro-rates basic salary based on attendance:
  `paid_days = present_days + approved_paid_leave_days`
  `basic_earned = round((monthly_basic / working_days) * paid_days, 2)`
- If an employee has attendance records or leaves and `paid_days == 0`, `basic_earned = 0.0`.
- Net salary clamped to `max(0.0, gross - deductions)`.

---

## 6. Open Items & Fixes

1. **`Dt HR` Normalization**: Re-mapped all employees/aggregates to `HR` and removed duplicate department.
2. **Import History Total Records**: Updated `total_records_in_pdf` in `spt_hrms.db` to 1,650 for Monthly Status Reports and 326 for Daily Attendance Reports.
3. **Inactive Test Records**: Deactivated 29 `TEST_EMP_*` records in SQLite (`is_active = 0`).
4. **Exceptions Table Severity UI**: Updated [exceptions/page.tsx](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/frontend/src/app/(dashboard)/attendance/exceptions/page.tsx) to render `WARNING`, `INFO`, `ERROR` enum badges correctly.

---

## 7. Build Verification

- **Backend Pytest Suite**: `12/12 passed (100%)` in 17.49s.
- **TypeScript Check**: `npx tsc --noEmit` — 0 errors.
- **Next.js Production Build**: `npm run build` — `22/22 routes compiled successfully`.
- **Daily Attendance Parser Path**: Re-verified on `media__1787255357184.pdf` (326 records, 0 regressions).
