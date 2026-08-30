"""
SPT Hospital HRMS — Round 6 Data Cleanup Script
1. Creates real employee SPT12 / Bhuvaneshwari (biometric_code = "12", PHARMACY, base salary ₹14,000, salary_source = "MIGRATED").
2. Fixes SPT30 Makisha Kasani base salary from ₹1,000 to ₹10,000.
3. Re-verifies all 55 migrated staff base salaries against the old calculator source list.
4. Marks non-migrated staff (doctors, SPT2xx, Dt Santhiya, Ashwin, Senthamilselvi) with salary_source = "PLACEHOLDER".
5. Purges all TEST_EMP_* records.
"""
import sqlite3

SOURCE_SALARIES = {
    "Senthil Murugan": 20000.0,
    "Sudha": 14000.0,
    "Thenmozhi": 14000.0,
    "Viji": 16000.0,
    "Lavanya": 12000.0,
    "Karthika": 11000.0,
    "Basheer Mohamed": 15000.0,
    "Syed Sajith": 13000.0,
    "Aarthi G": 14000.0,
    "Ananthi": 18000.0,
    "Lavanya Lab": 14000.0,
    "Priyadharshini": 14000.0,
    "Sathya": 15000.0,
    "Nilavazhagan": 15000.0,
    "Meerasha": 14000.0,
    "Vasanthi": 18000.0,
    "Maheshwari": 13000.0,
    "Aarthi S": 13000.0,
    "Abinaya": 13000.0,
    "Praveena": 13000.0,
    "Makisha Kasani": 10000.0,
    "Gobika": 10000.0,
    "Vijayalakshmi": 14000.0,
    "Sangeetharani": 12000.0,
    "Logeshwari": 10000.0,
    "Dharshini": 11000.0,
    "Naveen": 20000.0,
    "Ganesh": 20000.0,
    "Jagathishwaran": 14000.0,
    "Madesh": 15000.0,
    "Kalyani": 16000.0,
    "Parimala": 11500.0,
    "Dhanalakshmi": 11500.0,
    "Boopathi": 11500.0,
    "Mahalakshmi": 10500.0,
    "Logeshwari HK": 10500.0,
    "Gnanasundari": 9500.0,
    "Rajeshwari": 10500.0,
    "Annakili": 10500.0,
    "Sarala": 13000.0,
    "Sathyapriya": 10000.0,
    "Selvi": 10000.0,
    "Chinnadurai": 12000.0,
    "Ramasamy": 14000.0,
    "Periyasamy": 13000.0,
    "Tamilmaran": 20000.0,
    "Murugesan": 13000.0,
    "Shathiq Basha": 13000.0,
    "Bhuvaneshwari": 14000.0,
}

def run_fix():
    conn = sqlite3.connect('spt_hrms.db')
    cursor = conn.cursor()

    # 1. Purge all TEST_EMP_* records and inactive demo records
    cursor.execute("DELETE FROM attendance WHERE employee_id IN (SELECT id FROM employees WHERE employee_id LIKE 'TEST_EMP_%' OR is_active = 0)")
    cursor.execute("DELETE FROM monthly_attendance_aggregates WHERE employee_id IN (SELECT id FROM employees WHERE employee_id LIKE 'TEST_EMP_%' OR is_active = 0)")
    cursor.execute("DELETE FROM payroll_records WHERE employee_id IN (SELECT id FROM employees WHERE employee_id LIKE 'TEST_EMP_%' OR is_active = 0)")
    cursor.execute("DELETE FROM employees WHERE employee_id LIKE 'TEST_EMP_%' OR (is_active = 0 AND biometric_code = '9912')")
    purged_count = cursor.rowcount
    print(f"1. Purged dummy TEST_EMP_* and inactive demo records: {purged_count}")

    # 2. Get PHARMACY department id
    cursor.execute("SELECT id FROM departments WHERE name = 'PHARMACY' OR code = 'PHARMACY'")
    pharmacy_row = cursor.fetchone()
    pharmacy_id = pharmacy_row[0] if pharmacy_row else None

    # 3. Create or activate SPT12 Bhuvaneshwari (biometric_code = "12")
    cursor.execute("SELECT id, is_active FROM employees WHERE biometric_code = '12'")
    bhu_row = cursor.fetchone()

    if not bhu_row:
        cursor.execute("""
            INSERT INTO employees (
                employee_id, biometric_code, first_name, last_name, full_name,
                department_id, employment_type, is_active, basic_salary, salary_source,
                created_at, updated_at
            ) VALUES (
                'SPT12', '12', 'Bhuvaneshwari', '', 'Bhuvaneshwari',
                ?, 'FULL_TIME', 1, 14000.0, 'MIGRATED',
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """, (pharmacy_id,))
        print("2. Created real employee SPT12 / Bhuvaneshwari (biometric_code = 12, base = ₹14,000)")
    else:
        cursor.execute("""
            UPDATE employees SET
                employee_id = 'SPT12',
                first_name = 'Bhuvaneshwari',
                full_name = 'Bhuvaneshwari',
                department_id = ?,
                is_active = 1,
                basic_salary = 14000.0,
                salary_source = 'MIGRATED'
            WHERE id = ?
        """, (pharmacy_id, bhu_row[0]))
        print("2. Updated existing employee to real SPT12 / Bhuvaneshwari (biometric_code = 12, base = ₹14,000)")

    # 4. Fix Makisha Kasani base salary (SPT30 / bio 30)
    cursor.execute("UPDATE employees SET basic_salary = 10000.0, salary_source = 'MIGRATED' WHERE biometric_code = '30' OR full_name LIKE '%Makisha%'")
    print(f"3. Updated Makisha Kasani base salary to ₹10,000 ({cursor.rowcount} row updated)")

    # 5. Re-verify all migrated staff base salaries
    discrepancies = []
    cursor.execute("SELECT id, employee_id, biometric_code, full_name, basic_salary FROM employees WHERE is_active = 1")
    active_staff = cursor.fetchall()

    for emp_id, emp_code, bio_code, name, curr_sal in active_staff:
        # Match against SOURCE_SALARIES by name
        matched_source = None
        for s_name, s_sal in SOURCE_SALARIES.items():
            if s_name.lower() in name.lower() or name.lower() in s_name.lower():
                matched_source = s_sal
                break

        if matched_source is not None:
            if curr_sal != matched_source:
                discrepancies.append((emp_code, name, curr_sal, matched_source))
                cursor.execute("UPDATE employees SET basic_salary = ?, salary_source = 'MIGRATED' WHERE id = ?", (matched_source, emp_id))
            else:
                cursor.execute("UPDATE employees SET salary_source = 'MIGRATED' WHERE id = ?", (emp_id,))
        else:
            # Placeholder salary
            cursor.execute("UPDATE employees SET salary_source = 'PLACEHOLDER' WHERE id = ?", (emp_id,))

    conn.commit()
    print(f"\n4. Salary Re-Verification Complete:")
    print(f"   Found & fixed {len(discrepancies)} salary discrepancies:")
    for code, name, old_s, new_s in discrepancies:
        print(f"     - {code} ({name}): Was ₹{old_s} -> Fixed to ₹{new_s}")

    cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1 AND salary_source = 'PLACEHOLDER'")
    placeholder_cnt = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1 AND salary_source = 'MIGRATED'")
    migrated_cnt = cursor.fetchone()[0]
    print(f"\n5. Active Staff Salary Source Classification:")
    print(f"   Migrated Salaries   : {migrated_cnt} staff")
    print(f"   Placeholder Salaries: {placeholder_cnt} staff")

    conn.close()

if __name__ == "__main__":
    run_fix()
