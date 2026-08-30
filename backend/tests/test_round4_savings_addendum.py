"""
Regression test suite for Round 4 Addendum: Per-employee savings fund deduction.
Covers:
1. Employee set to 0 gets no savings deduction and no ledger transaction.
2. Three employees with 3 different amounts each get their own figure in payroll and on the slip.
3. An amount larger than payable salary deducts nothing and produces no negative/partial deduction.
4. Changing an amount does not alter a finalized period; applies on next DRAFT recalculation.
5. Recalculating the same DRAFT period twice does not double the ledger credit.
6. Validation & Audit: Rejects negative values, rejects amount > basic salary, records audit logs.
7. Bulk-set savings fund endpoint updates multiple employees atomically with audit logs.
"""
import pytest
from datetime import date, datetime
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, delete, func

from app.main import app
from app.core.security import create_access_token
from app.core.database import AsyncSessionLocal
from app.models.employee import Employee, SecurityFundTransaction
from app.models.attendance import Attendance, AttendanceStatus
from app.models.payroll import PayrollPeriod, PayrollRecord, PayrollItem, PayrollStatus, ComponentType
from app.models.audit import AuditLog
from app.payroll.engine import PayrollEngine


@pytest.fixture
def auth_headers():
    token = create_access_token(subject=1, role="SUPER_ADMIN")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_zero_savings_employee_gets_no_deduction_and_no_ledger(auth_headers):
    """1. An employee set to 0 gets no savings deduction and no ledger transaction."""
    async with AsyncSessionLocal() as db:
        emp = Employee(
            employee_id="TEST_SAV_0",
            biometric_code="9901",
            first_name="Zero",
            last_name="Savings",
            full_name="Zero Savings",
            basic_salary=30000.0,
            security_fund_deduction=0.0,
            is_active=True,
        )
        db.add(emp)
        await db.commit()
        await db.refresh(emp)
        emp_id = emp.id

        period = PayrollPeriod(
            year=2026,
            month=11,
            period_name="November 2026",
            working_days=30,
            status=PayrollStatus.DRAFT,
            created_by_id=1,
        )
        db.add(period)
        await db.commit()
        await db.refresh(period)
        period_id = period.id

    try:
        async with AsyncSessionLocal() as db:
            engine = PayrollEngine(db)
            record, items = await engine.calculate_employee_payroll(
                employee_id=emp_id,
                year=2026,
                month=11,
                period=period,
                override_inputs={"present_days": 30.0},
            )
            assert record.security_fund_deduction == 0.0
            # Ensure no "Staff Savings Fund" in items
            assert not any(i[0] == "Staff Savings Fund" for i in items)

            # Persist record
            db.add(record)
            await db.flush()
            for name, comp_type, amt, _ in items:
                item = PayrollItem(
                    payroll_record_id=record.id,
                    component_name=name,
                    component_type=comp_type,
                    amount=amt,
                )
                db.add(item)
            await db.commit()

            # Verify no ledger transaction created
            txs = (await db.execute(
                select(SecurityFundTransaction).where(SecurityFundTransaction.employee_id == emp_id)
            )).scalars().all()
            assert len(txs) == 0

    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(PayrollItem).where(PayrollItem.payroll_record_id.in_(
                select(PayrollRecord.id).where(PayrollRecord.employee_id == emp_id)
            )))
            await db.execute(delete(PayrollRecord).where(PayrollRecord.employee_id == emp_id))
            await db.execute(delete(PayrollPeriod).where(PayrollPeriod.id == period_id))
            await db.execute(delete(Employee).where(Employee.id == emp_id))
            await db.commit()


@pytest.mark.asyncio
async def test_three_different_savings_amounts_in_payroll_and_slip():
    """2. Three employees with 3 different amounts (0, 350, 800) each get their exact figure in payroll and slip."""
    async with AsyncSessionLocal() as db:
        emp1 = Employee(employee_id="TEST_SAV_A", first_name="A", full_name="Emp A", basic_salary=20000.0, security_fund_deduction=0.0, is_active=True)
        emp2 = Employee(employee_id="TEST_SAV_B", first_name="B", full_name="Emp B", basic_salary=20000.0, security_fund_deduction=350.0, is_active=True)
        emp3 = Employee(employee_id="TEST_SAV_C", first_name="C", full_name="Emp C", basic_salary=20000.0, security_fund_deduction=800.0, is_active=True)
        db.add_all([emp1, emp2, emp3])
        await db.commit()
        for e in [emp1, emp2, emp3]:
            await db.refresh(e)

        period = PayrollPeriod(year=2026, month=11, period_name="November 2026", working_days=30, status=PayrollStatus.DRAFT, created_by_id=1)
        db.add(period)
        await db.commit()
        await db.refresh(period)

        emp_ids = [emp1.id, emp2.id, emp3.id]
        period_id = period.id

    try:
        async with AsyncSessionLocal() as db:
            engine = PayrollEngine(db)
            rec1, items1 = await engine.calculate_employee_payroll(emp1.id, 2026, 11, period=period, override_inputs={"present_days": 30.0})
            rec2, items2 = await engine.calculate_employee_payroll(emp2.id, 2026, 11, period=period, override_inputs={"present_days": 30.0})
            rec3, items3 = await engine.calculate_employee_payroll(emp3.id, 2026, 11, period=period, override_inputs={"present_days": 30.0})

            assert rec1.security_fund_deduction == 0.0
            assert rec2.security_fund_deduction == 350.0
            assert rec3.security_fund_deduction == 800.0

            assert not any(i[0] == "Staff Savings Fund" for i in items1)
            assert any(i[0] == "Staff Savings Fund" and i[2] == 350.0 for i in items2)
            assert any(i[0] == "Staff Savings Fund" and i[2] == 800.0 for i in items3)

    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(PayrollPeriod).where(PayrollPeriod.id == period_id))
            await db.execute(delete(Employee).where(Employee.id.in_(emp_ids)))
            await db.commit()


