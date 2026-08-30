# Manual Salary Calculator Formula & Salary Migration Documentation

This document records the exact reverse-engineered formula from the hospital's live manual salary calculator, the automated unit test suite results, the 3-way salary migration reconciliation report, and verification that manual overrides survive attendance re-imports.

---

## 1. Implemented Salary Calculator Formula

For any selected month (`year`, `month`):

$$ \text{daysInMonth} = \text{calendar days in selected month} \quad (28, 29, 30, \text{ or } 31) $$
$$ \text{perDay} = \frac{\text{baseSalary}}{\text{daysInMonth}} $$
$$ \text{payableDays} = \min(\text{presentDays}, \text{daysInMonth}) + (\text{halfDays} \times 0.5) + \min(\text{leaveDays}, 3) + \text{offDutyDays} $$
$$ \text{salaryPart} = \min(\text{payableDays} \times \text{perDay}, \text{baseSalary}) $$
$$ \text{totalSalary} = \text{salaryPart} + \text{collection} $$

### Key Rules Verified
1. **Per-Day Rate**: Divides by calendar days of the month (e.g. 31 for Aug, 30 for Sep, 28/29 for Feb).
2. **Half Days**: Counted as exactly $0.5$ days.
3. **Paid Leave**: Capped at maximum 3 days per month. Leave beyond day 3 is unpaid.
4. **Off Duty**: Fully paid and uncapped.
5. **Base Salary Cap**: `salaryPart` is capped at $100\%$ of `baseSalary`.
6. **Collection**: Added to salary after base cap, paid even if payable days is 0. Cumulative lifetime collection is tracked per employee across months.

---

## 2. Unit Test Results (`test_manual_salary_calculator.py`)

All 16 experimental test cases + February leap year cases passed:

| Month (Days) | Present | Half | Leave | Off Duty | Collection (₹) | Expected Payable | Expected Total (₹) | Status |
|---|---|---|---|---|---|---|---|---|
| **Aug (31)** | 30 | 0 | 0 | 0 | 0 | 30.0 | ₹19,354.84 | ✅ PASSED |
| **Aug (31)** | 20 | 0 | 0 | 0 | 0 | 20.0 | ₹12,903.23 | ✅ PASSED |
| **Aug (31)** | 20 | 2 | 0 | 0 | 0 | 21.0 | ₹13,548.39 | ✅ PASSED |
| **Aug (31)** | 20 | 1 | 0 | 0 | 0 | 20.5 | ₹13,225.81 | ✅ PASSED |
| **Aug (31)** | 20 | 0 | 3 | 0 | 0 | 23.0 | ₹14,838.71 | ✅ PASSED |
| **Aug (31)** | 20 | 0 | 5 | 0 | 0 | 23.0 | ₹14,838.71 | ✅ PASSED |
| **Aug (31)** | 20 | 0 | 0 | 4 | 0 | 24.0 | ₹15,483.87 | ✅ PASSED |
| **Aug (31)** | 20 | 0 | 0 | 0 | 1,000 | 20.0 | ₹13,903.23 | ✅ PASSED |
| **Aug (31)** | 31 | 0 | 0 | 0 | 0 | 31.0 | ₹20,000.00 | ✅ PASSED |
| **Aug (31)** | 40 | 0 | 0 | 0 | 0 | 31.0 | ₹20,000.00 | ✅ PASSED |
| **Aug (31)** | 25 | 3 | 3 | 2 | 500 | 31.5 | ₹20,500.00 | ✅ PASSED |
| **Aug (31)** | 0 | 0 | 3 | 0 | 0 | 3.0 | ₹1,935.48 | ✅ PASSED |
| **Aug (31)** | 0 | 0 | 0 | 0 | 2,500 | 0.0 | ₹2,500.00 | ✅ PASSED |
| **Sep (30)** | 30 | 0 | 0 | 0 | 0 | 30.0 | ₹20,000.00 | ✅ PASSED |
| **Sep (30)** | 15 | 0 | 0 | 0 | 0 | 15.0 | ₹10,000.00 | ✅ PASSED |
| **Sep (30)** | 31 | 0 | 0 | 0 | 0 | 30.0 | ₹20,000.00 | ✅ PASSED |
| **Feb 2028 (29)** | 29 | 0 | 0 | 0 | 0 | 29.0 | ₹20,000.00 | ✅ PASSED |

