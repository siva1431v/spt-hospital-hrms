#!/usr/bin/env python3
"""
SPT Hospital HRMS — SQLite to PostgreSQL Migration Script

Migrates all data from the local SQLite database to a production PostgreSQL database.
Respects foreign key ordering to avoid constraint violations.

Usage:
    python migrate_sqlite_to_postgres.py --sqlite-path backend/spt_hrms.db --postgres-url postgresql://user:pass@host:5432/dbname

    Or, if you have a .env file with POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB:
    python migrate_sqlite_to_postgres.py --sqlite-path backend/spt_hrms.db --postgres-host localhost
"""

import argparse
import os
import sys
import time
from pathlib import Path

try:
    import sqlalchemy
    from sqlalchemy import create_engine, text, inspect
except ImportError:
    print("ERROR: SQLAlchemy is required. Install with: pip install sqlalchemy psycopg2-binary")
    sys.exit(1)


# Tables in migration order (respects foreign key dependencies)
MIGRATION_ORDER = [
    "departments",
    "designations",
    "shifts",
    "shift_code_aliases",
    "employees",
    "users",
    "attendance_imports",
    "attendance",
    "attendance_import_records",
    "attendance_corrections",
    "attendance_exceptions",
    "monthly_attendance_aggregates",
    "leave_types",
    "leave_requests",
    "leave_balances",
    "salary_components",
    "salary_structures",
    "salary_structure_items",
    "payroll_periods",
    "payroll_records",
    "payroll_items",
    "salary_slips",
    "security_fund_transactions",
    "audit_logs",
    "system_settings",
]

# Tables to skip during migration
SKIP_TABLES = {"alembic_version"}


def load_dotenv_file(env_path: str) -> dict:
    """Load environment variables from a .env file."""
    env_vars = {}
    if not os.path.exists(env_path):
        return env_vars
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                env_vars[key] = value
    return env_vars


def build_postgres_url(args) -> str:
    """Build PostgreSQL URL from args or .env file."""
    if args.postgres_url:
        return args.postgres_url

    # Try to load from .env
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    env_vars = load_dotenv_file(env_path)

    # Also check environment variables (they take priority)
    pg_user = os.environ.get("POSTGRES_USER") or env_vars.get("POSTGRES_USER")
    pg_password = os.environ.get("POSTGRES_PASSWORD") or env_vars.get("POSTGRES_PASSWORD")
    pg_db = os.environ.get("POSTGRES_DB") or env_vars.get("POSTGRES_DB")
    pg_host = args.postgres_host or os.environ.get("POSTGRES_HOST") or env_vars.get("POSTGRES_HOST", "localhost")
    pg_port = args.postgres_port or os.environ.get("POSTGRES_PORT") or env_vars.get("POSTGRES_PORT", "5432")

    if not all([pg_user, pg_password, pg_db]):
        print("ERROR: PostgreSQL connection details not found.")
        print("  Either provide --postgres-url or set POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB")
        print("  in your .env file or environment variables.")
        sys.exit(1)

    return f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"


def get_table_columns(engine, table_name: str) -> list:
    """Get column names for a table."""
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return [col["name"] for col in columns]


def migrate_table(sqlite_engine, pg_engine, table_name: str) -> int:
    """Migrate a single table from SQLite to PostgreSQL. Returns row count."""
    # Check if table exists in SQLite
    sqlite_inspector = inspect(sqlite_engine)
    sqlite_tables = sqlite_inspector.get_table_names()
    if table_name not in sqlite_tables:
        print(f"  ⏭  {table_name} — not found in SQLite, skipping")
        return 0

    # Check if table exists in PostgreSQL
    pg_inspector = inspect(pg_engine)
    pg_tables = pg_inspector.get_table_names()
    if table_name not in pg_tables:
        print(f"  ⏭  {table_name} — not found in PostgreSQL, skipping")
        return 0

    # Get columns that exist in both databases
    sqlite_columns = set(get_table_columns(sqlite_engine, table_name))
    pg_columns = set(get_table_columns(pg_engine, table_name))
    common_columns = sorted(sqlite_columns & pg_columns)

    if not common_columns:
        print(f"  ⏭  {table_name} — no common columns, skipping")
        return 0

    # Read all rows from SQLite
    columns_str = ", ".join(common_columns)
    with sqlite_engine.connect() as sqlite_conn:
        result = sqlite_conn.execute(text(f"SELECT {columns_str} FROM {table_name}"))
        rows = result.fetchall()

    if not rows:
        print(f"  ⏭  {table_name} — 0 rows, skipping")
        return 0

    # Insert into PostgreSQL
    placeholders = ", ".join([f":{col}" for col in common_columns])
    insert_sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

    inserted = 0
    skipped = 0

    with pg_engine.connect() as pg_conn:
        for row in rows:
            row_dict = dict(zip(common_columns, row))
            try:
                pg_conn.execute(text(insert_sql), row_dict)
                inserted += 1
            except sqlalchemy.exc.IntegrityError:
                pg_conn.rollback()
                skipped += 1
                continue

        # Reset the sequence for the id column if it exists
        if "id" in common_columns:
            try:
                pg_conn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), "
                    f"(SELECT COALESCE(MAX(id), 0) FROM {table_name}))"
                ))
            except Exception:
                # Table might not have a serial sequence (e.g., UUID primary keys)
                pass

        pg_conn.commit()

    status = f"  ✓  {table_name} — {inserted} rows migrated"
    if skipped:
        status += f" ({skipped} duplicates skipped)"
    print(status)

    return inserted


