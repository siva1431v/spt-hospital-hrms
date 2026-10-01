"""enforce attendance unique constraint

Revision ID: 773142dc6382
Revises: 
Create Date: 2026-10-02 01:22:31.025927
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = '773142dc6382'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        # SQLite: create unique index on (employee_id, attendance_date) if not exists
        op.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_employee_date ON attendance (employee_id, attendance_date)"
        )
    else:
        # Postgres / MySQL
        try:
            op.create_unique_constraint(
                "uq_attendance_employee_date", "attendance", ["employee_id", "attendance_date"]
            )
        except Exception:
            pass


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        op.execute("DROP INDEX IF EXISTS uq_attendance_employee_date")
    else:
        try:
            op.drop_constraint("uq_attendance_employee_date", "attendance", type_="unique")
        except Exception:
            pass

