"""
SPT Hospital HRMS — Employee Shift Migration Script
Migrates employees to the 8 real hospital shifts based on written roster.
"""
import asyncio
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.shift import Shift

ROSTER_BIO_TO_SHIFT_CODE = {
    # Shift I — General (Day) [GS]
    "1": "GS",   # DR Manoj (DOCTOR)
    "2": "GS",   # DR Periyasamy (DOCTOR)
    "64": "GS",  # DR Saranya (DOCTOR)
    "7": "GS",   # Sudha (RECEPTION)
    "8": "GS",   # Thenmozhi (RECEPTION)
    "9": "GS",   # Viji (RECEPTION)
    "10": "GS",  # Lavanya (RECEPTION)
    "11": "GS",  # Karthika (RECEPTION)
    "12": "GS",  # Bhuvaneshwari (PHARMACY)
    "32": "GS",  # Praveena (NURSING)
    "17": "GS",  # Priyadharshini (LAB)
    "19": "GS",  # Sathya (LAB)
    "20": "GS",  # Nilavazhagan (X RAY)
    "23": "GS",  # Maheshwari (NURSING)
    "24": "GS",  # Aarthi S (NURSING)
    "28": "GS",  # Kalyani (NURSING)
    "41": "GS",  # Jagathishwaran (NURSING)
    "26": "GS",  # Sangeetharani (NURSING)
    "44": "GS",  # Shathiq Basha (SECURITY)
    "63": "GS",  # Ashwin (PHARMACY)

    # Shift II — Shift II [S2]
    "14": "S2",  # Basheer Mohamed (PHARMACY)
    "15": "S2",  # Syed Sajith (PHARMACY)
    "21": "S2",  # Meerasha (X RAY)
    "16": "S2",  # Ananthi (LAB)
    "22": "S2",  # Vasanthi (NURSING)
    "27": "S2",  # Vijayalakshmi (NURSING)

    # Shift III — Shift III [S3]
    "30": "S3",  # Makisha Kasani (NURSING)
    "31": "S3",  # Dharshini (NURSING)
    "34": "S3",  # Gobika (NURSING)
    "37": "S3",  # Logeshwari (NURSING)
    "60": "S3",  # Tamilmaran (DRIVER)

    # Shift IV — Shift IV [S4]
    "13": "S4",  # Aarthi G (PHARMACY / Med)

    # Shift V — Lab Split [LAB_SPLIT]
    "18": "LAB_SPLIT",  # Lavanya (LAB)

    # Shift VI — House Keeping Split [HK_SPLIT]
    "46": "HK_SPLIT",  # Sarala (HOUSE KEEPING)
    "47": "HK_SPLIT",  # Parimala (HOUSE KEEPING)
    "48": "HK_SPLIT",  # Dhanalakshmi (HOUSE KEEPING)
    "49": "HK_SPLIT",  # Boopathi (HOUSE KEEPING)
    "50": "HK_SPLIT",  # Mahalakshmi (HOUSE KEEPING)
    "51": "HK_SPLIT",  # Annakili (HOUSE KEEPING)
    "52": "HK_SPLIT",  # Sathyapriya (HOUSE KEEPING)
    "53": "HK_SPLIT",  # Logeshwari HK (HOUSE KEEPING)
    "54": "HK_SPLIT",  # Rajeshwari (HOUSE KEEPING)
    "55": "HK_SPLIT",  # Selvi (HOUSE KEEPING)
    "56": "HK_SPLIT",  # Gnanasundari (HOUSE KEEPING)
    "59": "HK_SPLIT",  # Chinnadurai (SECURITY / HK)

    # Shift VII — Security Split [SEC_SPLIT]
    "57": "SEC_SPLIT",  # Ramasamy (SECURITY)
    "58": "SEC_SPLIT",  # Periyasamy (SECURITY)

    # Shift VIII — Dietitian [DIET]
    "3": "DIET",  # Dt Santhiya (HR / Dietitian)
}

REAL_SHIFT_CODES = ["GS", "S2", "S3", "S4", "LAB_SPLIT", "HK_SPLIT", "SEC_SPLIT", "DIET"]

async def migrate_employee_shifts():
    async with AsyncSessionLocal() as db:
        # Load shifts mapping (code -> Shift object)
        shifts_res = await db.execute(select(Shift))
        shifts_by_code = {s.code: s for s in shifts_res.scalars().all()}

        # Load active employees
        emps_res = await db.execute(
            select(Employee).options(selectinload(Employee.department)).where(Employee.is_active == True)
        )
        active_employees = emps_res.scalars().all()

        assigned_count = 0
        unassigned_list = []

        for emp in active_employees:
            bio = str(emp.biometric_code) if emp.biometric_code else None
            if bio and bio in ROSTER_BIO_TO_SHIFT_CODE:
                shift_code = ROSTER_BIO_TO_SHIFT_CODE[bio]
                target_shift = shifts_by_code[shift_code]
                emp.shift_id = target_shift.id
                assigned_count += 1
            else:
                emp.shift_id = None
                dept_name = emp.department.name if emp.department else "NONE"
                unassigned_list.append((emp.employee_id, bio, emp.full_name, dept_name))

        # Deactivate legacy shifts not in the 8 real shifts
        legacy_deactivated = 0
        for code, shift_obj in shifts_by_code.items():
            if code not in REAL_SHIFT_CODES:
                shift_obj.is_active = False
                legacy_deactivated += 1

        await db.commit()

        print("==================================================")
        print(" EMPLOYEE SHIFT MIGRATION COMPLETED")
        print("==================================================")
        print(f"Total Active Employees Processed: {len(active_employees)}")
        print(f"Successfully Assigned to Real Shifts: {assigned_count}")
        print(f"Left Unassigned (Collisions / Unlisted): {len(unassigned_list)}")
        print(f"Legacy Seeded Shifts Deactivated: {legacy_deactivated}")
        print("\n--- UNASSIGNED EMPLOYEES REPORT ---")
        for item in unassigned_list:
            print(f"EmpID: {item[0]:7s} | Bio: {str(item[1]):5s} | Name: {item[2]:22s} | Dept: {item[3]}")

if __name__ == "__main__":
    asyncio.run(migrate_employee_shifts())
