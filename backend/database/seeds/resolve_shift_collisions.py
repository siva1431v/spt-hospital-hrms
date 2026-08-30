"""Resolve shift roster collisions that can be disambiguated by department."""
import sqlite3
import os

def main():
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'spt_hrms.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Murugesan Bio 207 (Default) -> Shift I General (GS, ID 4)
    cursor.execute("UPDATE employees SET shift_id = 4 WHERE biometric_code = '207'")
    print(f'Murugesan Bio 207 -> GS (Shift I): {cursor.rowcount} rows updated')

    # Murugesan Bio 45 (Security) -> Shift VII Security Split (SEC_SPLIT, ID 17)
    cursor.execute("UPDATE employees SET shift_id = 17 WHERE biometric_code = '45'")
    print(f'Murugesan Bio 45 -> SEC_SPLIT (Shift VII): {cursor.rowcount} rows updated')

    # Verify Lavanya & Periyasamy are already correctly assigned
    for code, expected_name, expected_shift in [
        ('18', 'Lavanya (Lab)', 15),  # LAB_SPLIT
        ('10', 'Lavanya (Reception)', 4),  # GS
        ('2', 'Periyasamy (Dr)', 4),  # GS
        ('58', 'Periyasamy (Security)', 17),  # SEC_SPLIT
    ]:
        cursor.execute("SELECT first_name, last_name, shift_id FROM employees WHERE biometric_code = ?", (code,))
        row = cursor.fetchone()
        if row:
            name = f'{row[0]} {row[1]}'
            shift = row[2]
            status = 'OK' if shift == expected_shift else f'MISMATCH (expected {expected_shift}, got {shift})'
            print(f'{expected_name} Bio {code}: shift_id={shift} -> {status}')

    # Report all 7 unresolved collisions (both candidates in same dept) + 2 unlisted
    print('\n=== STILL UNRESOLVED SAME-DEPARTMENT PAIRS (owner must pick) ===')
    unresolved = [
        ('Senthil Murugan', [('6', 'MANAGER'), ('201', 'MANAGER')]),
        ('Naveen', [('40', 'NURSING'), ('206', 'NURSING')]),
        ('Saran', [('61', 'NURSING'), ('208', 'NURSING')]),
        ('Madesh', [('42', 'NURSING'), ('202', 'NURSING')]),
        ('Selladurai', [('62', 'NURSING'), ('209', 'NURSING')]),
        ('Abinaya', [('29', 'NURSING'), ('210', 'NURSING')]),
        ('Ganesh', [('39', 'NURSING'), ('204', 'NURSING')]),
    ]
    for name, candidates in unresolved:
        codes_str = ' vs '.join([f'Bio {c[0]} ({c[1]})' for c in candidates])
        print(f'  {name}: {codes_str} — same department, awaiting owner choice')

    print('\n=== UNLISTED / NAME VARIATION STAFF (owner confirmation) ===')
    print('  Jagathish (SPT203) vs Jagathishwaran (SPT41)')
    print('  Senthamilselvi (SPT33) vs Tamilselvi (PDF) vs Tamilmani/Tamilmaran (Roster)')

    conn.commit()
    conn.close()
    print('\nDone.')

if __name__ == '__main__':
    main()
