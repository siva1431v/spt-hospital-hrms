"""
SPT Hospital HRMS — Department & Designation Endpoints
"""
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import CurrentUser, require_roles
from app.models.user import UserRole
from app.models.department import Department, Designation
from app.utils.audit import log_audit

router = APIRouter(tags=["Departments & Designations"])


# ─── Departments ────────────────────────────────────────────────────────────────

@router.get("/departments", response_model=dict)
async def list_departments(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
):
    """List all departments."""
    query = select(Department)
    if is_active is not None:
        query = query.where(Department.is_active == is_active)
    if search:
        query = query.where(Department.name.ilike(f"%{search}%"))
    query = query.order_by(Department.name)
    result = await db.execute(query)
    departments = result.scalars().all()
    return {
        "items": [
            {
                "id": d.id,
                "name": d.name,
                "code": d.code,
                "description": d.description,
                "is_active": d.is_active,
                "created_at": d.created_at,
            }
            for d in departments
        ],
        "total": len(departments),
    }


@router.post("/departments", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_department(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    """Create a new department."""
    existing = await db.execute(
        select(Department).where(
            (Department.name == data["name"]) | (Department.code == data["code"])
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Department name or code already exists.")

    dept = Department(
        name=data["name"],
        code=data["code"].upper(),
        description=data.get("description"),
    )
    db.add(dept)
    await db.flush()
    await log_audit(db, current_user.id, "CREATE", "Department", str(dept.id),
                    f"Created department {dept.code}: {dept.name}")
    await db.commit()
    await db.refresh(dept)
    return {"id": dept.id, "name": dept.name, "code": dept.code, "is_active": dept.is_active}


@router.get("/departments/{dept_id}", response_model=dict)
async def get_department(dept_id: int, db: Annotated[AsyncSession, Depends(get_db)], current_user: CurrentUser):
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    return {"id": dept.id, "name": dept.name, "code": dept.code, "description": dept.description, "is_active": dept.is_active}


@router.put("/departments/{dept_id}", response_model=dict)
async def update_department(
    dept_id: int,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    for field in ["name", "code", "description", "is_active"]:
        if field in data:
            setattr(dept, field, data[field])
    await log_audit(db, current_user.id, "UPDATE", "Department", str(dept.id), f"Updated department {dept.name}")
    await db.commit()
    await db.refresh(dept)
    return {"id": dept.id, "name": dept.name, "code": dept.code, "is_active": dept.is_active}


@router.delete("/departments/{dept_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    dept_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN))],
):
    from app.models.employee import Employee
    result = await db.execute(select(Department).where(Department.id == dept_id))
    dept = result.scalar_one_or_none()
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")

    # Check for active employees referencing this department
    emp_count_res = await db.execute(
        select(func.count()).select_from(Employee).where(Employee.department_id == dept_id, Employee.is_active == True)
    )
    emp_count = emp_count_res.scalar() or 0
    if emp_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete department '{dept.name}': {emp_count} active employees are assigned to it. Please reassign or deactivate employees first."
        )

    await db.delete(dept)
    await log_audit(db, current_user.id, "DELETE", "Department", str(dept_id), f"Deleted department {dept.name}")
    await db.commit()


# ─── Designations ───────────────────────────────────────────────────────────────

@router.get("/designations", response_model=dict)
async def list_designations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    department_id: Optional[int] = Query(None),
):
    query = select(Designation)
    if department_id:
        query = query.where(Designation.department_id == department_id)
    query = query.where(Designation.is_active == True).order_by(Designation.name)
    result = await db.execute(query)
    designations = result.scalars().all()
    return {
        "items": [{"id": d.id, "name": d.name, "department_id": d.department_id} for d in designations],
        "total": len(designations),
    }


@router.post("/designations", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_designation(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    desig = Designation(name=data["name"], department_id=data.get("department_id"))
    db.add(desig)
    await db.flush()
    await log_audit(db, current_user.id, "CREATE", "Designation", str(desig.id), f"Created designation {desig.name}")
    await db.commit()
    await db.refresh(desig)
    return {"id": desig.id, "name": desig.name, "department_id": desig.department_id}


@router.put("/designations/{desig_id}", response_model=dict)
async def update_designation(
    desig_id: int,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[object, Depends(require_roles(UserRole.SUPER_ADMIN, UserRole.HR_ADMIN))],
):
    result = await db.execute(select(Designation).where(Designation.id == desig_id))
    desig = result.scalar_one_or_none()
    if not desig:
        raise HTTPException(status_code=404, detail="Designation not found")
    for field in ["name", "department_id", "is_active"]:
        if field in data:
            setattr(desig, field, data[field])
    await db.commit()
    await db.refresh(desig)
    return {"id": desig.id, "name": desig.name, "department_id": desig.department_id}