def main():
    parser = argparse.ArgumentParser(
        description="Migrate SPT Hospital HRMS data from SQLite to PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-path",
        default="backend/spt_hrms.db",
        help="Path to SQLite database file (default: backend/spt_hrms.db)",
    )
    parser.add_argument(
        "--postgres-url",
        default=None,
        help="PostgreSQL connection URL (e.g., postgresql://user:pass@localhost:5432/dbname)",
    )
    parser.add_argument(
        "--postgres-host",
        default=None,
        help="PostgreSQL host (default: localhost, used if --postgres-url not provided)",
    )
    parser.add_argument(
        "--postgres-port",
        default=None,
        help="PostgreSQL port (default: 5432, used if --postgres-url not provided)",
    )

    args = parser.parse_args()

    # Validate SQLite path
    sqlite_path = Path(args.sqlite_path)
    if not sqlite_path.exists():
        print(f"ERROR: SQLite database not found at: {sqlite_path.absolute()}")
        sys.exit(1)

    sqlite_size = sqlite_path.stat().st_size / (1024 * 1024)
    print("══════════════════════════════════════════════")
    print("  SPT Hospital HRMS — SQLite → PostgreSQL Migration")
    print("══════════════════════════════════════════════")
    print(f"\n  SQLite: {sqlite_path.absolute()} ({sqlite_size:.1f} MB)")

    # Build PostgreSQL URL
    postgres_url = build_postgres_url(args)
    # Mask password in display
    display_url = postgres_url
    if "@" in display_url:
        pre_at = display_url.split("@")[0]
        post_at = display_url.split("@")[1]
        if ":" in pre_at.split("//")[1]:
            user = pre_at.split("//")[1].split(":")[0]
            display_url = f"{pre_at.split('//')[0]}//{user}:****@{post_at}"
    print(f"  PostgreSQL: {display_url}")
    print()

    # Create engines
    sqlite_engine = create_engine(f"sqlite:///{sqlite_path.absolute()}")
    pg_engine = create_engine(postgres_url)

    # Test connections
    try:
        with sqlite_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  ✓ SQLite connection OK")
    except Exception as e:
        print(f"  ✗ SQLite connection failed: {e}")
        sys.exit(1)

    try:
        with pg_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  ✓ PostgreSQL connection OK")
    except Exception as e:
        print(f"  ✗ PostgreSQL connection failed: {e}")
        sys.exit(1)

    print()
    print("Migrating tables...")
    print("─" * 50)

    start_time = time.time()
    total_rows = 0
    tables_migrated = 0

    for table_name in MIGRATION_ORDER:
        if table_name in SKIP_TABLES:
            continue
        count = migrate_table(sqlite_engine, pg_engine, table_name)
        total_rows += count
        if count > 0:
            tables_migrated += 1

    # Check for any tables in SQLite that we might have missed
    sqlite_inspector = inspect(sqlite_engine)
    all_sqlite_tables = set(sqlite_inspector.get_table_names())
    covered_tables = set(MIGRATION_ORDER) | SKIP_TABLES
    missed_tables = all_sqlite_tables - covered_tables

    if missed_tables:
        print()
        print("Additional tables found in SQLite (not in migration order):")
        for table_name in sorted(missed_tables):
            count = migrate_table(sqlite_engine, pg_engine, table_name)
            total_rows += count
            if count > 0:
                tables_migrated += 1

    elapsed = time.time() - start_time

    print()
    print("══════════════════════════════════════════════")
    print("  Migration Complete!")
    print("══════════════════════════════════════════════")
    print(f"  Tables migrated: {tables_migrated}")
    print(f"  Total rows:      {total_rows}")
    print(f"  Time elapsed:    {elapsed:.1f}s")
    print()

    # Cleanup
    sqlite_engine.dispose()
    pg_engine.dispose()


if __name__ == "__main__":
    main()
