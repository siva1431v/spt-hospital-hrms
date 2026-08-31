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
                from database.seeds.seed_real_shifts import seed_shifts
                await seed_shifts()
                print("✓ Shifts seeded.")
            else:
                print(f"⏭ Shifts already seeded ({shift_count} found).")

        print("\n✅ Database initialization complete!")
    except Exception as e:
        print(f"⚠️ Error seeding database: {e}", file=sys.stderr)
        # Log error but do not fail startup (tables are already created, which is fatal)


if __name__ == "__main__":
    asyncio.run(init_database())
