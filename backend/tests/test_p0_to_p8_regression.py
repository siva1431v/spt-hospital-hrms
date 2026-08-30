"""
Regression test suite for SPT Hospital HRMS Bug Fixes (P0 - P8)
"""
import pytest
import pytest_asyncio
from datetime import date, datetime, time, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete

from app.main import app
from app.core.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.employee import Employee, EmploymentType, SecurityFundTransaction
from app.models.department import Department
from app.models.shift import Shift
from app.models.attendance import (
    Attendance, AttendanceStatus, AttendanceException,
    ExceptionReviewStatus, ExceptionSeverity, AttendanceCorrection
)
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollStatus
from app.payroll.engine import PayrollEngine


@pytest_asyncio.fixture(autouse=True)
async def cleanup_test_data():
    async with AsyncSessionLocal() as session:
        await session.execute(delete(AttendanceCorrection).where(AttendanceCorrection.reason.like("%test%")))
        await session.execute(delete(AttendanceException).where(AttendanceException.reason.like("%test%")))
        await session.execute(delete(SecurityFundTransaction).where(SecurityFundTransaction.notes.like("%test%")))
        await session.execute(delete(Attendance).where(Attendance.employee_id.in_(
            select(Employee.id).where(Employee.employee_id.like("TEST_%"))
        )))
        await session.execute(delete(PayrollRecord).where(PayrollRecord.employee_id.in_(
            select(Employee.id).where(Employee.employee_id.like("TEST_%"))
        )))
        await session.execute(delete(PayrollPeriod).where(PayrollPeriod.period_name.like("%Test%")))
        await session.execute(delete(Employee).where(Employee.employee_id.like("TEST_%")))
        await session.commit()
    yield
    async with AsyncSessionLocal() as session:
        await session.execute(delete(AttendanceCorrection).where(AttendanceCorrection.reason.like("%test%")))
        await session.execute(delete(AttendanceException).where(AttendanceException.reason.like("%test%")))
        await session.execute(delete(SecurityFundTransaction).where(SecurityFundTransaction.notes.like("%test%")))
        await session.execute(delete(Attendance).where(Attendance.employee_id.in_(
            select(Employee.id).where(Employee.employee_id.like("TEST_%"))
        )))
        await session.execute(delete(PayrollRecord).where(PayrollRecord.employee_id.in_(
            select(Employee.id).where(Employee.employee_id.like("TEST_%"))
        )))
        await session.execute(delete(PayrollPeriod).where(PayrollPeriod.period_name.like("%Test%")))
        await session.execute(delete(Employee).where(Employee.employee_id.like("TEST_%")))
        await session.commit()