@pytest.mark.asyncio
async def test_excessive_savings_amount_deducts_nothing():
    """3. An amount larger than payable salary deducts nothing (0.0) rather than making salary negative."""
    async with AsyncSessionLocal() as db:
        # Basic 10,000, but worked only 1 day (earning ~333.33), savings fund set to 500
        emp = Employee(employee_id="TEST_SAV_EXC", first_name="Exc", full_name="Exc", basic_salary=10000.0, security_fund_deduction=500.0, is_active=True)
        db.add(emp)
        await db.commit()
        await db.refresh(emp)
        emp_id = emp.id

        period = PayrollPeriod(year=2026, month=11, period_name="November 2026", working_days=30, status=PayrollStatus.DRAFT, created_by_id=1)
        db.add(period)
        await db.commit()
        await db.refresh(period)
        period_id = period.id

    try:
        async with AsyncSessionLocal() as db:
            engine = PayrollEngine(db)
            rec, items = await engine.calculate_employee_payroll(
                employee_id=emp_id,
                year=2026,
                month=11,
                period=period,
                override_inputs={"present_days": 1.0},  # Earns 333.33, cannot cover 500
            )
            # Available is 333.33 < 500 requested -> Deducts nothing (0.0)
            assert rec.security_fund_deduction == 0.0
            assert rec.net_salary == 333.33
            assert not any(i[0] == "Staff Savings Fund" for i in items)
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(PayrollPeriod).where(PayrollPeriod.id == period_id))
            await db.execute(delete(Employee).where(Employee.id == emp_id))
            await db.commit()


@pytest.mark.asyncio
async def test_changing_savings_amount_does_not_affect_finalized_period():
    """4. Changing an employee's savings amount does not alter a finalized period; applies on next DRAFT recalculation."""
    async with AsyncSessionLocal() as db:
        emp = Employee(employee_id="TEST_SAV_FIN", first_name="Fin", full_name="Fin", basic_salary=25000.0, security_fund_deduction=400.0, is_active=True)
        db.add(emp)
        await db.commit()
        await db.refresh(emp)
        emp_id = emp.id

        period = PayrollPeriod(year=2026, month=11, period_name="November 2026", working_days=30, status=PayrollStatus.FINALIZED, created_by_id=1)
        db.add(period)
        await db.flush()

        rec = PayrollRecord(
            employee_id=emp_id,
            period_id=period.id,
            total_working_days=30,
            present_days=30.0,
            payable_days=30.0,
            basic_salary=25000.0,
            gross_salary=25000.0,
            security_fund_deduction=400.0,
            total_deductions=400.0,
            net_salary=24600.0,
            status=PayrollStatus.FINALIZED,
        )
        db.add(rec)
        await db.commit()
        period_id = period.id
        rec_id = rec.id

    try:
        # Update employee amount to 700
        async with AsyncSessionLocal() as db:
            e_update = (await db.execute(select(Employee).where(Employee.id == emp_id))).scalar_one()
            e_update.security_fund_deduction = 700.0
            await db.commit()

            # Check finalized record unchanged
            rec_check = (await db.execute(select(PayrollRecord).where(PayrollRecord.id == rec_id))).scalar_one()
            assert rec_check.security_fund_deduction == 400.0
            assert rec_check.net_salary == 24600.0

            # But a new DRAFT calculation uses 700.0
            draft_period = PayrollPeriod(year=2026, month=12, period_name="December 2026", working_days=31, status=PayrollStatus.DRAFT, created_by_id=1)
            db.add(draft_period)
            await db.commit()
            await db.refresh(draft_period)
            draft_period_id = draft_period.id

            engine = PayrollEngine(db)
            draft_rec, draft_items = await engine.calculate_employee_payroll(emp_id, 2026, 12, period=draft_period, override_inputs={"present_days": 31.0})
            assert draft_rec.security_fund_deduction == 700.0

    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(PayrollRecord).where(PayrollRecord.employee_id == emp_id))
            await db.execute(delete(PayrollPeriod).where(PayrollPeriod.id.in_([period_id, draft_period_id])))
            await db.execute(delete(Employee).where(Employee.id == emp_id))
            await db.commit()


