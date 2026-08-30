"""
SPT Hospital HRMS — API v1 Router
Assembles all endpoint routers into a single router.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, employees, departments, shifts, attendance, leaves, payroll, dashboard, reports, settings
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(employees.router)
api_router.include_router(departments.router)
api_router.include_router(shifts.router)
api_router.include_router(attendance.router)
api_router.include_router(leaves.router)
api_router.include_router(payroll.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(settings.router)
