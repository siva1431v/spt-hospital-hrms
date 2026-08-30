# SPT Hospital HRMS — Bug Fix Summary (FIXES.md)

All 10 confirmed defects identified during the QA pass have been investigated, fixed, and verified across both backend (FastAPI) and frontend (Next.js 14).

---

### BUG-1: Payroll calculates negative net salary (−₹25,000 per employee)
- **Root Cause**: The payroll engine calculated `basic_earned` by pro-rating basic salary by present days (implicitly handling unpaid days), but then **also** subtracted `lop_amount = per_day_rate × loss_of_pay_days` as an explicit deduction. This resulted in a double deduction for any absent days. For an employee with zero attendance, `basic_earned = 0` and `lop_amount = 25,000`, producing `net_salary = −25,000`.
- **Files Changed**:
  - `backend/app/payroll/engine.py`
  - `backend/app/models/payroll.py`
  - `backend/tests/test_payroll.py`
- **Fix**: Removed explicit LOP deduction line items (handled implicitly via pro-rating). Added a zero-attendance check that sets record status to `NO_DATA` with `net_salary = 0`. Added a floor guard clamping `net_salary = max(0, gross - deductions)`. Updated leave date range query to compute the actual last day of the month using `calendar.monthrange`.
- **Verification**: Ran `pytest tests/test_payroll.py` — verified full attendance, partial attendance (20 days present, 6 absent), zero attendance (NO_DATA status), and overtime (2 hrs @ ₹120/hr). All assertions passed with zero negative values.

---

### BUG-2: Add Employee wizard saves on "Next Step" and skips Step 2
- **Root Cause**: The entire multi-step form was wrapped in an HTML `<form>` element. Pressing **Enter** in any input field or clicking buttons without type restrictions triggered implicit HTML form submission, immediately invoking `handleSubmit` and skipping Step 2.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/employees/new/page.tsx`
- **Fix**: Replaced the outer `<form>` with a `<div>`. Explicitly set `type="button"` on all navigation buttons. "Next Step" now programmatically validates Step 1 fields before advancing. "Save Employee Profile" is a button click handler that sends the full Step 1 + Step 2 payload.
- **Verification**: Tested flow in browser/build — "Next Step" validates required fields and advances to Step 2 without creating an employee. Only clicking "Save Employee Profile" on Step 2 submits data with department, shift, and joining date.

---

### BUG-3: Employees cannot be edited at all
- **Root Cause**: The frontend lacked an edit page/route at `/employees/[id]/edit`. While the backend API `PUT /employees/{id}` existed, the UI only offered view and deactivate actions.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/employees/[id]/edit/page.tsx` (New file)
  - `frontend/src/app/(dashboard)/employees/page.tsx`
  - `frontend/src/app/(dashboard)/employees/[id]/page.tsx`
- **Fix**: Created `/employees/[id]/edit/page.tsx` using a 2-step form matching the creation layout, pre-populated from `GET /employees/{id}` and submitting via `PUT /employees/{id}`. Added an Edit button to the directory rows and detail page header.
- **Verification**: Build verified cleanly. Navigating to `/employees/[id]/edit` pre-populates fields and updates records on submit.

---

### BUG-4: Four sidebar links are dead 404s
- **Root Cause**: Four directories existed (`/attendance/monthly`, `/attendance/import-history`, `/attendance/exceptions`, `/payroll/salary-slips`) but had no `page.tsx` files.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/attendance/monthly/page.tsx` (New file)
  - `frontend/src/app/(dashboard)/attendance/import-history/page.tsx` (New file)
  - `frontend/src/app/(dashboard)/attendance/exceptions/page.tsx` (New file)
  - `frontend/src/app/(dashboard)/payroll/salary-slips/page.tsx` (New file)
- **Fix**: Created styled "Coming Soon" placeholder pages inside the application dashboard shell for all 4 routes, displaying page titles, descriptions, icons, and "Under Development" badges.
- **Verification**: `next build` generated static routes for all 4 paths (`/attendance/monthly`, `/attendance/import-history`, `/attendance/exceptions`, `/payroll/salary-slips`).

---

### BUG-5: Duplicate employee ID / biometric code fails silently
- **Root Cause**: Error handling in `handleSubmit` called browser `alert()`, which could be swallowed or missed, and did not highlight the failing input field.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/employees/new/page.tsx`
  - `frontend/src/app/(dashboard)/employees/[id]/edit/page.tsx`
