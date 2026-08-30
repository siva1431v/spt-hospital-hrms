"""
SPT Hospital HRMS — Database Seed Script
Creates initial data: admin users, departments, shifts, leave types, salary components.
Run with: python -m database.seeds.seed
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import select
from datetime import time

from app.core.config import settings
from app.core.security import get_password_hash
from app.models import *


async def seed(db: AsyncSession):
    print("🌱 Seeding SPT Hospital HRMS database...")

    # ── 1. Departments ─────────────────────────────────────────────────────────
    departments_data = [
        ("NURSING", "NURS"),
        ("LAB", "LAB"),
        ("PHARMACY", "PHRM"),
        ("RECEPTION", "RECEP"),
        ("SECURITY", "SEC"),
        ("HOUSE KEEPING", "HK"),
        ("DRIVER", "DRV"),
        ("X RAY", "XRAY"),
        ("MANAGER", "MGR"),
        ("DOCTOR", "DR"),
        ("HR", "HR"),
        ("ADMINISTRATION", "ADMIN"),
        ("ICU", "ICU"),
        ("OT", "OT"),
        ("CASUALTY", "CAS"),
    ]
    departments = {}
    for name, code in departments_data:
        result = await db.execute(select(Department).where(Department.code == code))
        dept = result.scalar_one_or_none()
        if not dept:
            dept = Department(name=name, code=code, is_active=True)
            db.add(dept)
            await db.flush()
            print(f"  ✅ Department: {name}")
        departments[code] = dept

    # ── 2. Shifts ──────────────────────────────────────────────────────────────
    shifts_data = [
        # (code, name, start, end, overnight, grace, expected_mins, ot_threshold)
        ("MS", "Morning Shift", time(6, 0), time(14, 0), False, 15, 480, 480),
        ("NS", "Night Shift", time(14, 0), time(22, 0), False, 15, 480, 480),
        ("NTS", "Night Time Shift", time(22, 0), time(6, 0), True, 15, 480, 480),
        ("GS", "General Shift", time(9, 0), time(17, 0), False, 15, 480, 480),
        ("HK", "Housekeeping Morning", time(7, 0), time(15, 0), False, 15, 480, 480),
        ("HKN", "Housekeeping Night", time(15, 0), time(23, 0), False, 15, 480, 480),
        ("SS", "Split Shift", time(8, 0), time(20, 0), False, 30, 720, 720),
        ("IS", "Indian Shift", time(8, 30), time(17, 30), False, 15, 540, 540),
        ("B", "Backup Shift", time(6, 0), time(18, 0), False, 30, 720, 720),
        ("DS", "Day Shift", time(8, 0), time(16, 0), False, 15, 480, 480),
        ("ES", "Evening Shift", time(16, 0), time(0, 0), False, 15, 480, 480),
    ]
    for code, name, start, end, overnight, grace, expected, ot_thresh in shifts_data:
        result = await db.execute(select(Shift).where(Shift.code == code))
        if not result.scalar_one_or_none():
            shift = Shift(
                code=code, name=name, start_time=start, end_time=end,
                is_overnight=overnight, grace_period_minutes=grace,
                expected_working_minutes=expected, ot_threshold_minutes=ot_thresh,
            )
            db.add(shift)
            print(f"  ✅ Shift: {code} ({name})")

    await db.flush()

    # ── 3. Designations ────────────────────────────────────────────────────────
    designations_data = [
        ("Staff Nurse", "NURS"),
        ("Senior Nurse", "NURS"),
        ("Head Nurse", "NURS"),
        ("Lab Technician", "LAB"),
        ("Senior Lab Technician", "LAB"),
        ("Pharmacist", "PHRM"),
        ("Receptionist", "RECEP"),
        ("Security Guard", "SEC"),
        ("Housekeeping Staff", "HK"),
        ("Driver", "DRV"),
        ("X-Ray Technician", "XRAY"),
        ("Manager", "MGR"),
        ("Hospital Administrator", "ADMIN"),
        ("HR Executive", "HR"),
        ("Doctor", "DR"),
        ("ICU Nurse", "ICU"),
    ]
    for name, dept_code in designations_data:
        dept = departments.get(dept_code)
        result = await db.execute(select(Designation).where(Designation.name == name))
        if not result.scalar_one_or_none():
            desig = Designation(name=name, department_id=dept.id if dept else None)
            db.add(desig)
            print(f"  ✅ Designation: {name}")

    # ── 4. Leave Types ─────────────────────────────────────────────────────────
    leave_types_data = [
        ("Casual Leave", "CL", True, 12),
        ("Sick Leave", "SL", True, 12),
        ("Earned Leave", "EL", True, 15),
        ("Loss of Pay", "LOP", False, None),
        ("Maternity Leave", "ML", True, 84),
        ("Compensatory Off", "CO", True, None),
        ("Emergency Leave", "EM", True, 3),
    ]
    for name, code, is_paid, max_days in leave_types_data:
        result = await db.execute(select(LeaveType).where(LeaveType.code == code))
        if not result.scalar_one_or_none():
            lt = LeaveType(name=name, code=code, is_paid=is_paid, max_days_per_year=max_days)
            db.add(lt)
            print(f"  ✅ Leave Type: {name}")

    # ── 5. Salary Components ───────────────────────────────────────────────────
    components_data = [
        # (name, code, type, is_pct, default_value, is_taxable)
        ("Basic Salary", "BASIC", ComponentType.EARNING, False, 0.0, True),
        ("House Rent Allowance", "HRA", ComponentType.EARNING, True, 40.0, False),
        ("Transport Allowance", "TA", ComponentType.EARNING, False, 1600.0, False),
        ("Special Allowance", "SA", ComponentType.EARNING, False, 0.0, True),
        ("Overtime", "OT", ComponentType.EARNING, False, 0.0, False),
        ("Medical Allowance", "MA", ComponentType.EARNING, False, 1250.0, False),
        ("Advance Deduction", "ADV", ComponentType.DEDUCTION, False, 0.0, False),
        ("Absence Deduction", "ABS_DED", ComponentType.DEDUCTION, False, 0.0, False),
        ("Professional Tax", "PT", ComponentType.DEDUCTION, False, 200.0, False),
        ("Provident Fund", "PF", ComponentType.DEDUCTION, True, 12.0, False),
        ("ESI", "ESI", ComponentType.DEDUCTION, True, 0.75, False),
        ("Other Deduction", "OTH_DED", ComponentType.DEDUCTION, False, 0.0, False),
    ]
    for name, code, comp_type, is_pct, default_val, is_taxable in components_data:
        result = await db.execute(select(SalaryComponent).where(SalaryComponent.code == code))
        if not result.scalar_one_or_none():
            comp = SalaryComponent(
                name=name, code=code, component_type=comp_type,
                is_percentage=is_pct, default_value=default_val, is_taxable=is_taxable,
            )
            db.add(comp)
            print(f"  ✅ Salary Component: {name}")

    # ── 6. System Settings ─────────────────────────────────────────────────────
    settings_data = [
        ("hospital_name", "SPT Hospital", "GENERAL", "Hospital name displayed in reports"),
        ("hospital_address", "", "GENERAL", "Hospital address"),
        ("hospital_phone", "", "GENERAL", "Hospital phone number"),
        ("hospital_email", "", "GENERAL", "Hospital email"),
        ("attendance_grace_period", "15", "ATTENDANCE", "Grace period in minutes before late marking"),
        ("working_days_per_month", "26", "ATTENDANCE", "Default working days per month"),
        ("missing_punch_action", "FLAG", "ATTENDANCE", "Action for missing punch: FLAG or IGNORE"),
        ("ot_rate_multiplier", "1.5", "PAYROLL", "Overtime rate multiplier"),
        ("pay_cycle", "MONTHLY", "PAYROLL", "Payroll cycle: MONTHLY or WEEKLY"),
        ("currency", "INR", "PAYROLL", "Currency code"),
        ("salary_slip_footer", "This is a computer generated salary slip.", "PAYROLL", "Footer text on salary slips"),
    ]
    for key, value, category, description in settings_data:
        result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        if not result.scalar_one_or_none():
            setting = SystemSetting(key=key, value=value, category=category, description=description)
            db.add(setting)
            print(f"  ✅ Setting: {key}")

    await db.flush()

    # ── 7. Admin Users ─────────────────────────────────────────────────────────
    users_data = [
        ("admin", "admin@spthospital.com", "System Administrator", UserRole.SUPER_ADMIN, "Admin@123"),
        ("hr", "hr@spthospital.com", "HR Manager", UserRole.HR_ADMIN, "HR@12345"),
    ]
    for username, email, full_name, role, password in users_data:
        result = await db.execute(select(User).where(User.username == username))
        if not result.scalar_one_or_none():
            user = User(
                username=username,
                email=email,
                full_name=full_name,
                hashed_password=get_password_hash(password),
                role=role,
                is_active=True,
            )
            db.add(user)
            print(f"  ✅ User: {username} ({role.value}) — password: {password}")

    await db.commit()
    print("\n🎉 Database seeding complete!")
    print("\n🔐 Default credentials:")
    print("   Super Admin: admin / Admin@123")
    print("   HR Admin:    hr / HR@12345")


async def main():
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        await seed(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