---

## 3. Salary Migration — 3-Way Reconciliation Report

### Summary
- **Total Staff in Old Manual Calculator**: 55
- **Total Staff Matched & Migrated**: 48
- **Present Only in Old Calculator / Disambiguation Pairs**: 7
- **Present Only in HRMS**: 17

---

### Category A: Matched Staff (48 Staff — Base Salaries Migrated)

| # | Calculator Name | Department / Role | Base Salary (₹) | Matched HRMS Employee | Biometric Code |
|---|---|---|---|---|---|
| 1 | Senthilmurugan | Manager | 20,000 | SPT6 Senthil Murugan | 6 |
| 2 | Sudha | Receptionist | 14,000 | SPT7 Sudha | 7 |
| 3 | Thenmozhi | Receptionist | 14,000 | SPT8 Thenmozhi | 8 |
| 4 | Viji | Receptionist | 16,000 | SPT9 Viji | 9 |
| 5 | Lavanya | Receptionist | 12,000 | SPT10 Lavanya | 10 |
| 6 | Karthika | Receptionist | 11,000 | SPT11 Karthika | 11 |
| 7 | Basheer Mohamed | Pharmacist | 15,000 | SPT14 Basheer Mohamed | 14 |
| 8 | Syed Sajith | Pharmacist | 13,000 | SPT15 Syed Sajith | 15 |
| 9 | Aarthi | Pharmacist | 14,000 | SPT13 Aarthi G | 13 |
| 10 | Ananthi | Lab Technician | 18,000 | SPT16 Ananthi | 16 |
| 11 | Lavanya | Lab Technician | 14,000 | SPT18 Lavanya | 18 |
| 12 | Priyadharshini | Lab Technician | 14,000 | SPT17 Priyadharshini | 17 |
| 13 | Sathya LAB | Lab Technician | 15,000 | SPT19 Sathya | 19 |
| 14 | Nilavazhagan | X-ray Technician | 15,000 | SPT20 Nilavazhagan | 20 |
| 15 | Meerasha | Staff | 14,000 | SPT21 Meerasha | 21 |
| 16 | Vasanthi | Staff | 18,000 | SPT22 Vasanthi | 22 |
| 17 | Maheshwari | Staff | 13,000 | SPT23 Maheshwari | 23 |
| 18 | Aarthi | Staff | 13,000 | SPT24 Aarthi S | 24 |
| 19 | Abinaya | Staff | 13,000 | SPT29 Abinaya | 29 |
| 20 | Praveena | Staff | 13,000 | SPT32 Praveena | 32 |
| 21 | Makisha | Staff | 10,000 | SPT30 Makisha Kasani | 30 |
| 22 | Gobika J | Staff | 10,000 | SPT34 Gobika | 34 |
| 23 | Vijayalakshmi | Staff | 14,000 | SPT27 Vijayalakshmi | 27 |
| 24 | Sangeetharani | Staff | 12,000 | SPT26 Sangeetharani | 26 |
| 25 | Logeswari | Staff | 10,000 | SPT37 Logeshwari | 37 |
| 26 | Dharshini | Staff | 11,000 | SPT31 Dharshini | 31 |
| 27 | Naveen | Staff | 20,000 | SPT40 Naveen | 40 |
| 28 | Ganesh | Staff | 20,000 | SPT39 Ganesh | 39 |
| 29 | Jagadeeshwaran | Staff | 14,000 | SPT41 Jagathishwaran | 41 |
| 30 | Madesh | Staff | 15,000 | SPT42 Madesh | 42 |
| 31 | Kalyani | Staff | 16,000 | SPT28 Kalyani | 28 |
| 32 | Parimala | House Keeping | 11,500 | SPT47 Parimala | 47 |
| 33 | Dhanalakshmi | House Keeping | 11,500 | SPT48 Dhanalakshmi | 48 |
| 34 | Boopathi | House Keeping | 11,500 | SPT49 Boopathi | 49 |
| 35 | Mahalakshmi | House Keeping | 10,500 | SPT50 Mahalakshmi | 50 |
| 36 | Logeshwari | House Keeping | 10,500 | SPT53 Logeshwari HK | 53 |
| 37 | Gnana Soundari | House Keeping | 9,500 | SPT56 Gnanasundari | 56 |
| 38 | Rajeshwari | House Keeping | 10,500 | SPT54 Rajeshwari | 54 |
| 39 | Annakili | House Keeping | 10,500 | SPT51 Annakili | 51 |
| 40 | Sarala | House Keeping | 13,000 | SPT46 Sarala | 46 |
| 41 | Sathyapriya | House Keeping | 10,000 | SPT52 Sathyapriya | 52 |
| 42 | Selvi | House Keeping | 10,000 | SPT55 Selvi | 55 |
| 43 | Chinnadurai | Watchman | 12,000 | SPT59 Chinnadurai | 59 |
| 44 | Ramasamy | Watchman | 14,000 | SPT57 Ramasamy | 57 |
| 45 | Periyasamy | Security | 13,000 | SPT58 Periyasamy | 58 |
| 46 | Tamilmaran | Driver | 20,000 | SPT60 Tamilmaran | 60 |
| 47 | Murugesan | Shifting | 13,000 | SPT45 Murugesan | 45 |
| 48 | Sadiq Basha | Shifting | 13,000 | SPT44 Shathiq Basha | 44 |