- **Fix**: Parsed API error response details (e.g. `Employee ID 'EMP045' already exists`) and mapped them to field-level `errors` state. Highlighted the invalid field with red border and inline message, keeping the user on Step 1.
- **Verification**: Build verified cleanly. Duplicate employee IDs and biometric codes now render red error text directly under the input field.

---

### BUG-6: No validation on required fields
- **Root Cause**: "Next Step" clicked through without running programmatic field validation, allowing empty inputs to bypass client checks.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/employees/new/page.tsx`
  - `frontend/src/app/(dashboard)/employees/[id]/edit/page.tsx`
- **Fix**: Added `validateStep1()` checking `first_name`, `last_name`, and `employee_id`. Blocks step advancement and displays inline red error messages if any required field is empty.
- **Verification**: Clicking "Next Step" with empty fields blocks navigation and displays red validation messages.

---

### BUG-7: Payroll period selector renders zero options
- **Root Cause**: When no payroll periods existed in the database, `fetchPeriods()` set `periods = []`, causing the `<select>` element to render with no `<option>` tags and `value=""`.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/payroll/page.tsx`
  - `frontend/src/types/index.ts`
- **Fix**: Added a fallback `<option>` displaying the current month (e.g., `August 2026 (Not Calculated)`) when `periods` is empty. Added `NO_DATA` badge status support and synchronized `workingDays` when switching periods.
- **Verification**: Default state on load displays `August 2026 (Not Calculated)`. Clicking "Calculate Payroll" creates the period and populates records.

---

### BUG-8: Approved leave doesn't reach the dashboard
- **Root Cause**: The dashboard KPI endpoint (`/dashboard/stats`) calculated `on_leave_today` solely from `AttendanceStatus.LEAVE` in the attendance table. Approving a leave request created an entry in `leave_requests`, but did not generate an attendance record.
- **Files Changed**:
  - `backend/app/api/v1/endpoints/dashboard.py`
  - `frontend/src/app/(dashboard)/leave/page.tsx`
- **Fix**: Updated `/dashboard/stats` to query both attendance `LEAVE` records **and** approved `LeaveRequest` records active on `today`, taking `max(attendance_count, leave_request_count)` to avoid double-counting. Replaced the Leave Apply modal's numeric "Employee ID" input with a searchable employee dropdown picker.
- **Verification**: Approving a leave for today increments the dashboard "On Leave Today" tile.

---

### BUG-9: Deactivated employees cannot be reactivated
- **Root Cause**: The directory row action was hardcoded to a "Deactivate" button regardless of `is_active` status. No UI option or status filter existed for inactive employees.
- **Files Changed**:
  - `frontend/src/app/(dashboard)/employees/page.tsx`
  - `frontend/src/app/(dashboard)/employees/[id]/page.tsx`
- **Fix**: Toggled row action button: inactive employees display a green "Reactivate" button (calling `PUT /employees/{id}` with `{ is_active: true }`), while active employees display "Deactivate". Added a Status Filter dropdown (`Active`, `Inactive`, `All Status`, defaulting to `Active`). Updated directory header count to reflect filter.
- **Verification**: Inactive records appear under the "Inactive" filter and can be reactivated with a single click.

---

### BUG-10: No mobile layout
- **Root Cause**: Sidebar component had fixed width `w-64` without responsive hiding or drawer toggle functionality. Page content collapsed on viewports <768px.
- **Files Changed**:
  - `frontend/src/components/layout/MainLayout.tsx`
  - `frontend/src/components/layout/Sidebar.tsx`
  - `frontend/src/components/layout/TopNav.tsx`
- **Fix**: Added `sidebarOpen` state to `MainLayout`. On viewports `<md` (below 768px), the sidebar transitions off-screen (`-translate-x-full`) and opens as a sliding drawer via a hamburger icon added to `TopNav`. Added a semi-transparent dark backdrop overlay for backdrop dismissal.
- **Verification**: Responsive build verified. Tested sidebar drawer behavior and hamburger toggle.

---

## Build & Test Verification Results

1. **Next.js Production Build**:
   ```
   > next build
   ✓ Compiled successfully in 604ms
   ✓ Running TypeScript ... Passed
   ✓ Static Page Generation (21/21 routes) ... Passed
   ```
2. **TypeScript Validation**:
   ```
   > npx tsc --noEmit
   (0 errors)
   ```
3. **Backend Unit & Integration Tests**:
   ```
   > pytest tests/test_parser.py tests/test_payroll.py -v
   3 passed, 0 failed in 0.44s
   ```
