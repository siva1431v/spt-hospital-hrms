# SPT Hospital HRMS — Real Hospital Shift Structure Setup & Assignment Report (`FIXES_SHIFTS.md`)

This document details the schema design decision for split shifts, the migration of the hospital owner's real 8-shift roster, the employee shift assignment results, and verification metrics.

---

## 1. Split Shift Architecture Decision & Rationale

We chose **Option (b)**: Extended the `Shift` model with dual time window fields (`start_time_2`, `end_time_2`, `is_overnight_2`) and an `is_split` boolean flag.

### Why Option (b)?
1. **Single Assignment Model**: Employees in split/rotating departments (Lab, Housekeeping, Security) remain assigned to a single shift entity (e.g. `LAB_SPLIT`, `HK_SPLIT`, or `SEC_SPLIT`). HR does not need to manually swap shift assignments back and forth every week when staff rotate between day and night patterns.
2. **Dual-Window Automatic Evaluation**: Shift evaluation logic (`evaluate_shift_punch` in `app/utils/shift_utils.py`) dynamically compares an employee's check-in punch against both Window 1 (Day pattern) and Window 2 (Night pattern). It automatically evaluates late status and anomaly detection against the window closest to the check-in time. For example, an 18:40 PM check-in for a Housekeeping split worker matches Window 2 (18:30–08:30) and is marked on-time (within the 15-minute grace period) rather than an anomaly.
3. **Clean UI & Schema**: `/shifts` renders both Window 1 and Window 2 for split shifts in a unified card, while legacy dropdowns continue working seamlessly.

---

## 2. The 8 Real Hospital Shifts

| Shift Code | Shift Name | Timing (Window 1) | Timing (Window 2 - Split) | Notes |
|---|---|---|---|---|
| `GS` | General (Day) | 09:30 AM – 8:00 PM | — | Doctors, admin, nursing, support staff |
| `S2` | Shift II | 10:00 AM – 8:30 PM | — | Pharmacy, Nursing, Lab, X-Ray |
| `S3` | Shift III | 09:30 AM – 7:00 PM | — | Nursing, Driver |
| `S4` | Shift IV | 08:30 AM – 6:00 PM | — | Medical (Pharmacy) |
| `LAB_SPLIT` | Lab Split | Morning 07:30 AM – 5:30 PM | Night 06:30 PM – 9:30 AM (Overnight) | Split/rotating shift for Lab |
| `HK_SPLIT` | House Keeping Split | Morning 08:30 AM – 6:30 PM | Night 06:30 PM – 8:30 AM (Overnight) | Split/rotating shift for Housekeeping |
| `SEC_SPLIT` | Security Split | Morning 08:00 AM – 5:00 PM | Night 05:00 PM – 8:00 AM (Overnight) | Split/rotating shift for Security |
| `DIET` | Dietitian | 09:30 AM – 7:00 PM | — | Dietitian |

---

## 3. Employee Roster Assignment Results

- **Total Active Employees Processed**: 65
- **Successfully Assigned to Real Shifts**: 47
- **Left Unassigned (Unresolved Collisions / Unlisted)**: 18
- **Legacy Seeded Shifts Deactivated**: 10 (IDs 1, 2, 3, 5, 6, 7, 8, 9, 10, 11)

### A. Successfully Assigned Employees (47)

#### Shift I — General (Day) (`GS`) — 20 Employees
- **Doctors (3)**: Dr Manoj (Bio 1), Dr Periyasamy (Bio 2), Dr Saranya (Bio 64)
- **Reception (5)**: Sudha (Bio 7), Thenmozhi (Bio 8), Viji (Bio 9), Lavanya (Bio 10), Karthika (Bio 11)
- **Pharmacy (2)**: Bhuvaneshwari (Bio 12), Ashwin (Bio 63)
- **Nursing (6)**: Praveena (Bio 32), Maheshwari (Bio 23), Aarthi S (Bio 24), Kalyani (Bio 28), Jagathishwaran (Bio 41), Sangeetharani (Bio 26)
- **Lab (2)**: Priyadharshini (Bio 17), Sathya (Bio 19)
- **X-Ray (1)**: Nilavazhagan (Bio 20)
- **Security (1)**: Shathiq Basha (Bio 44)

#### Shift II (`S2`) — 6 Employees
- Basheer Mohamed (Bio 14, Pharmacy), Syed Sajith (Bio 15, Pharmacy), Meerasha (Bio 21, X-Ray), Ananthi (Bio 16, Lab), Vasanthi (Bio 22, Nursing), Vijayalakshmi (Bio 27, Nursing)

