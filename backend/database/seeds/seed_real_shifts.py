"""
SPT Hospital HRMS — Seed & Migrate Real Hospital Shifts
"""
import asyncio
from datetime import time
from sqlalchemy import select, update
from app.core.database import AsyncSessionLocal
from app.models.shift import Shift
from app.models.employee import Employee

REAL_SHIFTS_DATA = [
    {
        "code": "GS",
        "name": "General (Day)",
        "description": "Largest group — doctors, admin, most nursing/support staff",
        "start_time": time(9, 30),
        "end_time": time(20, 0),
        "is_overnight": False,
        "is_split": False,
        "expected_working_minutes": 630,
        "ot_threshold_minutes": 630,
        "grace_period_minutes": 5,
        "is_active": True,
    },
    {
        "code": "S2",
        "name": "Shift II",
        "description": "10:00 AM – 8:30 PM shift",
        "start_time": time(10, 0),
        "end_time": time(20, 30),
        "is_overnight": False,
        "is_split": False,
        "expected_working_minutes": 630,
        "ot_threshold_minutes": 630,
        "grace_period_minutes": 5,
        "is_active": True,
    },
    {
        "code": "S3",
        "name": "Shift III",
        "description": "9:30 AM – 7:00 PM shift",
        "start_time": time(9, 30),
        "end_time": time(19, 0),
        "is_overnight": False,
        "is_split": False,
        "expected_working_minutes": 570,
        "ot_threshold_minutes": 570,
        "grace_period_minutes": 5,
        "is_active": True,
    },
    {
        "code": "S4",
        "name": "Shift IV",
        "description": "8:30 AM – 6:00 PM Medical shift",
        "start_time": time(8, 30),
        "end_time": time(18, 0),
        "is_overnight": False,
        "is_split": False,
        "expected_working_minutes": 570,
        "ot_threshold_minutes": 570,
        "grace_period_minutes": 5,
        "is_active": True,
    },
    {
        "code": "LAB_SPLIT",
        "name": "Lab Split",
        "description": "Split/rotating shift for Lab (Morning 7:30 AM–5:30 PM / Night 6:30 PM–9:30 AM)",
        "start_time": time(7, 30),
        "end_time": time(17, 30),
        "is_overnight": False,
        "is_split": True,
        "start_time_2": time(18, 30),
        "end_time_2": time(9, 30),
        "is_overnight_2": True,
        "expected_working_minutes": 600,
        "ot_threshold_minutes": 600,
        "grace_period_minutes": 5,
        "is_active": True,
    },
    {
        "code": "HK_SPLIT",
        "name": "House Keeping Split",
        "description": "Split/rotating shift for Housekeeping dept (Morning 8:30 AM–6:30 PM / Night 6:30 PM–8:30 AM)",
        "start_time": time(8, 30),
        "end_time": time(18, 30),
        "is_overnight": False,
        "is_split": True,
        "start_time_2": time(18, 30),
        "end_time_2": time(8, 30),
        "is_overnight_2": True,
        "expected_working_minutes": 600,
        "ot_threshold_minutes": 600,
        "grace_period_minutes": 5,
        "is_active": True,
    },
    {
        "code": "SEC_SPLIT",
        "name": "Security Split",
        "description": "Split/rotating shift for Security dept (Morning 8:00 AM–5:00 PM / Night 5:00 PM–8:00 AM)",
        "start_time": time(8, 0),
        "end_time": time(17, 0),
        "is_overnight": False,
        "is_split": True,
        "start_time_2": time(17, 0),
        "end_time_2": time(8, 0),
        "is_overnight_2": True,
        "expected_working_minutes": 540,
        "ot_threshold_minutes": 540,
        "grace_period_minutes": 5,
        "is_active": True,
    },
    {
        "code": "DIET",
        "name": "Dietitian",
        "description": "9:30 AM – 7:00 PM Dietitian shift",
        "start_time": time(9, 30),
        "end_time": time(19, 0),
        "is_overnight": False,
        "is_split": False,
        "expected_working_minutes": 570,
        "ot_threshold_minutes": 570,
        "grace_period_minutes": 5,
        "is_active": True,
    },
    {
        "code": "NIGHT",
        "name": "Night Shift",
        "description": "7:30 PM – 9:30 AM Night shift for medical & nursing staff",
        "start_time": time(19, 30),
        "end_time": time(9, 30),
        "is_overnight": True,
        "is_split": False,
        "expected_working_minutes": 840,
        "ot_threshold_minutes": 840,
        "grace_period_minutes": 5,
        "is_active": True,
    },
]

SHIFT_ALIASES_DATA = [
    {"device_code": "MS", "shift_code": "GS", "target_window": 1},
    {"device_code": "NTS", "shift_code": "NIGHT", "target_window": 1},
    {"device_code": "HK", "shift_code": "HK_SPLIT", "target_window": 1},
    {"device_code": "HKN", "shift_code": "HK_SPLIT", "target_window": 2},
    {"device_code": "IS", "shift_code": "S2", "target_window": 1},
    {"device_code": "B", "shift_code": "S2", "target_window": 1},
    {"device_code": "GS", "shift_code": "DIET", "target_window": 1},
    {"device_code": "SS", "shift_code": "SEC_SPLIT", "target_window": 1},
    {"device_code": "SNS", "shift_code": "SEC_SPLIT", "target_window": 2},
]

async def seed_real_shifts():
    from app.models.shift import ShiftCodeAlias
    async with AsyncSessionLocal() as db:
        real_codes = {data["code"] for data in REAL_SHIFTS_DATA}

        for data in REAL_SHIFTS_DATA:
            res = await db.execute(select(Shift).where(Shift.code == data["code"]))
            existing = res.scalar_one_or_none()
            if existing:
                for k, v in data.items():
                    setattr(existing, k, v)
                print(f"Updated existing shift {data['code']} (ID {existing.id})")
            else:
                s = Shift(**data)
                db.add(s)
                await db.flush()
                print(f"Created new shift {data['code']} (ID {s.id})")

        await db.flush()

        # Seed Shift Code Aliases
        shift_objs = {s.code: s for s in (await db.execute(select(Shift))).scalars().all()}
        for alias_data in SHIFT_ALIASES_DATA:
            target_shift = shift_objs.get(alias_data["shift_code"])
            if not target_shift:
                continue
            a_res = await db.execute(
                select(ShiftCodeAlias).where(ShiftCodeAlias.device_code == alias_data["device_code"])
            )
            existing_alias = a_res.scalar_one_or_none()
            if existing_alias:
                existing_alias.shift_id = target_shift.id
                existing_alias.target_window = alias_data.get("target_window")
                print(f"Updated alias {alias_data['device_code']} -> {target_shift.code} (window {existing_alias.target_window})")
            else:
                alias = ShiftCodeAlias(
                    device_code=alias_data["device_code"],
                    shift_id=target_shift.id,
                    target_window=alias_data.get("target_window"),
                )
                db.add(alias)
                print(f"Created alias {alias_data['device_code']} -> {target_shift.code} (window {alias.target_window})")

        await db.commit()

        # Print all shifts in DB now
        all_shifts = (await db.execute(select(Shift))).scalars().all()
        print("\n=== CURRENT SHIFTS IN DB ===")
        for s in all_shifts:
            split_str = f" | Split 2: {s.start_time_2}-{s.end_time_2}" if s.is_split else ""
            print(f"ID:{s.id:2d} | Code:{s.code:10s} | Name:{s.name:25s} | Time:{s.start_time}-{s.end_time}{split_str} | Active:{s.is_active}")

if __name__ == "__main__":
    asyncio.run(seed_real_shifts())
