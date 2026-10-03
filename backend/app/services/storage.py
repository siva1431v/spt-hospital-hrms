"""
SPT Hospital HRMS — Unified Storage Service
Supports local filesystem and AWS S3 storage backends with presigned URLs.
"""
import os
import io
import asyncio
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError, BotoCoreError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    logger.warning("boto3 is not installed. AWS S3 storage backend is unavailable.")


class StorageService:
    """
    Unified Storage abstraction for local filesystem and AWS S3.
    """

    def __init__(self):
        self.backend = (settings.STORAGE_BACKEND or "local").lower().strip()
        self.upload_dir = Path(settings.UPLOAD_DIR).resolve()
        self.bucket_name = settings.AWS_S3_BUCKET_NAME
        self.region = settings.AWS_REGION or "ap-south-1"
        self.prefix = (settings.AWS_S3_PREFIX or "").strip("/ ")
        self.endpoint_url = settings.AWS_S3_ENDPOINT_URL
        self._s3_client = None

        # Ensure local directories exist regardless of backend (for temp work)
        os.makedirs(self.upload_dir / "pdfs", exist_ok=True)
        os.makedirs(self.upload_dir / "salary_slips", exist_ok=True)

        if self.is_s3_enabled:
            self._init_s3_client()

    @property
    def is_s3_enabled(self) -> bool:
        return self.backend == "s3" and bool(self.bucket_name) and HAS_BOTO3

    def _init_s3_client(self):
        """Initialize thread-safe boto3 S3 client."""
        client_kwargs: Dict[str, Any] = {
            "service_name": "s3",
            "region_name": self.region,
            "config": Config(
                signature_version=settings.AWS_S3_SIGNATURE_VERSION or "s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        }

        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY

        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        try:
            self._s3_client = boto3.client(**client_kwargs)
            logger.info(
                f"AWS S3 storage initialized: bucket={self.bucket_name}, "
                f"region={self.region}, prefix={self.prefix or '(root)'}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize AWS S3 client: {e}")
            self._s3_client = None

    def _build_s3_key(self, path_or_key: str) -> str:
        """Normalize key by removing duplicate slashes and applying bucket prefix."""
        cleaned = path_or_key.strip().lstrip("/")
        if cleaned.startswith("s3://"):
            parts = cleaned.replace("s3://", "").split("/", 1)
            cleaned = parts[1] if len(parts) > 1 else ""

        if self.prefix and not cleaned.startswith(f"{self.prefix}/"):
            return f"{self.prefix}/{cleaned}"
        return cleaned

    def _build_local_path(self, path_or_key: str) -> Path:
        """Resolve a relative key or absolute path against UPLOAD_DIR safely."""
        cleaned = path_or_key.strip().lstrip("/")
        # If already starts with UPLOAD_DIR
        if os.path.isabs(path_or_key):
            return Path(path_or_key).resolve()
        return (self.upload_dir / cleaned).resolve()

    # ── Upload Operations ───────────────────────────────────────────────────

    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/pdf",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Upload binary data.
        Returns the persistent storage identifier:
        - S3 URI (s3://bucket/key) if S3 backend is active
        - Absolute filesystem path if local backend is active
        """
        if self.is_s3_enabled and self._s3_client:
            s3_key = self._build_s3_key(key)
            extra_args = {"ContentType": content_type}
            if metadata:
                extra_args["Metadata"] = metadata

            def _upload():
                self._s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=data,
                    **extra_args,
                )
                return f"s3://{self.bucket_name}/{s3_key}"

            uri = await asyncio.to_thread(_upload)
            logger.info(f"Uploaded bytes to S3: {uri} ({len(data)} bytes)")
            return uri
        else:
            local_path = self._build_local_path(key)
            local_path.parent.mkdir(parents=True, exist_ok=True)

            def _write():
                with open(local_path, "wb") as f:
                    f.write(data)
                return str(local_path)

            saved_path = await asyncio.to_thread(_write)
            logger.info(f"Saved bytes to local storage: {saved_path} ({len(data)} bytes)")
            return saved_path

    async def upload_file(
        self,
        local_file_path: str,
        key: str,
        content_type: str = "application/pdf",
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Upload an existing local file into storage.
        """
        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"Local file not found: {local_file_path}")

        if self.is_s3_enabled and self._s3_client:
            s3_key = self._build_s3_key(key)
            extra_args = {"ContentType": content_type}
            if metadata:
                extra_args["Metadata"] = metadata

            def _upload():
                self._s3_client.upload_file(
                    Filename=local_file_path,
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    ExtraArgs=extra_args,
                )
                return f"s3://{self.bucket_name}/{s3_key}"

            uri = await asyncio.to_thread(_upload)
            logger.info(f"Uploaded file {local_file_path} to S3: {uri}")
            return uri
        else:
            target_path = self._build_local_path(key)
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if str(Path(local_file_path).resolve()) != str(target_path):
                import shutil
                def _copy():
                    shutil.copy2(local_file_path, target_path)
                    return str(target_path)
                return await asyncio.to_thread(_copy)
            return str(target_path)

    # ── Download & Read Operations ──────────────────────────────────────────

    async def get_bytes(self, path_or_key: str) -> bytes:
        """
        Retrieve file content as raw bytes from S3 or local storage.
        """
        if self.is_s3_enabled and (path_or_key.startswith("s3://") or not os.path.exists(path_or_key)):
            s3_key = self._build_s3_key(path_or_key)

            def _get():
                resp = self._s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
                return resp["Body"].read()

            try:
                return await asyncio.to_thread(_get)
            except ClientError as e:
                logger.error(f"Error fetching from S3 ({s3_key}): {e}")
                raise FileNotFoundError(f"File not found in S3: {s3_key}")
        else:
            local_path = self._build_local_path(path_or_key)
            if not local_path.exists():
                raise FileNotFoundError(f"Local file not found: {local_path}")

            def _read():
                with open(local_path, "rb") as f:
                    return f.read()

            return await asyncio.to_thread(_read)

    async def download_to_file(self, path_or_key: str, target_local_path: str) -> str:
        """
        Ensures a local file copy exists (useful for PDF parsers needing a disk path).
        """
        os.makedirs(os.path.dirname(os.path.abspath(target_local_path)), exist_ok=True)

        if self.is_s3_enabled and (path_or_key.startswith("s3://") or not os.path.exists(path_or_key)):
            s3_key = self._build_s3_key(path_or_key)

            def _download():
                self._s3_client.download_file(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Filename=target_local_path,
                )
                return target_local_path

            return await asyncio.to_thread(_download)
        else:
            local_path = self._build_local_path(path_or_key)
            if not local_path.exists():
                raise FileNotFoundError(f"Source file not found: {local_path}")

            if str(local_path) != str(Path(target_local_path).resolve()):
                import shutil
                def _copy():
                    shutil.copy2(str(local_path), target_local_path)
                    return target_local_path
                return await asyncio.to_thread(_copy)
            return str(local_path)

    # ── Presigned URLs & Existence ──────────────────────────────────────────

    async def generate_presigned_url(
        self,
        path_or_key: str,
        expires_in: Optional[int] = None,
        download_filename: Optional[str] = None,
    ) -> Optional[str]:
        """
        Generates a secure, temporary presigned GET URL for S3 downloads.
        Returns None if S3 is not enabled.
        """
        if not self.is_s3_enabled or not self._s3_client:
            return None

        s3_key = self._build_s3_key(path_or_key)
        expiry = expires_in or settings.AWS_S3_PRESIGNED_URL_EXPIRES_SECONDS or 3600

        params = {"Bucket": self.bucket_name, "Key": s3_key}
        if download_filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_filename}"'

        def _generate():
            return self._s3_client.generate_presigned_url(
                ClientMethod="get_object",
                Params=params,
                ExpiresIn=expiry,
            )

        try:
            return await asyncio.to_thread(_generate)
        except Exception as e:
            logger.error(f"Failed to generate presigned S3 URL for {s3_key}: {e}")
            return None

    async def file_exists(self, path_or_key: str) -> bool:
        """Check if file exists in active storage."""
        if self.is_s3_enabled and (path_or_key.startswith("s3://") or not os.path.exists(path_or_key)):
            s3_key = self._build_s3_key(path_or_key)

            def _check():
                try:
                    self._s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
                    return True
                except ClientError:
                    return False

            return await asyncio.to_thread(_check)
        else:
            local_path = self._build_local_path(path_or_key)
            return local_path.is_file()

    async def delete_file(self, path_or_key: str) -> bool:
        """Deletes file from S3 or local disk."""
        if self.is_s3_enabled and (path_or_key.startswith("s3://") or not os.path.exists(path_or_key)):
            s3_key = self._build_s3_key(path_or_key)

            def _delete():
                try:
                    self._s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
                    return True
                except ClientError as e:
                    logger.error(f"Failed to delete S3 object {s3_key}: {e}")
                    return False

            return await asyncio.to_thread(_delete)
        else:
            local_path = self._build_local_path(path_or_key)
            if local_path.is_file():
                try:
                    local_path.unlink()
                    return True
                except Exception as e:
                    logger.error(f"Failed to delete local file {local_path}: {e}")
                    return False
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Verify storage health and connectivity."""
        if self.is_s3_enabled:
            if not self._s3_client:
                return {
                    "backend": "s3",
                    "status": "error",
                    "detail": "S3 client not initialized. Check credentials.",
                }

            def _check_bucket():
                try:
                    self._s3_client.head_bucket(Bucket=self.bucket_name)
                    return {
                        "backend": "s3",
                        "status": "healthy",
                        "bucket": self.bucket_name,
                        "region": self.region,
                        "prefix": self.prefix,
                    }
                except ClientError as e:
                    code = e.response.get("Error", {}).get("Code", "Unknown")
                    return {
                        "backend": "s3",
                        "status": "unhealthy",
                        "error_code": code,
                        "bucket": self.bucket_name,
                        "region": self.region,
                    }

            return await asyncio.to_thread(_check_bucket)
        else:
            return {
                "backend": "local",
                "status": "healthy",
                "upload_dir": str(self.upload_dir),
                "is_writable": os.access(self.upload_dir, os.W_OK),
            }


# Global singleton instance
storage_service = StorageService()
