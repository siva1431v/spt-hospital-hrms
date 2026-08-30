"""
Standalone Migration Script: Identify and Deactivate Duplicate SPT2xx Employees

Identifies duplicate records in the SPT201–SPT210 range that duplicate existing active hospital staff
(e.g., SPT202 Madesh -> SPT42 Madesh, SPT206 Naveen -> SPT40 Naveen, SPT208 Saran -> SPT61 Saran, etc.)
and deactivates them or merges references.

Usage:
    python scripts/cleanup_duplicate_spt2xx_employees.py [--dry-run]
"""
import argparse
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.employee import Employee


DUPLICATE_MAP = {
    "SPT201": {"name": "Senthil Murugan", "primary_code": "SPT58"},
    "SPT202": {"name": "Madesh", "primary_code": "SPT42"},
    "SPT203": {"name": "Jagathish Siva", "primary_code": "SPT41"},
    "SPT204": {"name": "Ganesh k", "primary_code": "SPT39"},
    "SPT206": {"name": "Naveen", "primary_code": "SPT40"},
    "SPT207": {"name": "Murugesan", "primary_code": "SPT52"},
    "SPT208": {"name": "Saran", "primary_code": "SPT61"},
    "SPT209": {"name": "Selladurai", "primary_code": "SPT62"},
    "SPT210": {"name": "Abinaya", "primary_code": "SPT29"},
}


async def run_cleanup(dry_run: bool = True):
    print(f"--- SPT2xx Duplicate Cleanup Script (dry_run={dry_run}) ---")
    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Employee).where(Employee.employee_id.in_(list(DUPLICATE_MAP.keys())))
        )
        dups = res.scalars().all()

        if not dups:
            print("No matching duplicate SPT2xx employees found in database.")
            return

        for emp in dups:
            info = DUPLICATE_MAP.get(emp.employee_id, {})
            print(f"Found duplicate: ID={emp.id} Code={emp.employee_id} Name={emp.full_name} -> Primary={info.get('primary_code')}")
            if not dry_run:
                emp.is_active = False
                emp.remarks = f"Deactivated: duplicate of primary staff {info.get('primary_code')}"

        if not dry_run:
            await db.commit()
            print(f"Successfully deactivated {len(dups)} duplicate SPT2xx records.")
        else:
            print(f"[Dry Run] Would deactivate {len(dups)} duplicate records. Run without --dry-run to apply.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", default=False)
    args = parser.parse_args()
    asyncio.run(run_cleanup(dry_run=args.dry_run))
