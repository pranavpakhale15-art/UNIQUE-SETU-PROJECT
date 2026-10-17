from io import BytesIO
from pathlib import Path
import time
import uuid

import boto3
import cloudinary
from cloudinary import uploader as cloudinary_uploader
from cloudinary import utils as cloudinary_utils
import magic

from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png"}

class StorageService:
    """Store files locally, in S3-compatible storage, or as private Cloudinary assets."""
    def __init__(self, s3_client=None, cloudinary_api=None, cloudinary_signer=None):
        self.provider = settings.storage_provider.lower()
        self.bucket = settings.storage_bucket
        self.client = s3_client
        self.base = Path(settings.local_storage_dir).resolve()
        self.cloudinary_api = cloudinary_api or cloudinary_uploader
        self.cloudinary_signer = cloudinary_signer or cloudinary_utils
        if self.provider == "local":
            self.base.mkdir(parents=True, exist_ok=True)
        elif self.provider == "s3":
            self._get_s3_client()
        elif self.provider == "cloudinary":
            self._configure_cloudinary()
        else:
            raise RuntimeError("STORAGE_PROVIDER must be 'local', 's3', or 'cloudinary'")

    @staticmethod
    def _validate_provider(provider: str | None) -> str:
        selected = (provider or settings.storage_provider).lower()
        if selected not in ("local", "s3", "cloudinary"):
            raise RuntimeError("STORAGE_PROVIDER must be 'local', 's3', or 'cloudinary'")
        return selected

    def _get_s3_client(self):
        if self.client is None:
            client_options = {"region_name": settings.storage_region or None}
            if settings.storage_endpoint:
                client_options["endpoint_url"] = settings.storage_endpoint
            if settings.storage_access_key_id and settings.storage_secret_access_key:
                client_options["aws_access_key_id"] = settings.storage_access_key_id
                client_options["aws_secret_access_key"] = settings.storage_secret_access_key
            self.client = boto3.client("s3", **client_options)
        return self.client

    @staticmethod
    def _configure_cloudinary():
        credentials = (
            settings.cloudinary_cloud_name.strip(),
            settings.cloudinary_api_key.strip(),
            settings.cloudinary_api_secret.strip(),
        )
        if not all(credentials):
            raise RuntimeError("Cloudinary credentials are not configured")
        cloudinary.config(
            cloud_name=credentials[0],
            api_key=credentials[1],
            api_secret=credentials[2],
            secure=True,
        )

    @staticmethod
    def provider_for_record(record: dict) -> str:
        provider = record.get("storage_provider")
        if provider:
            return StorageService._validate_provider(provider)
        key = record.get("storage_key")
        if not key:
            raise ValueError("Storage reference is missing")
        return "s3" if key.startswith("applications/") else "local"

    @staticmethod
    def validate_declared_upload(filename: str, content_type: str, file_size: int) -> str:
        extension = Path(filename).suffix.lower()
        expected_type = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(extension)
        if not expected_type or content_type != expected_type:
            raise ValueError("Only PDF, JPEG, and PNG files are accepted")
        if file_size <= 0 or file_size > settings.max_upload_size_mb * 1024 * 1024:
            raise OverflowError("File exceeds configured maximum size")
        return expected_type

    @staticmethod
    def detect_content_type(content: bytes) -> str:
        if not content:
            raise ValueError("Empty file")
        detected_type = magic.from_buffer(content[:8192], mime=True)
        if detected_type not in ALLOWED_TYPES:
            raise ValueError("File content is not an allowed PDF, JPEG, or PNG")
        return detected_type

    def _validate_content(self, content: bytes, original_filename: str) -> str:
        extension = Path(original_filename).suffix.lower()
        detected_type = self.detect_content_type(content)
        expected_type = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(extension)
        if expected_type != detected_type:
            raise ValueError("File content does not match its extension")
        return detected_type

    def save_bytes(
        self,
        content: bytes,
        original_filename: str,
        content_type: str,
        provider: str | None = None,
        resource_type: str = "raw",
        folder: str = "application-documents",
    ) -> tuple[str, int]:
        ext = Path(original_filename).suffix.lower()
        if len(content) > settings.max_upload_size_mb * 1024 * 1024:
            raise OverflowError("File exceeds configured maximum size")
        detected_type = self._validate_content(content, original_filename)
        selected = self._validate_provider(provider)
        if selected == "cloudinary":
            expected_folder = {"raw": "application-documents", "image": "customer-photos"}.get(resource_type)
            if folder != expected_folder:
                raise ValueError("Invalid Cloudinary storage scope")
            self._configure_cloudinary()
            extension = ext if resource_type == "raw" else ""
            key = f"{folder}/{uuid.uuid4().hex}{extension}"
            result = self.cloudinary_api.upload(
                BytesIO(content),
                public_id=key,
                resource_type=resource_type,
                type="authenticated",
                overwrite=False,
                use_filename=False,
                unique_filename=False,
                invalidate=False,
            )
            if result.get("public_id") != key:
                raise RuntimeError("Cloudinary returned an unexpected asset identifier")
        else:
            key = f"{uuid.uuid4().hex}{ext}"
        if selected == "s3":
            self._get_s3_client().put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=detected_type)
        elif selected == "local":
            path = (self.base / key).resolve()
            if self.base not in path.parents:
                raise ValueError("Invalid storage path")
            path.write_bytes(content)
        return key, len(content)

    def generate_upload_url(self, filename: str, content_type: str, file_size: int) -> tuple[str, dict, str]:
        if self.provider != "s3":
            raise RuntimeError("Signed upload URLs require S3-compatible storage")
        detected_extension = Path(filename).suffix.lower()
        self.validate_declared_upload(filename, content_type, file_size)
        key = f"pending/{uuid.uuid4().hex}{detected_extension}"
        signed = self._get_s3_client().generate_presigned_post(
            self.bucket,
            key,
            Fields={"Content-Type": content_type},
            Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, settings.max_upload_size_mb * 1024 * 1024]],
            ExpiresIn=300,
        )
        return signed["url"], signed["fields"], key

    def verify_uploaded_object(
        self, key: str, filename: str, expected_size: int, provider: str | None = None
    ) -> tuple[int, str]:
        if self._validate_provider(provider) != "s3":
            raise RuntimeError("Object verification requires S3-compatible storage")
        client = self._get_s3_client()
        metadata = client.head_object(Bucket=self.bucket, Key=key)
        size = metadata["ContentLength"]
        if size != expected_size or size > settings.max_upload_size_mb * 1024 * 1024:
            raise ValueError("Uploaded file size does not match the upload request")
        sample = client.get_object(Bucket=self.bucket, Key=key, Range="bytes=0-8191")["Body"].read()
        detected_type = self._validate_content(sample, filename)
        return size, detected_type

    def finalize_upload(self, key: str, application_id: str, provider: str | None = None) -> str:
        if self._validate_provider(provider) != "s3":
            return key
        final_key = f"applications/{application_id}/{uuid.uuid4().hex}{Path(key).suffix.lower()}"
        client = self._get_s3_client()
        client.copy_object(Bucket=self.bucket, Key=final_key,
                           CopySource={"Bucket": self.bucket, "Key": key})
        client.delete_object(Bucket=self.bucket, Key=key)
        return final_key

    def generate_download_url(
        self,
        key: str,
        provider: str | None = None,
        resource_type: str = "raw",
        expires_in_seconds: int = 300,
    ) -> str:
        selected = self._validate_provider(provider)
        if selected == "cloudinary":
            if resource_type not in ("raw", "image") or expires_in_seconds <= 0:
                raise ValueError("Invalid Cloudinary download settings")
            self._configure_cloudinary()
            return self.cloudinary_signer.private_download_url(
                key,
                Path(key).suffix.lstrip("."),
                resource_type=resource_type,
                type="authenticated",
                attachment=True,
                expires_at=int(time.time()) + expires_in_seconds,
            )
        if selected != "s3":
            raise RuntimeError("Signed download URLs require S3-compatible storage")
        return self._get_s3_client().generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in_seconds
        )

    def read_bytes(self, key: str, provider: str | None = None) -> bytes:
        selected = self._validate_provider(provider)
        if selected == "s3":
            if not key.startswith("applications/"):
                raise ValueError("Invalid storage key")
            return self._get_s3_client().get_object(Bucket=self.bucket, Key=key)["Body"].read()
        if selected == "cloudinary":
            raise RuntimeError("Cloudinary assets must be delivered through an authorized signed URL")
        if "/" in key or "\\" in key or key.startswith("."):
            raise ValueError("Invalid storage key")
        path = (self.base / key).resolve()
        if self.base not in path.parents or not path.is_file():
            raise FileNotFoundError("File not found")
        return path.read_bytes()

    def delete(self, key: str, provider: str | None = None, resource_type: str = "raw"):
        selected = self._validate_provider(provider)
        if selected == "cloudinary":
            if resource_type not in ("raw", "image"):
                raise ValueError("Invalid Cloudinary resource type")
            self._configure_cloudinary()
            result = self.cloudinary_api.destroy(
                key, resource_type=resource_type, type="authenticated", invalidate=True
            )
            if result.get("result") not in ("ok", "not found"):
                raise RuntimeError("Cloudinary asset deletion failed")
            return
        if selected == "s3":
            self._get_s3_client().delete_object(Bucket=self.bucket, Key=key)
            return
        try:
            (self.base / key).unlink(missing_ok=True)
        except OSError:
            pass