#### Shift III (`S3`) — 5 Employees
- Makisha Kasani (Bio 30, Nursing), Dharshini (Bio 31, Nursing), Gobika (Bio 34, Nursing), Logeshwari (Bio 37, Nursing), Tamilmaran (Bio 60, Driver)

#### Shift IV (`S4`) — 1 Employee
- Aarthi G (Bio 13, Pharmacy/Med)

#### Shift V — Lab Split (`LAB_SPLIT`) — 1 Employee
- Lavanya (Bio 18, Lab) — *Disambiguated from Reception Lavanya (Bio 10) using department context.*

#### Shift VI — House Keeping Split (`HK_SPLIT`) — 12 Employees
- Sarala (Bio 46), Parimala (Bio 47), Dhanalakshmi (Bio 48), Boopathi (Bio 49), Mahalakshmi (Bio 50), Annakili (Bio 51), Sathyapriya (Bio 52), Logeshwari HK (Bio 53), Rajeshwari (Bio 54), Selvi (Bio 55), Gnanasundari (Bio 56), Chinnadurai (Bio 59)

#### Shift VII — Security Split (`SEC_SPLIT`) — 2 Employees
- Ramasamy (Bio 57), Periyasamy (Bio 58) — *Disambiguated from Dr. Periyasamy (Bio 2, Doctor) using department context.*

#### Shift VIII — Dietitian (`DIET`) — 1 Employee
- Dt Santhiya (Bio 3, HR/Dietitian) — *Matches roster entry "Parthiya M / Sarthiya M".*

---

### B. Unresolved Collisions List (Left Unassigned) (16 Employee Records)

Per the strict directives in the prompt ("match by department context first... and if more than one employee record still matches after that filter, leave it unassigned and list it in your FIXES writeup rather than picking one arbitrarily"), the following 8 duplicate pairs (16 employee records) remain unassigned (`shift_id = NULL`) pending owner confirmation:

| Name | Duplicate Records in DB | Department Context | Status | Reason |
|---|---|---|---|---|
| **Senthil Murugan** | SPT6 (Bio 6) vs SPT201 (Bio 201) | Both `MANAGER` | Unassigned | Both records share name & department; biometric code choice requires confirmation |
| **Naveen** | SPT40 (Bio 40) vs SPT206 (Bio 206) | Both `NURSING` | Unassigned | Both records share name & department; biometric code choice requires confirmation |
| **Saran** | SPT61 (Bio 61) vs SPT208 (Bio 208) | Both `NURSING` | Unassigned | Both records share name & department; biometric code choice requires confirmation |
| **Madesh** | SPT42 (Bio 42) vs SPT202 (Bio 202) | Both `NURSING` | Unassigned | Both records share name & department; biometric code choice requires confirmation |
| **Selladurai** | SPT62 (Bio 62) vs SPT209 (Bio 209) | Both `NURSING` | Unassigned | Both records share name & department; biometric code choice requires confirmation |
| **Ganesh** | SPT39 (Bio 39) vs SPT204 (Bio 204) | Both `NURSING` | Unassigned | Both records share name & department; biometric code choice requires confirmation |
| **Abinaya** | SPT29 (Bio 29) vs SPT210 (Bio 210) | Both `NURSING` | Unassigned | Both records share name & department; biometric code choice requires confirmation |
| **Murugesan** | SPT45 (Bio 45, Security) vs SPT207 (Bio 207, Default) | `SECURITY` / `Default` | Unassigned | Roster lists Murugesan under Shift I (General), while Bio 45 is in Security; ambiguous match |

### C. Unlisted Active Employees (2 Records)
- **Jagathish** (SPT203, Bio 203, Nursing): Unlisted in roster sheet (Roster has Jagathishwaran Bio 41).
- **Senthamilselvi** (SPT33, Bio 33, Nursing): Unlisted in roster sheet.

---

## 4. Legacy Shift Preservation & Verification Results

1. **Legacy Shift Deactivation**: All 10 legacy generic shifts (IDs 1, 2, 3, 5, 6, 7, 8, 9, 10, 11) have been set `is_active = False`. Existing attendance records maintain foreign key integrity.
2. **Backend Test Suite**: `9/9 passed (100%)` (`PYTHONPATH=. pytest tests/ -v`).
3. **TypeScript Compilation**: `npx tsc --noEmit` passed cleanly with 0 errors.
4. **Next.js Production Build**: `21/21 routes compiled successfully` (`npm run build`).
5. **Backend Server Status**: Server active on `http://127.0.0.1:8000`.