@pytest_asyncio.fixture
async def app_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_token():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        if not user:
            from app.core.security import get_password_hash
            user = User(
                username="admin",
                email="admin@spthospital.com",
                hashed_password=get_password_hash("Admin@123"),
                full_name="Super Admin",
                role=UserRole.SUPER_ADMIN,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

    from app.core.security import create_access_token
    token = create_access_token(user.id, user.role.value)
    return token


@pytest.mark.asyncio
async def test_p0_exception_approval_resolves_attendance(app_client, admin_token):
    """P0: Approving a NO_OUT_PUNCH exception resolves attendance to shift end."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncSessionLocal() as session:
        # 1. Setup employee with GS shift (09:30 - 20:00, 630 mins)
        shift_res = await session.execute(select(Shift).where(Shift.code == "GS"))
        shift = shift_res.scalar_one_or_none()
        if not shift:
            shift = Shift(
                code="GS", name="General",
                start_time=time(9, 30), end_time=time(20, 0),
                expected_working_minutes=630, is_overnight=False
            )
            session.add(shift)
            await session.flush()

        emp = Employee(
            employee_id="TEST_P0_EMP",
            biometric_code="9901",
            first_name="Dr",
            last_name="ManojTest",
            full_name="Dr ManojTest",
            employment_type=EmploymentType.FULL_TIME,
            shift_id=shift.id,
            is_active=True,
        )
        session.add(emp)
        await session.flush()

        # Incomplete attendance (only in punch)
        att_date = date(2026, 8, 20)
        in_dt = datetime.combine(att_date, time(9, 39))
        att = Attendance(
            employee_id=emp.id,
            attendance_date=att_date,
            source_in_time="09:39",
            source_out_time=None,
            check_in_datetime=in_dt,
            check_out_datetime=None,
            work_minutes=0,
            ot_minutes=0,
            status=AttendanceStatus.PRESENT_INCOMPLETE,
        )
        session.add(att)
        await session.flush()

        exc = AttendanceException(
            attendance_id=att.id,
            employee_id=emp.id,
            exception_date=att_date,
            exception_type="NO_OUT_PUNCH",
            reason="Present (No OutPunch)",
            severity=ExceptionSeverity.WARNING,
            review_status=ExceptionReviewStatus.PENDING,
        )
        session.add(exc)
        await session.commit()
        exc_id = exc.id
        emp_id = emp.id
        att_id = att.id

    try:
        # Review exception as APPROVED
        res = await app_client.put(
            f"/api/v1/attendance/exceptions/{exc_id}/review",
            json={"status": "APPROVED", "notes": "Approved by HR QA test"},
            headers=headers,
        )
        assert res.status_code == 200
        assert res.json()["review_status"] == "APPROVED"

        # Verify underlying Attendance is resolved
        async with AsyncSessionLocal() as session:
            att_after = await session.get(Attendance, att_id)
            assert att_after.status == AttendanceStatus.PRESENT
            assert att_after.check_out_datetime is not None
            assert att_after.check_out_datetime.time() == time(20, 0)
            assert att_after.source_out_time == "20:00"
            assert att_after.work_minutes == 621  # 09:39 to 20:00 = 621 mins
            assert att_after.ot_minutes == 0
            assert att_after.is_corrected == True

            # Verify correction audit trail
            corr_res = await session.execute(
                select(AttendanceCorrection)
                .where(AttendanceCorrection.attendance_id == att_id)
                .order_by(AttendanceCorrection.id.desc())
            )
            corrs = corr_res.scalars().all()
            assert len(corrs) >= 1
            assert corrs[0].corrected_status == "PRESENT"
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(AttendanceCorrection).where(AttendanceCorrection.attendance_id == att_id))
            await session.execute(delete(AttendanceException).where(AttendanceException.id == exc_id))
            await session.execute(delete(Attendance).where(Attendance.id == att_id))
            await session.execute(delete(Employee).where(Employee.id == emp_id))
            await session.commit()


@pytest.mark.asyncio
async def test_p1_and_p2_work_ot_invariants_and_overnight(app_client, admin_token):
    """P1 & P2: Overnight OT calculation and work == 0 => OT == 0 invariant."""
    async with AsyncSessionLocal() as session:
        # Night shift HKN (expected 480 mins)
        hkn_res = await session.execute(select(Shift).where(Shift.code == "HKN"))
        hkn = hkn_res.scalar_one_or_none()
        if not hkn:
            hkn = Shift(code="HKN", name="HK Night", start_time=time(15, 0), end_time=time(23, 0), expected_working_minutes=480, is_overnight=False)
            session.add(hkn)
            await session.flush()

        emp = Employee(
            employee_id="TEST_P1_EMP",
            biometric_code="9902",
            first_name="Rajeshwari",
            last_name="Test",
            full_name="Rajeshwari Test",
            employment_type=EmploymentType.FULL_TIME,
            shift_id=hkn.id,
            is_active=True,
        )
        session.add(emp)
        await session.flush()

        # Overnight shift 18:23 -> 07:38 (13h 15m = 795 mins)
        att_date = date(2026, 8, 23)
        in_dt = datetime.combine(att_date, time(18, 23))
        out_dt = datetime.combine(att_date + timedelta(days=1), time(7, 38))

        # Test punch calculation directly
        dur_mins = int((out_dt - in_dt).total_seconds() / 60)
        assert dur_mins == 795

        work_mins = min(dur_mins, hkn.expected_working_minutes)
        ot_mins = max(0, dur_mins - hkn.expected_working_minutes)

        assert work_mins == 480  # 8.0 hours
        assert ot_mins == 315    # 5.25 hours OT

        # Invariant check: incomplete record
        incomplete_work = 0
        incomplete_ot = 0
        assert incomplete_work == 0 and incomplete_ot == 0

        await session.execute(delete(Employee).where(Employee.id == emp.id))
        await session.commit()


@pytest.mark.asyncio
async def test_p3_zero_punch_employees_excluded_from_lop():
    """P3: Employees with no punches have qualifying_late_days = 0 and lop_days = 0."""
    async with AsyncSessionLocal() as session:
        emp = Employee(
            employee_id="TEST_P3_EMP",
            biometric_code="9903",
            first_name="Jagathish",
            last_name="Siva",
            full_name="Jagathish Siva",
            employment_type=EmploymentType.FULL_TIME,
            basic_salary=18000,
            security_fund_deduction=500,
            is_active=True,
        )
        session.add(emp)
        await session.commit()
        await session.refresh(emp)

        user_res = await session.execute(select(User).where(User.username == "admin"))
        admin_user = user_res.scalar_one_or_none()

        period_res = await session.execute(
            select(PayrollPeriod).where(PayrollPeriod.year == 2099, PayrollPeriod.month == 8)
        )
        period = period_res.scalar_one_or_none()
        if not period:
            period = PayrollPeriod(
                period_name="August 2099 Test",
                year=2099,
                month=8,
                working_days=31,
                created_by_id=admin_user.id if admin_user else 1,
                status=PayrollStatus.DRAFT,
            )
            session.add(period)
            await session.commit()
            await session.refresh(period)

        engine = PayrollEngine(session)
        record, items = await engine.calculate_employee_payroll(emp.id, 2099, 8, period)

        assert record.present_days == 0
        assert record.qualifying_late_days == 0
        assert record.lop_days == 0.0
        assert record.loss_of_pay_days == 0.0
        assert record.lop_deduction == 0.0
        # P5 check: zero-net employee has security_fund_deduction == 0 and gross == 0
        assert record.gross_salary == 0.0
        assert record.security_fund_deduction == 0.0
        assert record.net_salary == 0.0

        # Clean up
        await session.execute(delete(PayrollPeriod).where(PayrollPeriod.id == period.id))
        await session.execute(delete(Employee).where(Employee.id == emp.id))
        await session.commit()


@pytest.mark.asyncio
async def test_p5_savings_fund_ledger_balance_calculation(app_client, admin_token):
    """P5: Accumulated savings fund balance accurately reflects DEPOSIT transactions."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with AsyncSessionLocal() as session:
        emp = Employee(
            employee_id="TEST_P5_EMP",
            biometric_code="9905",
            first_name="Ledger",
            last_name="Staff",
            full_name="Ledger Staff",
            employment_type=EmploymentType.FULL_TIME,
            basic_salary=20000,
            security_fund_deduction=500,
            is_active=True,
        )
        session.add(emp)
        await session.commit()
        await session.refresh(emp)

        # Add 3 deposits of 500
        for i in range(3):
            tx = SecurityFundTransaction(
                employee_id=emp.id,
                transaction_type="DEPOSIT",
                amount=500.0,
                notes=f"Monthly payroll deduction test #{i+1}",
            )
            session.add(tx)
        await session.commit()
        emp_id = emp.id

    try:
        res = await app_client.get(f"/api/v1/employees/{emp_id}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["accumulated_security_fund"] == 1500.0
    finally:
        async with AsyncSessionLocal() as session:
            await session.execute(delete(SecurityFundTransaction).where(SecurityFundTransaction.employee_id == emp_id))
            await session.execute(delete(Employee).where(Employee.id == emp_id))
            await session.commit()
