"""
SPT Hospital HRMS — Migration to 5-minute Grace Period
1. Updates system_settings key 'attendance_grace_period' to '5'.
2. Updates shifts (GS, S2, S3, S4, LAB_SPLIT, HK_SPLIT, SEC_SPLIT, DIET, MS, NS, NTS, HK, HKN, IS, DS, ES) to grace_period_minutes = 5.
3. Re-runs MonthlyStatusReportParser with grace_minutes=5 against the 66-page PDF to update monthly_attendance_aggregates for August 2026.
4. Recalculates any draft/under_review August 2026 payroll periods.
"""
import asyncio
import os
from sqlalchemy import select, update, delete

from app.core.database import AsyncSessionLocal
from app.models.audit import SystemSetting
from app.models.shift import Shift
from app.models.attendance import MonthlyAttendanceAggregate, Attendance
from app.models.employee import Employee
from app.parsers.pdf.monthly_parser import MonthlyStatusReportParser
from app.payroll.engine import PayrollEngine
from app.models.payroll import PayrollPeriod, PayrollStatus

MONTHLY_PDF_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "uploads",
    "pdfs",
    "preview_5ac85198c8a64183901221ef9d48ee6c_Monthly_Attendance_AUG_1_TO_26.pdf",
)


async def update_grace_period():
    async with AsyncSessionLocal() as session:
        # 1. Update system_settings
        res = await session.execute(
            select(SystemSetting).where(SystemSetting.key == "attendance_grace_period")
        )
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = "5"
            print("Updated SystemSetting 'attendance_grace_period' to '5'")
        else:
            setting = SystemSetting(
                key="attendance_grace_period",
                value="5",
                description="Grace period in minutes before late marking",
                category="ATTENDANCE"
            )
            session.add(setting)
            print("Created SystemSetting 'attendance_grace_period' = '5'")

        # 2. Update shifts to grace_period_minutes = 5 (keep custom non-15 overrides like SS=30, B=30 intact if desired, but update the 8 requested shifts and standard shifts)
        target_codes = ["GS", "S2", "S3", "S4", "LAB_SPLIT", "HK_SPLIT", "SEC_SPLIT", "DIET", "MS", "NS", "NTS", "HK", "HKN", "IS", "DS", "ES"]
        await session.execute(
            update(Shift)
            .where(Shift.code.in_(target_codes))
            .values(grace_period_minutes=5)
        )
        print(f"Updated shifts {target_codes} to grace_period_minutes = 5")

        # 3. If PDF exists, re-parse with 5-minute grace and update monthly_attendance_aggregates
        if os.path.exists(MONTHLY_PDF_PATH):
            parser = MonthlyStatusReportParser(MONTHLY_PDF_PATH, grace_minutes=5)
            report = parser.parse()

            emp_res = await session.execute(select(Employee))
            all_emps = emp_res.scalars().all()
            emp_map = {}
            for e in all_emps:
                if e.biometric_code:
                    emp_map[str(e.biometric_code).strip()] = e
                emp_map[str(e.employee_id).strip()] = e

            for agg in report.monthly_aggregates:
                emp = emp_map.get(agg.employee_code.strip())
                if emp:
                    # Update existing aggregate
                    existing_agg_res = await session.execute(
                        select(MonthlyAttendanceAggregate).where(
                            MonthlyAttendanceAggregate.employee_id == emp.id,
                            MonthlyAttendanceAggregate.year == 2026,
                            MonthlyAttendanceAggregate.month == 8,
                        )
                    )
                    existing_agg = existing_agg_res.scalar_one_or_none()
                    if existing_agg:
                        existing_agg.late_days_device = agg.late_days_device
                        existing_agg.late_days_qualifying = agg.late_days_qualifying
                        existing_agg.lop_days = agg.lop_days
                    else:
                        new_agg = MonthlyAttendanceAggregate(
                            employee_id=emp.id,
                            employee_code=agg.employee_code,
                            employee_name=agg.employee_name,
                            department_name=agg.department_name,
                            company_name=agg.company_name,
                            year=2026,
                            month=8,
                            total_work_duration=agg.total_work_duration,
                            total_ot=agg.total_ot,
                            present_count=agg.present_count,
                            absent_count=agg.absent_count,
                            weekly_off_count=agg.weekly_off_count,
                            holidays_count=agg.holidays_count,
                            leaves_taken=agg.leaves_taken,
                            late_by_hrs=agg.late_by_hrs,
                            late_by_days=agg.late_by_days,
                            late_days_device=agg.late_days_device,
                            late_days_qualifying=agg.late_days_qualifying,
                            lop_days=agg.lop_days,
                            early_by_hrs=agg.early_by_hrs,
                            early_going_by_days=agg.early_going_by_days,
                            total_duration_with_ot=agg.total_duration_with_ot,
                            average_working_hrs=agg.average_working_hrs,
                            has_zero_punches=agg.has_zero_punches,
                        )
                        session.add(new_agg)

            total_qual = sum(a.late_days_qualifying for a in report.monthly_aggregates)
            total_lop = sum(a.lop_days for a in report.monthly_aggregates)
            print(f"Updated August 2026 MonthlyAttendanceAggregate with 5m grace: Qualifying Late = {total_qual}, Total LOP = {total_lop}")

        await session.commit()

        # 4. Recalculate August 2026 draft payroll periods
        period_res = await session.execute(
            select(PayrollPeriod).where(
                PayrollPeriod.year == 2026,
                PayrollPeriod.month == 8,
                PayrollPeriod.status != PayrollStatus.FINALIZED,
            )
        )
        periods = period_res.scalars().all()
        engine = PayrollEngine(session)
        for p in periods:
            calculated = await engine.calculate_all_employees(
                period=p,
                working_days=p.working_days,
            )
            print(f"Recalculated PayrollPeriod {p.id} ({p.period_name}): {calculated} records updated.")
        await session.commit()


if __name__ == "__main__":
    asyncio.run(update_grace_period())
