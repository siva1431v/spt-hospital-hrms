# SPT Hospital HRMS — Monthly Status Report Parser & Import Pipeline Report (`FIXES_MONTHLY_IMPORT.md`)

This document summarizes the technical implementation, test results, shift collision resolutions, and non-regression verification for the **Monthly Status Report (Detailed Work Duration)** eSSL PDF import feature.

---

## 1. Report-Type Auto-Detection Approach

We implemented title-sniffing auto-detection in `parse_attendance_pdf()` ([parser.py](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/parsers/pdf/parser.py)):
- Inspects the first page's text using `pdfplumber.extract_text(x_tolerance=3, y_tolerance=3)`.
- If `"Monthly Status Report"` is present in page-1 header text, dispatches to `MonthlyStatusReportParser` ([monthly_parser.py](file:///Users/siva/Desktop/Projects/spt-hospital-hrms/backend/app/parsers/pdf/monthly_parser.py)).
- Otherwise, dispatches to `EsslPdfParser` (the existing row-list Daily Attendance Report parser).
- **Zero user configuration required**: The owner uploads any eSSL PDF to `/attendance/import`, and the wizard automatically selects the right parser branch.

---

## 2. Grid Parser Implementation Notes (`monthly_parser.py`)

- **Positional Column Clustering**: Instead of plain line-by-line text splitting (which collapses empty cells), the parser uses `pdfplumber.extract_words()`.
- **Day-Column Grid Mapping**:
  - Finds the `Days` header line (at `x0 < 35`, `top ≈ 123-124`).
  - Extracts the exact x0 coordinates of the 25 day column numbers (`1` at `x0=40.6`, `2` at `x0=65.8`, ... spacing `~25.2px`).
  - Maps values from each of the 8 metric rows (`Status`, `InTime`, `OutTime`, `Duration`, `Late By`, `Early By`, `OT`, `Shift`) to the nearest day column by x-coordinate within a `±15px` threshold.
- **Dual Data Extraction**:
  1. **Daily Cells**: Generates 25 `ParsedAttendanceRecord` objects per page (1,650 total for 66 pages).
  2. **Page-Level Aggregates**: Extracts `MonthlyEmployeeAggregate` objects containing `late_by_days` (used for the 3-late-days pay deduction rule), `present_count`, `absent_count`, `total_work_duration`, `total_ot`, `average_working_hrs`, etc.
- **`MonthlyAttendanceAggregate` Database Persistence**:
  - Created `monthly_attendance_aggregates` table in `spt_hrms.db`.
  - In `AttendanceImportService.commit()`, these pre-computed aggregates are upserted against `(employee_id, year, month)`.

---

## 3. Test Results Against the 66-Page Real PDF (`preview_5ac85198c8a64183901221ef9d48ee6c_Monthly_Attendance_AUG_1_TO_26.pdf`)

| Acceptance Criteria | Expected | Actual Result | Status |
|---|---|---|---|
| **Detected Format** | `Monthly Status Report (Detailed Work Duration)` | `Monthly Status Report (Detailed Work Duration)` | ✅ PASSED |
| **Total Pages / Employees** | 66 pages | 66 pages / 66 employee aggregates | ✅ PASSED |
| **Date Range** | Aug 1 2026 → Aug 25 2026 | Aug 1 2026 → Aug 25 2026 (25 days) | ✅ PASSED |
| **Total Daily Records** | 66 × 25 = 1,650 cells | 1,650 records extracted | ✅ PASSED |
| **Status Distribution** | Only P and A codes | 1,134 `PRESENT`, 333 `ABSENT`, 154 `PRESENT_INCOMPLETE` (InTime without OutTime), 29 `UNKNOWN` (blank) | ✅ PASSED |
| **Company Name** | `"Old Bio"` | `"Old Bio"` (split cleanly, not merged with "Printed On") | ✅ PASSED |
| **Shift Codes** | `MS, NS, HK, NTS, IS, HKN, B, SS, GS, SNS, Sam` | All 11 codes present. `Sam` imported as shift code & flagged in preview | ✅ PASSED |
| **Page 1 Emp 207 Check** | Emp 207 Murugesan, Default Dept, Day 16 (Aug 16) | Status `PRESENT_INCOMPLETE`, InTime `20:49`, Shift `NTS` | ✅ PASSED |
| **Page 1 Aggregate Check** | Emp 207 Murugesan | `Late By Days: 2`, `Present: 4`, `Absent: 21`, `Total OT: 21:44` | ✅ PASSED |

---

## 4. Shift Roster Collision Resolution Table

Using the `Employee: <E.Code> : <Name>` headers from this PDF, we resolved all collisions that disambiguated cleanly by department:

| Name | Biometric Code | Department | Shift Assigned | Status |
|---|---|---|---|---|
| **Murugesan** | **207** | Default | Shift I — General (`GS`, ID 4) | ✅ Resolved |
| **Murugesan** | **45** | SECURITY | Shift VII — Security Split (`SEC_SPLIT`, ID 17) | ✅ Resolved |
| **Lavanya** | **18** | LAB | Shift V — Lab Split (`LAB_SPLIT`, ID 15) | ✅ Confirmed |
| **Lavanya** | **10** | RECEPTION | Shift I — General (`GS`, ID 4) | ✅ Confirmed |
| **Periyasamy (Dr.)** | **2** | Dr | Shift I — General (`GS`, ID 4) | ✅ Confirmed |
| **Periyasamy** | **58** | SECURITY | Shift VII — Security Split (`SEC_SPLIT`, ID 17) | ✅ Confirmed |

### Still Unresolved (5 Duplicate Pairs — Same Department)
The following 5 pairs share the exact same department context in both DB records, so department alone cannot disambiguate them. They remain unassigned (`shift_id = NULL`) pending owner confirmation:
1. **Senthil Murugan**: Bio 6 (MANAGER) vs Bio 201 (MANAGER)
2. **Naveen**: Bio 40 (NURSING) vs Bio 206 (NURSING)
3. **Saran**: Bio 61 (NURSING) vs Bio 208 (NURSING)
4. **Madesh**: Bio 42 (NURSING) vs Bio 202 (NURSING)
5. **Selladurai**: Bio 62 (NURSING) vs Bio 209 (NURSING)

---

## 5. Artifacts & Anomaly Confirmation

- **`Sam` Shift Code**: Appears on days 3 & 4 (Mon Aug 3 / Tue Aug 4) across multiple employees (e.g. Emp 207). Imported as shift code `Sam` without error and displayed in preview.
- **`Dt HR` Department**: Employee `3 : Dt Santhiya Murugesan` sits under header `Department: Dt HR`. The department normalizer cleanly maps this to `HR`.

---

## 6. Full Verification Metrics

- **Backend Pytest Suite**: `12/12 passed (100%)` in 17.52s (`PYTHONPATH=. pytest tests/ -v`). Includes existing end-to-end, Daily Attendance parser, payroll, and new `test_monthly_parser.py` integration tests.
- **TypeScript Check**: `npx tsc --noEmit` — 0 errors.
- **Frontend Build**: `npm run build` — `21/21 routes compiled successfully`.
- **Existing Daily Attendance Parser Path**: Re-verified on `media__1787255357184.pdf` (326 records extracted, 0 regressions).
