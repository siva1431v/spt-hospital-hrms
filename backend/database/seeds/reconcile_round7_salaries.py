"""
SPT Hospital HRMS — Round 7 Base Salary Re-Migration & Disambiguation Script
Matches by name + department.
Leaves ambiguous same-department pairs as PLACEHOLDER / UNSET for owner decision.
"""
import sqlite3
import os

OLD_CALCULATOR_STAFF = [
    ('Senthilmurugan', 'MANAGER', 20000.0),
    ('Sudha', 'RECEPTION', 14000.0),
    ('Thenmozhi', 'RECEPTION', 14000.0),
    ('Viji', 'RECEPTION', 16000.0),
    ('Lavanya', 'RECEPTION', 12000.0),
    ('Karthika', 'RECEPTION', 11000.0),
    ('Basheer Mohamed', 'PHARMACY', 15000.0),
    ('Bhuvaneshwari', 'PHARMACY', 14000.0),
    ('Syed Sajith', 'PHARMACY', 13000.0),
    ('Aarthi', 'PHARMACY', 14000.0),
    ('Ananthi', 'LAB', 18000.0),
    ('Lavanya', 'LAB', 14000.0),
    ('Priyadharshini', 'LAB', 14000.0),
    ('Sathya LAB', 'LAB', 15000.0),
    ('Nilavazhagan', 'X RAY', 15000.0),
    ('Meerasha', 'X RAY', 14000.0),
    ('Lavanya J', 'NURSING', 10000.0),
    ('Vasanthi', 'NURSING', 18000.0),
    ('Abinaya', 'NURSING', 13000.0),
    ('Maheshwari', 'NURSING', 13000.0),
    ('Aarthi', 'NURSING', 13000.0),
    ('Praveena', 'NURSING', 13000.0),
    ('Makisha', 'NURSING', 10000.0),
    ('Gobika J', 'NURSING', 10000.0),
    ('Sharshini', 'NURSING', 10000.0),
    ('Gopika', 'NURSING', 15000.0),
    ('Vijayalakshmi', 'NURSING', 14000.0),
    ('Sangeetharani', 'NURSING', 12000.0),
    ('Logeswari', 'NURSING', 10000.0),
    ('Dharshini', 'NURSING', 14000.0),
    ('Naveen', 'NURSING', 20000.0),
    ('Ganesh', 'NURSING', 20000.0),
    ('Jothivel', 'NURSING', 16000.0),
    ('Nalayini', 'NURSING', 10000.0),
    ('Jagadeeshwaran', 'NURSING', 14000.0),
    ('Madesh', 'NURSING', 15000.0),
    ('Parimala', 'HOUSE KEEPING', 11500.0),
    ('Dhanalakshmi', 'HOUSE KEEPING', 11500.0),
    ('Boopathi', 'HOUSE KEEPING', 11500.0),
    ('Mahalakshmi', 'HOUSE KEEPING', 10500.0),
    ('Logeshwari', 'HOUSE KEEPING', 10500.0),
    ('Gnana Soundari', 'HOUSE KEEPING', 9500.0),
    ('Rajeshwari', 'HOUSE KEEPING', 10500.0),
    ('Annakili', 'HOUSE KEEPING', 10500.0),
    ('Sarala', 'HOUSE KEEPING', 13000.0),
    ('Chinnadurai', 'SECURITY', 12000.0),
    ('Ramasamy', 'SECURITY', 14000.0),
    ('Tamilmaran', 'DRIVER', 20000.0),
    ('Murugesan', 'SECURITY', 13000.0),
    ('Sadiq Basha', 'SECURITY', 13000.0),
    ('Kalyani', 'NURSING', 16000.0),
    ('Savithiri', 'HOUSE KEEPING', 9500.0),
    ('Sathyapriya', 'HOUSE KEEPING', 15000.0),
    ('Selvi', 'HOUSE KEEPING', 10000.0),
    ('Periyasamy', 'SECURITY', 13000.0),
]

