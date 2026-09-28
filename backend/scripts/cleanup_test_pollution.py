"""
One-off cleanup script to purge test pollution from the live spt_hrms.db database.
Usage:
    python backend/scripts/cleanup_test_pollution.py --dry-run
    python backend/scripts/cleanup_test_pollution.py --execute
"""
import os
import sys
import argparse
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spt_hrms.db")


def inspect_and_clean(dry_run: bool = True):
    if not os.path.exists(DB_PATH):
        sys.exit(f"Database not found at {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    mode_str = "DRY RUN (No changes will be saved)" if dry_run else "EXECUTE MODE (Changes WILL be committed)"
    print("=" * 70)
    print(f"SPT Hospital HRMS — Database Cleanup Script")
    print(f"Database: {DB_PATH}")
    print(f"Mode:     {mode_str}")
    print("=" * 70)

    # ─────────────────────────────────────────────────────────────
    # 1. Security Fund Transactions
    # ─────────────────────────────────────────────────────────────
    print("\n1. [SECURITY FUND TRANSACTIONS]")
    cursor.execute("""
        SELECT sft.id, sft.employee_id, e.employee_id, e.full_name, sft.transaction_type, sft.amount, sft.notes
        FROM security_fund_transactions sft
        LEFT JOIN employees e ON sft.employee_id = e.id
        WHERE sft.id = 710 OR lower(sft.notes) LIKE '%test%'
    """)
    sft_rows = cursor.fetchall()
    if sft_rows:
        print(f"Found {len(sft_rows)} test transaction(s) to DELETE:")
        for r in sft_rows:
            print(f"  - ID {r[0]}: emp_id={r[1]} ({r[2]} - {r[3]}), type={r[4]}, amount={r[5]}, notes='{r[6]}'")
        if not dry_run:
            cursor.execute("DELETE FROM security_fund_transactions WHERE id = 710 OR lower(notes) LIKE '%test%'")
            print(f"  --> Deleted {cursor.rowcount} row(s).")
    else:
        print("  None found.")

    # ─────────────────────────────────────────────────────────────
    # 2. Attendance Exceptions
    # ─────────────────────────────────────────────────────────────
    print("\n2. [ATTENDANCE EXCEPTIONS]")
    cursor.execute("""
        SELECT ae.id, ae.employee_id, e.employee_id, e.full_name, ae.exception_type, ae.review_status, ae.review_notes
        FROM attendance_exceptions ae
        LEFT JOIN employees e ON ae.employee_id = e.id
        WHERE ae.id = 721 OR lower(ae.review_notes) LIKE '%test%'
    """)
    ae_rows = cursor.fetchall()
    if ae_rows:
        print(f"Found {len(ae_rows)} exception(s) to RESET to 'PENDING':")
        for r in ae_rows:
            print(f"  - ID {r[0]}: emp={r[2]} ({r[3]}), type={r[4]}, status={r[5]}, notes='{r[6]}'")
        if not dry_run:
            cursor.execute("""
                UPDATE attendance_exceptions
                SET review_status = 'PENDING',
                    reviewed_by_id = NULL,
                    reviewed_at = NULL,
                    review_notes = NULL
                WHERE id = 721 OR lower(review_notes) LIKE '%test%'
            """)
            print(f"  --> Reset {cursor.rowcount} exception(s) to PENDING.")
    else:
        print("  None found.")

    # ─────────────────────────────────────────────────────────────
    # 3. Attendance Imports & Child Records
    # ─────────────────────────────────────────────────────────────
    print("\n3. [ATTENDANCE IMPORTS & TEST UPLOADS]")
    cursor.execute("""
        SELECT id, filename, status, total_records_in_pdf, records_imported, imported_at
        FROM attendance_imports
        WHERE lower(filename) LIKE '%test%'
           OR id IN (38, 39, 40)
    """)
    import_rows = cursor.fetchall()
    if import_rows:
        print(f"Found {len(import_rows)} test import session(s):")
        import_ids = [r[0] for r in import_rows]
        for r in import_rows:
            # Check children
            cursor.execute("SELECT count(*) FROM attendance_import_records WHERE import_id = ?", (r[0],))
            child_import_recs = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM attendance WHERE source_import_id = ?", (r[0],))
            child_att_recs = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM attendance_exceptions WHERE import_id = ?", (r[0],))
            child_exc_recs = cursor.fetchone()[0]
            print(f"  - Import ID {r[0]}: '{r[1]}' (created: {r[5]}) | "
                  f"child records: {child_import_recs}, child attendance: {child_att_recs}, child exceptions: {child_exc_recs}")

        placeholders = ",".join(str(i) for i in import_ids)
        if not dry_run:
            cursor.execute(f"DELETE FROM attendance WHERE source_import_id IN ({placeholders})")
            del_att = cursor.rowcount
            cursor.execute(f"DELETE FROM attendance_exceptions WHERE import_id IN ({placeholders})")
            del_exc = cursor.rowcount
            cursor.execute(f"DELETE FROM attendance_import_records WHERE import_id IN ({placeholders})")
            del_rec = cursor.rowcount
            cursor.execute(f"DELETE FROM attendance_imports WHERE id IN ({placeholders})")
            del_imp = cursor.rowcount
            print(f"  --> Deleted {del_imp} import(s), {del_rec} import_record(s), {del_att} attendance row(s), {del_exc} exception(s).")
    else:
        print("  None found.")

    # ─────────────────────────────────────────────────────────────
    # 4. Audit Logs
    # ─────────────────────────────────────────────────────────────
    print("\n4. [AUDIT LOGS]")
    audit_filter = """
        lower(description) LIKE '%test%'
        OR lower(description) LIKE '%june 2030%'
        OR lower(description) LIKE '%integrity test%'
        OR description LIKE '%TEST_%'
    """
    cursor.execute(f"SELECT count(*) FROM audit_logs WHERE {audit_filter}")
    test_logs_count = cursor.fetchone()[0]
    cursor.execute(f"SELECT id, action, entity_type, description, created_at FROM audit_logs WHERE {audit_filter} LIMIT 5")
    sample_logs = cursor.fetchall()
    print(f"Found {test_logs_count} test audit log entry/entries to DELETE.")
    if sample_logs:
        print("  Sample entries:")
        for l in sample_logs:
            print(f"    * [{l[4]}] {l[1]} on {l[2]}: {l[3]}")
    if not dry_run and test_logs_count > 0:
        cursor.execute(f"DELETE FROM audit_logs WHERE {audit_filter}")
        print(f"  --> Deleted {cursor.rowcount} test audit log entry/entries.")

    # ─────────────────────────────────────────────────────────────
    # 5. Integrity Verification
    # ─────────────────────────────────────────────────────────────
    print("\n5. [STATE INTEGRITY VERIFICATION]")
    # Employees
    cursor.execute("SELECT count(*) FROM employees")
    total_emps = cursor.fetchone()[0]
    cursor.execute("SELECT count(*) FROM employees WHERE employee_id LIKE 'TEST_%'")
    test_emps = cursor.fetchone()[0]
    print(f"  - Total employees: {total_emps} (Test employees: {test_emps})")
    assert test_emps == 0, f"Found {test_emps} leftover test employees!"
    assert total_emps == 66, f"Expected 66 employees, found {total_emps}!"

    # Users
    cursor.execute("SELECT id, username, email, role, is_active FROM users")
    users = cursor.fetchall()
    user_names = [u[1] for u in users]
    print(f"  - Users ({len(users)}): {', '.join(user_names)}")
    assert set(user_names) == {"admin", "hr"}, f"Unexpected users found: {user_names}"

    # Payroll Periods
    cursor.execute("SELECT id, year, month, period_name, status FROM payroll_periods")
    periods = cursor.fetchall()
    period_names = [p[3] for p in periods]
    print(f"  - Payroll Periods ({len(periods)}): {', '.join(period_names)}")
    assert len(periods) == 1 and periods[0][1] == 2026 and periods[0][2] == 8, f"Unexpected payroll periods: {periods}"

    # Attendance
    cursor.execute("SELECT count(*) FROM attendance")
    total_att = cursor.fetchone()[0]
    cursor.execute("SELECT count(DISTINCT attendance_date) FROM attendance")
    dates_att = cursor.fetchone()[0]
    print(f"  - Attendance records: {total_att} rows across {dates_att} dates in August 2026")

    print("\n" + "=" * 70)
    if dry_run:
        print("DRY RUN COMPLETE — No modifications were written to disk.")
        print("Run with --execute to apply these changes.")
    else:
        conn.commit()
        print("CHANGES COMMITTED SUCCESSFULLY!")
    print("=" * 70)

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Purge test pollution from live spt_hrms.db")
    parser.add_argument("--execute", action="store_true", help="Execute the deletions and commits")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run only (default)")
    args = parser.parse_args()

    execute_mode = args.execute
    inspect_and_clean(dry_run=not execute_mode)
