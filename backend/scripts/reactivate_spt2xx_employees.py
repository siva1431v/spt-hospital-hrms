"""
Script to reactivate all SPT2xx employees (SPT201 to SPT210).
They represent legitimate secondary biometric device enrolments (e.g. Old Bio device).
"""
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.employee import Employee


async def reactivate_spt2xx():
    print("--- Reactivating SPT2xx Employees ---")
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Employee).where(
                Employee.employee_id.in_([
                    "SPT201", "SPT202", "SPT203", "SPT204", "SPT205",
                    "SPT206", "SPT207", "SPT208", "SPT209", "SPT210"
                ])
            )
        )
        spt2xx = res.scalars().all()
        from datetime import date
        for emp in spt2xx:
            emp.is_active = True
            emp.joining_date = date(2026, 8, 1)
            emp.remarks = "Active secondary biometric enrolment"
            print(f"Reactivated: {emp.employee_id} ({emp.biometric_code}) - {emp.full_name}")

        await db.commit()
        print(f"Successfully reactivated {len(spt2xx)} SPT2xx employees.")


if __name__ == "__main__":
    asyncio.run(reactivate_spt2xx())
