"""
SPT Hospital HRMS — PDF Employee Sync Script
Extracts all unique employees from the PDF report and syncs them to the database.
"""
import asyncio
import os
import re
from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.employee import Employee
from app.models.department import Department
from app.parsers.pdf.parser import EsslPdfParser

PDF_PATH = "/Users/siva/Desktop/Projects/spt-hospital-hrms/Daily Attendance Report AUG.pdf"

async def sync_employees():
    if not os.path.exists(PDF_PATH):
        print(f"PDF report not found at {PDF_PATH}")
        return

    parser = EsslPdfParser(PDF_PATH)
    report = parser.parse()

    # Collect unique employees from PDF
    pdf_employees = {}
    for r in report.all_records:
        code = str(r.employee_code).strip()
        name = (r.employee_name or f"Staff {code}").strip()
        dept = (r.department_name or "Default").strip()
        if code not in pdf_employees:
            pdf_employees[code] = {"code": code, "name": name, "dept": dept}

    print(f"Extracted {len(pdf_employees)} unique employees from PDF.")

    async with AsyncSessionLocal() as db:
        # Ensure all departments exist
        res_dept = await db.execute(select(Department))
        depts = res_dept.scalars().all()
        dept_by_name = {d.name.upper().strip(): d for d in depts}
        dept_by_code = {d.code.upper().strip(): d for d in depts if d.code}

        for info in pdf_employees.values():
            d_name = info["dept"]
            d_name_key = d_name.upper().strip()
            d_code_key = d_name_key.replace(" ", "_")[:10]

            if d_name_key not in dept_by_name and d_code_key not in dept_by_code:
                new_dept = Department(
                    name=d_name,
                    code=d_code_key,
                    description=f"{d_name} Department",
                    is_active=True,
                )
                db.add(new_dept)
                await db.flush()
                dept_by_name[d_name_key] = new_dept
                dept_by_code[d_code_key] = new_dept

        # Reload departments map
        res_dept_2 = await db.execute(select(Department))
        depts_2 = res_dept_2.scalars().all()
        dept_map = {}
        for d in depts_2:
            dept_map[d.name.upper().strip()] = d
            if d.code:
                dept_map[d.code.upper().strip()] = d

        # Create or update employees from PDF
        valid_biocodes = set(pdf_employees.keys())
        created_count = 0
        updated_count = 0

        # Load existing employees
        res_emp = await db.execute(select(Employee))
        existing_emps = res_emp.scalars().all()
        emp_by_code = {}
        for e in existing_emps:
            if e.biometric_code:
                emp_by_code[str(e.biometric_code).strip()] = e
            num_part = re.sub(r"^[^\d]+", "", str(e.employee_id))
            if num_part:
                emp_by_code[num_part] = e

        for code, info in pdf_employees.items():
            name_parts = info["name"].split(maxsplit=1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            full_name = info["name"]

            d_key = info["dept"].upper().strip()
            d_code_key = d_key.replace(" ", "_")[:10]
            dept_obj = dept_map.get(d_key) or dept_map.get(d_code_key)
            dept_id = dept_obj.id if dept_obj else None
            emp_id_code = f"SPT{code}"

            if code in emp_by_code:
                emp = emp_by_code[code]
                emp.first_name = first_name
                emp.last_name = last_name
                emp.full_name = full_name
                emp.department_id = dept_id
                emp.biometric_code = code
                emp.is_active = True
                updated_count += 1
            else:
                emp = Employee(
                    employee_id=emp_id_code,
                    biometric_code=code,
                    first_name=first_name,
                    last_name=last_name,
                    full_name=full_name,
                    department_id=dept_id,
                    is_active=True,
                    basic_salary=25000.00,
                    employment_type="FULL_TIME",
                )
                db.add(emp)
                created_count += 1

        await db.flush()

        # Deactivate non-PDF employees
        res_emp_all = await db.execute(select(Employee))
        all_emps = res_emp_all.scalars().all()
        deactivated_count = 0

        for e in all_emps:
            code_str = str(e.biometric_code).strip() if e.biometric_code else ""
            num_part = re.sub(r"^[^\d]+", "", str(e.employee_id))
            if code_str not in valid_biocodes and num_part not in valid_biocodes:
                e.is_active = False
                deactivated_count += 1

        await db.commit()
        print(f"Sync finished: {created_count} created, {updated_count} updated, {deactivated_count} non-PDF employees deactivated.")

if __name__ == "__main__":
    asyncio.run(sync_employees())
