"""
Tests for duplicate attendance PDF import detection and attendance unique constraint enforcement.
"""
import os
import pytest
from datetime import date
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.models.attendance import Attendance, AttendanceImport
from app.services.attendance_import import AttendanceImportService

_FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "Monthly_Status_Report_Aug_1_to_24.pdf")
_REPO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Monthly_Status_Report_Aug_1_to_24.pdf")

if os.path.exists(_FIXTURE_PATH):
    SAMPLE_PDF_PATH = _FIXTURE_PATH
elif os.path.exists(_REPO_PATH):
    SAMPLE_PDF_PATH = _REPO_PATH
else:
    SAMPLE_PDF_PATH = None


@pytest.mark.asyncio
async def test_duplicate_pdf_detection_and_duplicate_counting():
    if not SAMPLE_PDF_PATH or not os.path.exists(SAMPLE_PDF_PATH):
        pytest.skip("Sample PDF not found")

    async with AsyncSessionLocal() as db:
        service = AttendanceImportService(db=db, user_id=1)

        # 1. First preview
        preview_1 = await service.preview(
            pdf_path=SAMPLE_PDF_PATH,
            filename="Test_Report_Aug.pdf",
            file_size=os.path.getsize(SAMPLE_PDF_PATH),
        )
        assert preview_1["report_type"] == "Monthly Status Report (Summary Report)"

        # 2. First commit
        commit_1 = await service.commit(
            preview_data=preview_1,
            duplicate_action="skip",
        )
        assert commit_1["status"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS")

        # 3. Second preview with identical file -> SHA-256 duplicate file detection
        preview_2 = await service.preview(
            pdf_path=SAMPLE_PDF_PATH,
            filename="Test_Report_Aug_Reupload.pdf",
            file_size=os.path.getsize(SAMPLE_PDF_PATH),
        )
        assert preview_2["is_duplicate_file"] is True
        assert preview_2["existing_import"] is not None
        assert preview_2["existing_import"]["id"] == commit_1["import_id"]

        # 4. Second commit with 'skip' -> 0 newly imported, duplicates accurately reported
        commit_2 = await service.commit(
            preview_data=preview_2,
            duplicate_action="skip",
        )
        print("COMMIT_1:", commit_1)
        print("COMMIT_2:", commit_2)
        assert commit_2["imported"] == 0
        assert commit_2["duplicates"] > 0

        # 5. Check attendance_imports table has accurate duplicate count
        imp_row = await db.execute(
            select(AttendanceImport).where(AttendanceImport.id == commit_2["import_id"])
        )
        imp = imp_row.scalar_one()
        assert imp.records_imported == 0
        assert imp.records_duplicate > 0


@pytest.mark.asyncio
async def test_attendance_unique_constraint():
    """Verify unique constraint on (employee_id, attendance_date)."""
    async with AsyncSessionLocal() as db:
        rec1 = Attendance(
            employee_id=1,
            attendance_date=date(2025, 1, 15),
            source_in_time="09:00",
            source_out_time="17:00",
            work_minutes=480,
            status="PRESENT",
        )
        db.add(rec1)
        await db.commit()
        await db.refresh(rec1)
        rec1_id = rec1.id

        try:
            # Attempt to insert duplicate record with same employee_id and date
            rec2 = Attendance(
                employee_id=1,
                attendance_date=date(2025, 1, 15),
                source_in_time="10:00",
                source_out_time="18:00",
                work_minutes=480,
                status="PRESENT",
            )
            db.add(rec2)
            with pytest.raises(IntegrityError):
                await db.commit()

            await db.rollback()
        finally:
            # Clean up rec1 so test database state is isolated
            await db.execute(delete(Attendance).where(Attendance.id == rec1_id))
            await db.commit()
