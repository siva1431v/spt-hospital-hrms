"""
SPT Hospital HRMS — Base Salary Migration & 3-Way Reconciliation Script
Migrates the 55 real base salaries from the live manual calculator into HRMS.
"""
import sqlite3
import os

OLD_CALCULATOR_STAFF = [
    ('Senthilmurugan', 'Manager', 20000.0),
    ('Sudha', 'Receptionist', 14000.0),
    ('Thenmozhi', 'Receptionist', 14000.0),
    ('Viji', 'Receptionist', 16000.0),
    ('Lavanya', 'Receptionist', 12000.0),
    ('Karthika', 'Receptionist', 11000.0),
    ('Basheer Mohamed', 'Pharmacist', 15000.0),
    ('Bhuvaneshwari', 'Pharmacist', 14000.0),
    ('Syed Sajith', 'Pharmacist', 13000.0),
    ('Aarthi', 'Pharmacist', 14000.0),
    ('Ananthi', 'Lab Technician', 18000.0),
    ('Lavanya', 'Lab Technician', 14000.0),
    ('Priyadharshini', 'Lab Technician', 14000.0),
    ('Sathya LAB', 'Lab Technician', 15000.0),
    ('Nilavazhagan', 'X-ray Technician', 15000.0),
    ('Lavanya J', 'Staff', 10000.0),
    ('Vasanthi', 'Staff', 18000.0),
    ('Abinaya', 'Staff', 13000.0),
    ('Maheshwari', 'Staff', 13000.0),
    ('Aarthi', 'Staff', 13000.0),
    ('Praveena', 'Staff', 13000.0),
    ('Makisha', 'Staff', 1000.0),
    ('Gobika J', 'Staff', 10000.0),
    ('Sharshini', 'Staff', 10000.0),
    ('Gopika', 'Staff', 15000.0),
    ('Vijayalakshmi', 'Staff', 14000.0),
    ('Sangeetharani', 'Staff', 12000.0),
    ('Logeswari', 'Staff', 10000.0),
    ('Dharshini', 'Staff', 11000.0),
    ('Naveen', 'Staff', 20000.0),
    ('Ganesh', 'Staff', 20000.0),
    ('Jothivel', 'Staff', 16000.0),
    ('Nalayini', 'Staff', 10000.0),
    ('Jagadeeshwaran', 'Staff', 14000.0),
    ('Madesh', 'Staff', 15000.0),
    ('Meerasha', 'Staff', 14000.0),
    ('Parimala', 'House Keeping', 11500.0),
    ('Dhanalakshmi', 'House Keeping', 11500.0),
    ('Boopathi', 'House Keeping', 11500.0),
    ('Mahalakshmi', 'House Keeping', 10500.0),
    ('Logeshwari', 'House Keeping', 10500.0),
    ('Gnana Soundari', 'House Keeping', 9500.0),
    ('Rajeshwari', 'House Keeping', 10500.0),
    ('Annakili', 'House Keeping', 10500.0),
    ('Sarala', 'House Keeping', 13000.0),
    ('Chinnadurai', 'Watchman', 12000.0),
    ('Ramasamy', 'Watchman', 14000.0),
    ('Tamilmaran', 'Driver', 20000.0),
    ('Murugesan', 'Shifting', 13000.0),
    ('Sadiq Basha', 'Shifting', 13000.0),
    ('Kalyani', 'Staff', 16000.0),
    ('Savithiri', 'House Keeping', 9500.0),
    ('Sathyapriya', 'House Keeping', 10000.0),
    ('Selvi', 'House Keeping', 10000.0),
    ('Periyasamy', 'Security', 13000.0),
]

EXPLICIT_EMP_CODE_MAP = {
    ('Senthilmurugan', 'Manager'): 'SPT6',
    ('Aarthi', 'Pharmacist'): 'SPT13',
    ('Aarthi', 'Staff'): 'SPT24',
    ('Abinaya', 'Staff'): 'SPT29',
    ('Naveen', 'Staff'): 'SPT40',
    ('Ganesh', 'Staff'): 'SPT39',
    ('Jagadeeshwaran', 'Staff'): 'SPT41',
    ('Madesh', 'Staff'): 'SPT42',
    ('Meerasha', 'Staff'): 'SPT21',
    ('Murugesan', 'Shifting'): 'SPT45',
}

DEPT_MAP = {
    'Manager': 'MANAGER',
    'Receptionist': 'RECEPTION',
    'Pharmacist': 'PHARMACY',
    'Lab Technician': 'LAB',
    'X-ray Technician': 'X RAY',
    'Staff': 'NURSING',
    'House Keeping': 'HOUSE KEEPING',
    'Watchman': 'SECURITY',
    'Security': 'SECURITY',
    'Shifting': 'SECURITY',
    'Driver': 'DRIVER',
}

NAME_ALIASES = {
    'Sathya LAB': 'Sathya',
    'Sadiq Basha': 'Shathiq Basha',
    'Gnana Soundari': 'Gnanasundari',
    'Logeswari': 'Logeshwari',
    'Logeshwari': 'Logeshwari HK',
    'Gobika J': 'Gobika',
    'Makisha': 'Makisha Kasani',
}


def run_migration():
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'spt_hrms.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT e.id, e.employee_id, e.biometric_code, e.first_name, e.last_name, d.name as dept, e.basic_salary, e.is_active
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
    ''')
    hrms_emps = cursor.fetchall()
    emp_by_code = {e[1]: e for e in hrms_emps}

    matched = []
    unmatched_calculator = []
    matched_ids = set()

    for calc_name, calc_role, salary in OLD_CALCULATOR_STAFF:
        key = (calc_name, calc_role)
        if key in EXPLICIT_EMP_CODE_MAP:
            code = EXPLICIT_EMP_CODE_MAP[key]
            if code in emp_by_code:
                emp = emp_by_code[code]
                matched.append((calc_name, calc_role, salary, emp))
                matched_ids.add(emp[0])
                continue

        target_dept = DEPT_MAP.get(calc_role, calc_role)
        norm_name = NAME_ALIASES.get(calc_name, calc_name).lower().replace(' ', '')

        candidates = []
        for emp in hrms_emps:
            if emp[0] in matched_ids or not emp[7]:  # active only for heuristic
                continue
            emp_id, emp_code, bio_code, f_name, l_name, dept, _, _ = emp
            full_name = f'{f_name} {l_name or ""}'.strip()
            norm_full = full_name.lower().replace(' ', '')

            if (norm_name in norm_full or norm_full in norm_name) and (dept == target_dept or (target_dept == 'SECURITY' and dept in ['SECURITY', 'Default'])):
                candidates.append(emp)

        if len(candidates) == 1:
            emp = candidates[0]
            matched.append((calc_name, calc_role, salary, emp))
            matched_ids.add(emp[0])
        else:
            unmatched_calculator.append((calc_name, calc_role, salary, candidates))

    unmatched_hrms = [emp for emp in hrms_emps if emp[7] and emp[0] not in matched_ids]

    # Update basic salary for matched employees
    updated_count = 0
    for calc_name, calc_role, salary, emp in matched:
        cursor.execute('UPDATE employees SET basic_salary = ? WHERE id = ?', (salary, emp[0]))
        updated_count += cursor.rowcount

    conn.commit()
    conn.close()

    print(f'Successfully migrated {updated_count} base salaries to HRMS database!')
    print(f'  - Matched & Updated: {len(matched)}')
    print(f'  - Unmatched in Calculator: {len(unmatched_calculator)}')
    print(f'  - Present Only in HRMS: {len(unmatched_hrms)}')


if __name__ == '__main__':
    run_migration()
