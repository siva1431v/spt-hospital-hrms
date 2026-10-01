"""
Database initialization script for production deployment.
Creates all tables and seeds initial data (admin user, departments, shifts, etc.)
Run this once on a fresh database:
    python -m scripts.init_db
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def init_database():
    from app.core.database import engine, Base, AsyncSessionLocal
    from app.core.config import settings

    # Import ALL models so Base.metadata has them
    from app.models.employee import Employee, SecurityFundTransaction
    from app.models.department import Department, Designation
    from app.models.shift import Shift, ShiftCodeAlias
    from app.models.attendance import (
        Attendance, AttendanceException, AttendanceImport,
        MonthlyAttendanceAggregate,
    )
    from app.models.payroll import (
        PayrollPeriod, PayrollRecord, PayrollItem, SalaryStructure,
    )
    from app.models.user import User, UserRole
    from app.models.audit import AuditLog, SystemSetting

    print(f"Database URL: {settings.DATABASE_URL[:40]}...")
    print("Creating all tables...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("✓ Tables created.")

    # Wrap seed block in try/except to prevent database seed failures from crashing startup
    try:
        from app.core.security import hash_password

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select

            # Check if admin user already exists
            existing = await db.execute(select(User).where(User.username == "admin"))
            if existing.scalar_one_or_none() is None:
                admin = User(
                    username="admin",
                    email="admin@spthospital.com",
                    hashed_password=hash_password("Admin@123"),
                    role=UserRole.SUPER_ADMIN,
                    is_active=True,
                    full_name="System Administrator",
                )
                db.add(admin)
                print("✓ Created admin user (admin / Admin@123)")
            else:
                print("⏭ Admin user already exists.")

            # HR user
            existing_hr = await db.execute(select(User).where(User.username == "hr"))
            if existing_hr.scalar_one_or_none() is None:
                hr = User(
                    username="hr",
                    email="hr@spthospital.com",
                    hashed_password=hash_password("HR@123"),
                    role=UserRole.HR_ADMIN,
                    is_active=True,
                    full_name="HR Administrator",
                )
                db.add(hr)
                print("✓ Created HR user (hr / HR@123)")
            else:
                print("⏭ HR user already exists.")

            await db.commit()

        # Seed shifts
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func
            count = await db.execute(select(func.count()).select_from(Shift))
            shift_count = count.scalar()
            if shift_count == 0:
                print("Seeding shifts...")
                os.environ.setdefault("PYTHONPATH", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from database.seeds.seed_real_shifts import seed_real_shifts
                await seed_real_shifts()
                print("✓ Shifts seeded.")
            else:
                print(f"⏭ Shifts already seeded ({shift_count} found).")

        # Seed core database (employees, departments, designations, settings, aliases) if empty
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func, text
            from app.models.employee import Employee
            emp_count_res = await db.execute(select(func.count()).select_from(Employee))
            emp_count = emp_count_res.scalar()
            if emp_count == 0:
                seed_sql_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database", "initial_seed.sql")
                if os.path.exists(seed_sql_path):
                    print(f"Seeding core database from {seed_sql_path}...")
                    with open(seed_sql_path, "r", encoding="utf-8") as f:
                        sql_content = f.read()
                    is_sqlite = "sqlite" in settings.DATABASE_URL
                    for statement in sql_content.split(";"):
                        statement = statement.strip()
                        if statement:
                            if not is_sqlite and statement.startswith("INSERT OR IGNORE INTO"):
                                statement = statement.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1) + " ON CONFLICT DO NOTHING"
                            await db.execute(text(statement))
                    await db.commit()
                    print("✓ Core database seeded (66 employees, departments, settings).")
            else:
                print(f"⏭ Employees already exist ({emp_count} found).")

        print("\n✅ Database initialization complete!")
    except Exception as e:
        print(f"⚠️ Error seeding database: {e}", file=sys.stderr)
        # Log error but do not fail startup (tables are already created, which is fatal)


if __name__ == "__main__":
    asyncio.run(init_database())