@pytest.mark.asyncio
async def test_recalculation_idempotency_does_not_double_ledger():
    """5. Recalculating the same DRAFT period twice does not double the ledger credit."""
    async with AsyncSessionLocal() as db:
        emp = Employee(employee_id="TEST_SAV_IDEM", first_name="Idem", full_name="Idem", basic_salary=20000.0, security_fund_deduction=500.0, is_active=True)
        db.add(emp)
        await db.commit()
        await db.refresh(emp)
        emp_id = emp.id

        period = PayrollPeriod(year=2026, month=11, period_name="November 2026", working_days=30, status=PayrollStatus.DRAFT, created_by_id=1)
        db.add(period)
        await db.commit()
        await db.refresh(period)
        period_id = period.id

        # Add 30 attendance days for this employee in November
        for d in range(1, 31):
            att = Attendance(
                employee_id=emp_id,
                attendance_date=date(2026, 11, d),
                check_in_datetime=datetime(2026, 11, d, 9, 30),
                check_out_datetime=datetime(2026, 11, d, 20, 0),
                work_minutes=630,
                status=AttendanceStatus.PRESENT,
            )
            db.add(att)
        await db.commit()

    try:
        async with AsyncSessionLocal() as db:
            engine = PayrollEngine(db)
            # Calculate period twice
            await engine.calculate_all_employees(period, working_days=30, user_id=1)
            await engine.calculate_all_employees(period, working_days=30, user_id=1)

            txs = (await db.execute(
                select(SecurityFundTransaction).where(
                    SecurityFundTransaction.employee_id == emp_id,
                    SecurityFundTransaction.notes == f"Payroll deduction for {period.period_name}"
                )
            )).scalars().all()
            assert len(txs) == 1, "Idempotent recalculation must NOT create duplicate ledger transactions"
            assert float(txs[0].amount) == 500.0
    finally:
        async with AsyncSessionLocal() as db:
            await db.execute(delete(SecurityFundTransaction).where(SecurityFundTransaction.employee_id == emp_id))
            await db.execute(delete(Attendance).where(Attendance.employee_id == emp_id))
            await db.execute(delete(PayrollItem).where(PayrollItem.payroll_record_id.in_(
                select(PayrollRecord.id).where(PayrollRecord.employee_id == emp_id)
            )))
            await db.execute(delete(PayrollRecord).where(PayrollRecord.employee_id == emp_id))
            await db.execute(delete(PayrollPeriod).where(PayrollPeriod.id == period_id))
            await db.execute(delete(Employee).where(Employee.id == emp_id))
            await db.commit()


@pytest.mark.asyncio
async def test_validation_and_bulk_set_savings_api(auth_headers):
    """6 & 7: API rejects negative/exceeding basic salary, and bulk-set endpoint updates atomically with audit logs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create test employee
        async with AsyncSessionLocal() as db:
            emp = Employee(employee_id="TEST_SAV_API", first_name="Api", full_name="Api Emp", basic_salary=15000.0, security_fund_deduction=500.0, is_active=True)
            db.add(emp)
            await db.commit()
            await db.refresh(emp)
            emp_id = emp.id

        try:
            # 1. Reject negative deduction
            neg_res = await client.put(f"/api/v1/employees/{emp_id}", headers=auth_headers, json={"security_fund_deduction": -100})
            assert neg_res.status_code == 422 or neg_res.status_code == 400

            # 2. Reject deduction exceeding basic salary (₹20,000 > ₹15,000)
            exceed_res = await client.put(f"/api/v1/employees/{emp_id}", headers=auth_headers, json={"security_fund_deduction": 20000.0})
            assert exceed_res.status_code == 400
            assert "cannot exceed basic salary" in exceed_res.json()["detail"]

            # 3. Successful single update
            ok_res = await client.put(f"/api/v1/employees/{emp_id}", headers=auth_headers, json={"security_fund_deduction": 650.0})
            assert ok_res.status_code == 200
            assert ok_res.json()["security_fund_deduction"] == 650.0

            # 4. Successful bulk-set update
            bulk_res = await client.post("/api/v1/employees/bulk-set-savings", headers=auth_headers, json={
                "employee_ids": [emp_id],
                "amount": 750.0,
            })
            assert bulk_res.status_code == 200
            assert bulk_res.json()["updated_count"] == 1
            assert bulk_res.json()["amount"] == 750.0

            # Verify in DB and Audit Log
            async with AsyncSessionLocal() as db:
                e_check = (await db.execute(select(Employee).where(Employee.id == emp_id))).scalar_one()
                assert float(e_check.security_fund_deduction) == 750.0

                audits = (await db.execute(
                    select(AuditLog).where(
                        AuditLog.entity_type == "Employee",
                        AuditLog.entity_id == str(emp_id),
                    )
                )).scalars().all()
                assert any("Bulk updated monthly savings fund deduction" in a.description for a in audits)

        finally:
            async with AsyncSessionLocal() as db:
                await db.execute(delete(AuditLog).where(AuditLog.entity_type == "Employee", AuditLog.entity_id == str(emp_id)))
                await db.execute(delete(Employee).where(Employee.id == emp_id))
                await db.commit()
