# Monthly Attendance Import & Payroll Guide (eSSL Biometric)

This guide explains step-by-step how to export attendance from the eSSL biometric attendance system, import it into the SPT Hospital HRMS, resolve employee mappings, and calculate monthly payroll.

---

## 1. Exporting from eSSL Biometric Software

1. Open your **eSSL Biometric Attendance Software** (eTimeTrack / SmartOffice).
2. Go to **Reports** &rarr; **Monthly Reports** &rarr; **Monthly Status Report (Basic Report)**.
3. Select the period:
   - **Start Date**: 1st of the month (e.g., `01/09/2026`)
   - **End Date**: Last day of the month (e.g., `30/09/2026`)
4. Select all departments and companies (both **SPT** and **Old Bio** if applicable).
5. Click **View / Generate Report**.
6. Ensure the report displays:
   - Header with period: `Sep 01 2026 To Sep 30 2026`
   - Employee columns: `Sl`, `Emp. Code`, `Name`, followed by day columns `1` to `30`/`31` (`P`, `A`, `L`, `H`, `HP`, `WO`, `WOP`), and totals columns `P`, `A`, `L`, `H`, `HP`, `WO`, `WOP`.
7. Click **Export** &rarr; **Acrobat (PDF) file** and save it (e.g., `SPE26_MONTHLY_REPORTS.pdf`).

---

## 2. Uploading via Attendance Import Wizard

1. Log into SPT Hospital HRMS.
2. Navigate to **Attendance** &rarr; **Import Attendance** (`/attendance/import`).
3. **Step 1: Upload File**:
   - Drag and drop or browse to select your exported eSSL PDF file.
   - Click **Upload & Preview**.
4. The system automatically inspects the PDF:
   - **Period Detection**: Extracted directly from the PDF header (e.g., `September 2026`). If this period differs from your system's current date, an informative banner will alert you.
   - **Report Type Detection**: Auto-detects whether the report is a *Monthly Status Report (Basic Report)* (summary codes without punch timestamps) or a *Detailed Punch Log*.
   - **Checksum Verification**: Recomputes all daily cells (`P`, `A`, `L`, `H`, `HP`, `WO`, `WOP`) against printed summary totals to ensure 100% data integrity.
   - **Payroll Lock Check**: If payroll for the detected month is already `FINALIZED`, the import is safely blocked to protect financial records.

---

## 3. Resolving Review Screen Rows (Step 3)

The wizard categorizes all detected employee rows into four distinct statuses:

| Status Badge | Meaning | Recommended Action |
| :--- | :--- | :--- |
| <span style="color: green; font-weight: bold;">MATCHED</span> | The biometric code and name match an existing active employee in HRMS. | Default: **Link** (no action needed). |
| <span style="color: orange; font-weight: bold;">NAME MISMATCH</span> | Biometric code matches an employee in the system, but the name in the PDF differs (e.g., Code 64: PDF has "Kiruthika", system has "DR Saranya"). | Choose whether to **Link** to the matched employee or select another staff member from the dropdown. Enable **"Save as Alias"** to remember this mapping for future months. |
| <span style="color: blue; font-weight: bold;">NEW EMPLOYEE</span> | Biometric code is not yet found in the HRMS master database (e.g., Code 65: "Latha"). | Choose **Create New Employee** (system auto-populates their name and department), or **Link** to an existing staff member. |
| <span style="color: gray; font-weight: bold;">DUPLICATE SUSPECT</span> | Secondary device entry (e.g., Old Bio codes 208–210) where an employee has all-absent records or duplicate punches. | Default: **Ignore** (safely skipped so secondary records don't overwrite primary attendance). |

### Biometric Code Aliases
If an employee has different codes across devices (e.g., Old Bio vs. SPT main biometric device):
- Check **"Save as Alias"** during review.
- The system saves this in the `Device Code Aliases` table. Future monthly imports will automatically resolve this employee without prompting.
- You can manage existing aliases anytime under **Settings** &rarr; **Device Code Aliases** (`/settings/aliases`).

---

## 4. Multi-Device Consolidation Priority

When an employee has records from multiple devices on the same day, the system consolidates them using this precedence order:
$$\text{P (Present)} > \text{WOP (Weekly Off Present)} > \text{HP (Half Day)} > \text{WO (Weekly Off)} > \text{H (Holiday)} > \text{L (Leave)} > \text{A (Absent)} > \text{NO\_DATA}$$

Empty cells before an employee's joining date are recorded as `NO_DATA`. They are **never** treated as Absent or Loss of Pay.

---

## 5. Reviewing Coverage and Calculating Payroll

1. Once the import is committed, click **"Calculate Payroll for [Month Year]"** directly on the success screen.
2. In the **Monthly Payroll & Salary Calculator** (`/payroll`):
   - **Attendance Coverage Card**: Shows how many active staff members have imported attendance (e.g., `45 of 47 employees • 95.7%`).
   - **Notice Banner**: For basic status reports, a notice clarifies: *"Lateness data unavailable — imported from monthly status report. LOP from lateness is not applied."*
   - **Paid Leave Rule**: The first **3 leave days** are fully paid (`Paid Leave = min(Leave, 3)`). Only unworked absences beyond 3 days generate Loss of Pay (LOP) deductions.
   - **Mid-Month Joiners**: Payable days are strictly capped by days active (e.g., an employee joining on the 30th gets 1 payable day, not 0 and not 30).
   - **Finalize Guard**: If attendance coverage is incomplete, the system prompts with a warning before allowing finalization.