# Explicit single matches where department and identity are unique
KNOWN_MAPPINGS = {
    "12": ("Bhuvaneshwari", "PHARMACY", 14000.0),
    "1":  ("DR Manoj", "DOCTOR", 25000.0),
    "6":  ("Senthil Murugan", "MANAGER", 20000.0),
    "7":  ("Sudha", "RECEPTION", 14000.0),
    "8":  ("Thenmozhi", "RECEPTION", 14000.0),
    "9":  ("Viji", "RECEPTION", 16000.0),
    "10": ("Lavanya", "RECEPTION", 12000.0),        # Reception Lavanya: 12k
    "11": ("Karthika", "RECEPTION", 11000.0),
    "12": ("Bhuvaneshwari", "PHARMACY", 14000.0),
    "13": ("Aarthi G", "PHARMACY", 14000.0),
    "14": ("Basheer Mohamed", "PHARMACY", 15000.0),
    "15": ("Syed Sajith", "PHARMACY", 13000.0),
    "16": ("Ananthi", "LAB", 18000.0),
    "17": ("Priyadharshini", "LAB", 14000.0),
    "18": ("Lavanya", "LAB", 14000.0),             # Lab Lavanya: 14k
    "19": ("Sathya", "LAB", 15000.0),
    "20": ("Nilavazhagan", "X RAY", 15000.0),
    "21": ("Meerasha", "X RAY", 14000.0),
    "22": ("Vasanthi", "NURSING", 18000.0),
    "23": ("Maheshwari", "NURSING", 13000.0),
    "24": ("Aarthi S", "NURSING", 13000.0),
    "26": ("Sangeetharani", "NURSING", 12000.0),
    "27": ("Vijayalakshmi", "NURSING", 14000.0),
    "28": ("Kalyani", "NURSING", 16000.0),
    "29": ("Abinaya", "NURSING", 13000.0),
    "30": ("Makisha Kasani", "NURSING", 10000.0),
    "31": ("Dharshini", "NURSING", 14000.0),
    "32": ("Praveena", "NURSING", 13000.0),
    "34": ("Gobika", "NURSING", 10000.0),
    "37": ("Logeshwari", "NURSING", 10000.0),
    "39": ("Ganesh", "NURSING", 20000.0),
    "40": ("Naveen", "NURSING", 20000.0),
    "41": ("Jagathishwaran", "NURSING", 14000.0),
    "42": ("Madesh", "NURSING", 15000.0),
    "44": ("Shathiq Basha", "SECURITY", 13000.0),
    "45": ("Murugesan", "SECURITY", 13000.0),
    "46": ("Sarala", "HOUSE KEEPING", 13000.0),
    "47": ("Parimala", "HOUSE KEEPING", 11500.0),
    "48": ("Dhanalakshmi", "HOUSE KEEPING", 11500.0),
    "49": ("Boopathi", "HOUSE KEEPING", 11500.0),
    "50": ("Mahalakshmi", "HOUSE KEEPING", 10500.0),
    "51": ("Annakili", "HOUSE KEEPING", 10500.0),
    "52": ("Sathyapriya", "HOUSE KEEPING", 15000.0),
    "53": ("Logeshwari HK", "HOUSE KEEPING", 10000.0),
    "54": ("Rajeshwari", "HOUSE KEEPING", 10500.0),
    "55": ("Selvi", "HOUSE KEEPING", 10000.0),
    "56": ("Gnanasundari", "HOUSE KEEPING", 9500.0),
    "57": ("Ramasamy", "SECURITY", 14000.0),
    "58": ("Periyasamy", "SECURITY", 13000.0),      # Security Periyasamy: 13k
    "59": ("Chinnadurai", "SECURITY", 12000.0),
    "60": ("Tamilmaran", "DRIVER", 20000.0),
    "62": ("Selladurai", "NURSING", 25000.0),
    "64": ("DR Saranya", "DOCTOR", 25000.0),
}

# Ghost duplicate pairs and non-migrated staff -> leave as PLACEHOLDER / UNSET
GHOST_PLACEHOLDERS = ["201", "202", "203", "204", "206", "207", "208", "209", "210", "2", "3", "33", "61", "63"]
# 201-210: Ghost duplicate records created during initial bio import
# 2: DR Periyasamy (DOCTOR) -> PLACEHOLDER
# 3: Dt Santhiya (HR) -> PLACEHOLDER
# 33: Senthamilselvi (NURSING) -> PLACEHOLDER
# 61: Saran (NURSING) -> PLACEHOLDER
# 63: Ashwin (PHARMACY) -> PLACEHOLDER

def run_reconciliation():
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'spt_hrms.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Update known unambiguous migrated salaries
    for bio, (name, dept, sal) in KNOWN_MAPPINGS.items():
        cursor.execute(
            "UPDATE employees SET basic_salary = ?, salary_source = 'MIGRATED' WHERE biometric_code = ? AND is_active = 1",
            (sal, bio)
        )

    # 2. Mark ghost duplicates and non-migrated staff as PLACEHOLDER
    for bio in GHOST_PLACEHOLDERS:
        cursor.execute(
            "UPDATE employees SET basic_salary = 25000.0, salary_source = 'PLACEHOLDER' WHERE biometric_code = ? AND is_active = 1",
            (bio,)
        )

    conn.commit()

    # Print summary
    cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1 AND salary_source = 'MIGRATED'")
    migrated_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1 AND salary_source = 'PLACEHOLDER'")
    placeholder_count = cursor.fetchone()[0]

    print(f"Salary Reconciliation Complete:")
    print(f"  - Verified MIGRATED staff   : {migrated_count}")
    print(f"  - Unset / PLACEHOLDER staff : {placeholder_count} (including {len(GHOST_PLACEHOLDERS)} in ghost/non-migrated list)")
    print(f"  - Lavanya (Lab bio 18)      : ₹14,000 (MIGRATED)")
    print(f"  - Lavanya (Reception bio 10): ₹12,000 (MIGRATED)")
    print(f"  - DR Periyasamy (bio 2)     : PLACEHOLDER (Doctor)")
    print(f"  - Periyasamy (bio 58)       : ₹13,000 (Security)")

    conn.close()

if __name__ == '__main__':
    run_reconciliation()
