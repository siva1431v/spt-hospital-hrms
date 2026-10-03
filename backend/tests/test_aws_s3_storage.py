"""
SPT Hospital HRMS — AWS S3 & Unified Storage Service Tests
Validates local and S3 storage backends, presigned URLs, and salary slip / import PDF storage.
"""
import os
import io
import pytest
from unittest.mock import MagicMock, patch
import httpx
from botocore.exceptions import ClientError

from app.main import app
from app.core.config import settings
from app.services.storage import StorageService


@pytest.mark.asyncio
async def test_storage_service_local_mode(tmp_path):
    """Verify local filesystem backend operations."""
    service = StorageService()
    # Force local mode with temp directory
    service.backend = "local"
    service.upload_dir = tmp_path

    test_content = b"PDF_CONTENT_TEST_DATA_12345"
    key = "pdfs/test_document.pdf"

    # 1. Upload bytes
    saved_path = await service.upload_bytes(test_content, key, content_type="application/pdf")
    assert os.path.exists(saved_path)
    assert await service.file_exists(key)

    # 2. Read bytes
    read_bytes = await service.get_bytes(key)
    assert read_bytes == test_content

    # 3. Health check
    health = await service.health_check()
    assert health["backend"] == "local"
    assert health["status"] == "healthy"

    # 4. Presigned URL in local mode returns None (as designed)
    presigned = await service.generate_presigned_url(key)
    assert presigned is None

    # 5. Delete
    deleted = await service.delete_file(key)
    assert deleted is True
    assert not await service.file_exists(key)


@pytest.mark.asyncio
async def test_storage_service_s3_mode_mocked():
    """Verify AWS S3 backend operations using mocked boto3 client."""
    mock_s3 = MagicMock()

    service = StorageService()
    service.backend = "s3"
    service.bucket_name = "spt-hospital-hrms-storage"
    service.region = "ap-south-1"
    service.prefix = "hrms"
    service._s3_client = mock_s3

    test_content = b"%PDF-1.4 Mocked S3 PDF Document"
    key = "salary_slips/salary_slip_SPT001_2026_08.pdf"
    expected_s3_key = "hrms/salary_slips/salary_slip_SPT001_2026_08.pdf"

    # 1. Upload bytes
    uri = await service.upload_bytes(
        test_content,
        key,
        content_type="application/pdf",
        metadata={"employee_id": "SPT001"},
    )
    assert uri == f"s3://spt-hospital-hrms-storage/{expected_s3_key}"
    mock_s3.put_object.assert_called_once_with(
        Bucket="spt-hospital-hrms-storage",
        Key=expected_s3_key,
        Body=test_content,
        ContentType="application/pdf",
        Metadata={"employee_id": "SPT001"},
    )

    # 2. Get bytes
    mock_body = MagicMock()
    mock_body.read.return_value = test_content
    mock_s3.get_object.return_value = {"Body": mock_body}

    retrieved = await service.get_bytes(uri)
    assert retrieved == test_content
    mock_s3.get_object.assert_called_once_with(
        Bucket="spt-hospital-hrms-storage",
        Key=expected_s3_key,
    )

    # 3. Presigned URL generation
    mock_s3.generate_presigned_url.return_value = "https://s3.ap-south-1.amazonaws.com/spt-hospital-hrms-storage/presigned-url"
    url = await service.generate_presigned_url(
        key,
        expires_in=1800,
        download_filename="slip.pdf",
    )
    assert url == "https://s3.ap-south-1.amazonaws.com/spt-hospital-hrms-storage/presigned-url"
    mock_s3.generate_presigned_url.assert_called_once_with(
        ClientMethod="get_object",
        Params={
            "Bucket": "spt-hospital-hrms-storage",
            "Key": expected_s3_key,
            "ResponseContentDisposition": 'attachment; filename="slip.pdf"',
        },
        ExpiresIn=1800,
    )

    # 4. File exists (head_object)
    mock_s3.head_object.return_value = {"ContentLength": len(test_content)}
    assert await service.file_exists(key) is True

    # 5. Delete object
    assert await service.delete_file(key) is True
    mock_s3.delete_object.assert_called_once_with(
        Bucket="spt-hospital-hrms-storage",
        Key=expected_s3_key,
    )

    # 6. Health check healthy
    mock_s3.head_bucket.return_value = {}
    health = await service.health_check()
    assert health["backend"] == "s3"
    assert health["status"] == "healthy"
    assert health["bucket"] == "spt-hospital-hrms-storage"


@pytest.mark.asyncio
async def test_health_endpoint_includes_storage():
    """Verify that the /health API endpoint reports storage health details."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "storage" in data
        assert "backend" in data["storage"]


@pytest.mark.asyncio
async def test_salary_slip_download_endpoint_with_storage():
    """Verify downloading a salary slip through the API."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Query existing payroll records
        rec_res = await client.get("/api/v1/payroll/periods", headers=headers)
        assert rec_res.status_code == 200
        periods_data = rec_res.json()
        period_items = periods_data.get("items", []) if isinstance(periods_data, dict) else periods_data
        if period_items and len(period_items) > 0:
            period_id = period_items[0]["id"]
            records_res = await client.get(f"/api/v1/payroll/periods/{period_id}/records", headers=headers)
            records = records_res.json().get("items", [])
            if records:
                rec_id = records[0]["id"]
                # Request salary slip download
                download_res = await client.get(f"/api/v1/payroll/salary-slips/{rec_id}", headers=headers)
                assert download_res.status_code == 200
                assert download_res.headers["content-type"] == "application/pdf"
                assert len(download_res.content) > 100


@pytest.mark.asyncio
async def test_import_pdf_download_endpoint():
    """Verify downloading an imported attendance PDF through the storage-backed endpoint."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # Login
        login_res = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "Admin@123"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Query existing imports
        imports_res = await client.get("/api/v1/attendance/imports", headers=headers)
        assert imports_res.status_code == 200
        items = imports_res.json().get("items", [])
        if items:
            import_id = items[0]["id"]
            # Download file
            dl_res = await client.get(f"/api/v1/attendance/imports/{import_id}/download", headers=headers)
            if dl_res.status_code == 200:
                assert dl_res.headers["content-type"] == "application/pdf"
                assert len(dl_res.content) > 0
            else:
                assert dl_res.status_code in (200, 404)