---

### Category B: Present Only in Old Calculator / Owner Resolution Required (7 Staff)

| # | Old Calculator Name | Role | Salary (₹) | Reason / Note |
|---|---|---|---|---|
| 1 | Bhuvaneshwari | Pharmacist | 14,000 | Inactive in DB (`EMP12`, bio `9912`) |
| 2 | Lavanya J | Staff | 10,000 | Distinct Lavanya entry in Nursing |
| 3 | Sharshini | Staff | 10,000 | Spelling collision / not in biometric series |
| 4 | Gopika | Staff | 15,000 | Distinct from Gobika J |
| 5 | Jothivel | Staff | 16,000 | Not present in biometric device export |
| 6 | Nalayini | Staff | 10,000 | Not present in biometric device export |
| 7 | Savithiri | House Keeping | 9,500 | Not present in biometric device export |

---

### Category C: Present Only in HRMS (17 Staff)

| # | Code | Biometric Code | Name | Department |
|---|---|---|---|---|
| 1 | SPT1 | 1 | Dr Manoj | DOCTOR |
| 2 | SPT2 | 2 | Dr Periyasamy | DOCTOR |
| 3 | SPT64 | 64 | Dr Saranya | DOCTOR |
| 4 | SPT3 | 3 | Dt Santhiya | HR |
| 5 | SPT33 | 33 | Senthamilselvi | NURSING |
| 6 | SPT61 | 61 | Saran | NURSING |
| 7 | SPT62 | 62 | Selladurai | NURSING |
| 8 | SPT63 | 63 | Ashwin | PHARMACY |
| 9 | SPT201 | 201 | Senthil Murugan (Old Bio) | MANAGER |
| 10 | SPT202 | 202 | Madesh (Old Bio) | NURSING |
| 11 | SPT203 | 203 | Jagathish (Old Bio) | NURSING |
| 12 | SPT204 | 204 | Ganesh (Old Bio) | NURSING |
| 13 | SPT206 | 206 | Naveen (Old Bio) | NURSING |
| 14 | SPT207 | 207 | Murugesan (Old Bio) | Default |
| 15 | SPT208 | 208 | Saran (Old Bio) | NURSING |
| 16 | SPT209 | 209 | Selladurai (Old Bio) | NURSING |
| 17 | SPT210 | 210 | Abinaya (Old Bio) | NURSING |

---

## 4. Manual Override Survival Verification

Tested and confirmed:
1. **Manual Inputs**: Editing `present_days`, `half_days`, `leave_days`, `off_duty_days`, or `collection` sets `is_manual_override = True`.
2. **Attendance Import Re-run**: Executing `calculate_all_employees` or re-importing biometric PDFs preserves the overridden figures and does not overwrite manual inputs.
