"""
SPT Hospital HRMS — Designations & Shift Fix Script
1. Assigns appropriate designation_id to all 66 active employees.
2. Fixes Chinnadurai (bio 59, SECURITY) shift from HK_SPLIT to SEC_SPLIT.
3. Audits all other staff department/shift mappings.
4. Cleans up QA leave requests, QA correction test rows, and QA shift.
"""
import sqlite3
import os

DEPT_DESIGNATION_MAP = {
    'NURSING': 'Staff Nurse',
    'LAB': 'Lab Technician',
    'PHARMACY': 'Pharmacist',
    'RECEPTION': 'Receptionist',
    'SECURITY': 'Security Guard',
    'HOUSE KEEPING': 'Housekeeping Staff',
    'DRIVER': 'Driver',
    'X RAY': 'X-Ray Technician',
    'MANAGER': 'Manager',
    'DOCTOR': 'Doctor',
    'HR': 'HR Executive',
    'ADMIN': 'Hospital Administrator',
}

def run_fixes():
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'spt_hrms.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Load designations
    cursor.execute("SELECT id, name FROM designations")
    desig_name_to_id = {row[1].lower(): row[0] for row in cursor.fetchall()}

    # 1. Populate designations for all active employees
    cursor.execute("""
        SELECT e.id, e.biometric_code, e.first_name, e.last_name, d.name as dept
        FROM employees e
        LEFT JOIN departments d ON e.department_id = d.id
        WHERE e.is_active = 1
    """)
    emps = cursor.fetchall()
    updated_desigs = 0
    for emp_id, bio, f_name, l_name, dept in emps:
        full_name = f"{f_name} {l_name or ''}".strip()
        target_desig_name = DEPT_DESIGNATION_MAP.get(dept, 'Staff Nurse')
        if 'dr ' in full_name.lower():
            target_desig_name = 'Doctor'
        elif 'manager' in (dept or '').lower() or 'senthil murugan' in full_name.lower():
            target_desig_name = 'Manager'

        desig_id = desig_name_to_id.get(target_desig_name.lower())
        if desig_id:
            cursor.execute("UPDATE employees SET designation_id = ? WHERE id = ?", (desig_id, emp_id))
            updated_desigs += 1

    print(f"1. Assigned designations to {updated_desigs} active employees.")

    # 2. Fix Chinnadurai (bio 59, SECURITY) shift to SEC_SPLIT (id 17)
    cursor.execute("SELECT id FROM shifts WHERE code = 'SEC_SPLIT'")
    sec_split_id = cursor.fetchone()[0]
    cursor.execute("UPDATE employees SET shift_id = ? WHERE biometric_code = '59'", (sec_split_id,))
    print(f"2. Updated Chinnadurai (bio 59, SECURITY) shift to SEC_SPLIT (shift_id = {sec_split_id}).")

    # 3. Clean up QA leave requests
    cursor.execute("DELETE FROM leave_requests WHERE reason LIKE '%QA%' OR review_comment LIKE '%QA%'")
    print(f"3. Cleaned up QA leave requests: {cursor.rowcount} rows removed.")

    # 4. Clean up QA correction test attendance record
    cursor.execute("DELETE FROM attendance_corrections WHERE reason LIKE '%QA%'")
    cursor.execute("UPDATE attendance SET is_corrected = 0, remarks = NULL WHERE remarks LIKE '%QA correction test%'")
    print(f"4. Cleaned up QA attendance corrections.")

    # 5. Clean up QA shift
    cursor.execute("DELETE FROM shifts WHERE code = 'QAS' OR name LIKE '%QA%'")
    print(f"5. Cleaned up QA test shifts: {cursor.rowcount} rows removed.")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    run_fixes()
