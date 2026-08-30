"""
Backfill Script:
1. Backfills joining_date = '2026-08-01' for all active employees with joining_date IS NULL.
2. Resolves all historically APPROVED exceptions whose Attendance rows remain incomplete.
"""
import asyncio
import os
import sys
from datetime import date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.attendance import Attendance, AttendanceException, ExceptionReviewStatus
from app.api.v1.endpoints.attendance import backfill_approved_exceptions


async def run_backfill():
    print("--- Running Backfill for Joining Dates and Approved Exceptions ---")
    async with AsyncSessionLocal() as db:
        # 1. Backfill joining_date
        res = await db.execute(
            select(Employee).where(Employee.is_active == True, Employee.joining_date.is_(None))
        )
        null_joining = res.scalars().all()
        for emp in null_joining:
            emp.joining_date = date(2026, 8, 1)
        
        await db.flush()
        print(f"Updated joining_date to 2026-08-01 for {len(null_joining)} active employees.")

        # 2. Backfill approved exceptions
        resolved_count = await backfill_approved_exceptions(db)
        print(f"Resolved {resolved_count} historically approved exceptions.")

        await db.commit()
        print("Backfill completed successfully.")


if __name__ == "__main__":
    asyncio.run(run_backfill())
