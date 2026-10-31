from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.admin import AdminRoleChange, AdminUserStatusChange, StaffCreateRequest
from app.schemas.auth import RegisterRequest
from app.schemas.service import ServiceCreate, ServicePatch
from app.services.rate_limit_service import consume_login_attempt
from app.services.storage_service import StorageService
from app.utils.identifiers import normalize_indian_mobile
from app.api.v1 import health
from fastapi import HTTPException
from app.core.config import settings
from app.core.permissions import has_permission
from app.core.security import decode_token, token_digest
from app.schemas.application import CustomerApplicationResponse
from app.api.dependencies import verify_csrf
from app.api.v1.auth import issue_tokens
from app.api.v1.tasks import is_overdue
from bson import ObjectId
from starlette.requests import Request


def test_mobile_normalizer_is_shared_and_strips_formatting():
    assert normalize_indian_mobile("+91 (814) 992-1445") == "8149921445"
    assert normalize_indian_mobile("8149921445") == "8149921445"
    with pytest.raises(ValueError):
        normalize_indian_mobile("12345")

def test_public_registration_cannot_assign_privileged_roles():
    payload = RegisterRequest(
        full_name="Test Customer",
        mobile_number="8149921445",
        password="secure-password-123",
        role="admin",
    )

    assert "role" not in payload.model_dump()


def test_sensitive_mutation_schemas_require_json_values():
    assert AdminRoleChange(role="staff").role == "staff"
    assert AdminUserStatusChange(account_status="suspended").account_status == "suspended"
    with pytest.raises(ValidationError):
        AdminRoleChange(role="owner-admin")
    with pytest.raises(ValidationError):
        StaffCreateRequest(full_name="Staff", mobile_number="12345", password="LongPassword123")


def test_service_patch_accepts_partial_updates():
    assert ServicePatch(category="Tax").model_dump(exclude_unset=True) == {"category": "Tax"}
    assert ServicePatch(form_requirements=[{"id": "phone"}]).model_dump(exclude_unset=True) == {
        "form_requirements": [{"id": "phone"}]
    }
    with pytest.raises(ValidationError):
        ServiceCreate(service_code="ITR", category="Tax")
    with pytest.raises(ValidationError):
        ServiceCreate(service_code="ITR", name={"mr": "सेवा"}, category="Tax", is_published=True)


class FakeRateLimits:
    def __init__(self):
        self.records = {}

    def update_one(self, query, update, upsert=False):
        record = self.records.setdefault(query["_id"], {"count": 0})
        record["count"] += update["$inc"]["count"]
        record.update(update.get("$setOnInsert", {}))

    def find_one(self, query):
        return self.records.get(query["_id"])


class FakeDatabase:
    def __init__(self):
        self.rate_limits = FakeRateLimits()


def test_login_rate_limit_applies_to_ip_and_phone():
    db = FakeDatabase()
    now = datetime(2026, 10, 14, tzinfo=timezone.utc)

    assert all(consume_login_attempt(db, "192.0.2.1", "8149921445", now) for _ in range(5))
    assert not consume_login_attempt(db, "192.0.2.1", "9999999999", now)
    assert not consume_login_attempt(db, "192.0.2.2", "8149921445", now)


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch):
    monkeypatch.setattr(health, "ping", lambda: False)
    with pytest.raises(HTTPException) as error:
        health.ready()
    assert error.value.status_code == 503


def test_readiness_reports_connected_database(monkeypatch):
    monkeypatch.setattr(health, "ping", lambda: True)
    assert health.ready() == {"status": "ready", "database": "connected"}


def test_local_storage_validates_detected_content(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    storage = StorageService()
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"

    key, size = storage.save_bytes(pdf_content, "document.pdf", "image/jpeg")

    assert storage.read_bytes(key) == pdf_content
    assert size == len(pdf_content)
    with pytest.raises(ValueError, match="does not match its extension"):
        storage.save_bytes(pdf_content, "document.jpg", "application/pdf")


def test_upload_declared_size_over_limit_is_rejected():
    with pytest.raises(OverflowError, match="maximum size"):
        StorageService.validate_declared_upload("large.pdf", "application/pdf", settings.max_upload_size_mb * 1024 * 1024 + 1)


def test_s3_upload_url_is_short_lived_and_size_limited(monkeypatch):
    class FakeS3:
        def generate_presigned_post(self, bucket, key, **kwargs):
            self.request = (bucket, key, kwargs)
            return {"url": "https://storage.example", "fields": {"key": key}}

        def copy_object(self, **kwargs):
            self.copy_request = kwargs

        def delete_object(self, **kwargs):
            self.delete_request = kwargs

    monkeypatch.setattr(settings, "storage_provider", "s3")
    monkeypatch.setattr(settings, "storage_bucket", "private-test-bucket")
    client = FakeS3()
    storage = StorageService(s3_client=client)

    url, fields, key = storage.generate_upload_url("document.pdf", "application/pdf", 512)

    assert url == "https://storage.example"
    assert fields["key"] == key
    assert client.request[2]["ExpiresIn"] == 300
    assert key.startswith("pending/")
    assert ["content-length-range", 1, settings.max_upload_size_mb * 1024 * 1024] in client.request[2]["Conditions"]
    final_key = storage.finalize_upload(key, "application-id")
    assert final_key.startswith("applications/application-id/")
    assert client.delete_request["Key"] == key


def test_session_tokens_store_only_refresh_token_digest():
    class FakeSessions:
        def insert_one(self, document):
            self.document = document

    class FakeDatabase:
        def __init__(self):
            self.sessions = FakeSessions()

    database = FakeDatabase()
    access_token, refresh_token = issue_tokens(database, "507f1f77bcf86cd799439011", "test-agent")

    assert database.sessions.document["refresh_token_hash"] == token_digest(refresh_token)
    assert database.sessions.document["refresh_token_hash"] != refresh_token
    assert decode_token(access_token)["sid"] == str(database.sessions.document["_id"])


def test_customer_application_model_excludes_internal_fields():
    response = CustomerApplicationResponse.model_validate({
        "_id": "app-id", "application_number": "USK-1", "service_id": "service-id",
        "service_version": 1, "checklist_snapshot": [], "status": "Draft",
        "form_requirements_snapshot": [{"id": "phone", "label": {"mr": "मोबाईल नंबर"}}],
        "application_data": {"phone": "8149921445"},
        "created_at": "2026-10-14T00:00:00+00:00", "updated_at": "2026-10-14T00:00:00+00:00",
        "internal_notes": "staff-only", "internal_due_date": "2026-10-15T00:00:00+00:00",
    })

    assert "internal_notes" not in response.model_dump()
    assert "internal_due_date" not in response.model_dump()
    assert response.application_data == {"phone": "8149921445"}


def test_permission_overrides_can_restrict_role_defaults():
    assert has_permission({"role": "owner"}, "reports:read")
    assert not has_permission({"role": "owner", "permissions_customized": True, "permissions": []}, "reports:read")


def test_csrf_validation_requires_matching_cookie_and_header():
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [
        (b"cookie", b"csrf_token=csrf-value"), (b"x-csrf-token", b"csrf-value")], "query_string": b""})
    verify_csrf(request)

    invalid_request = Request({"type": "http", "method": "POST", "path": "/", "headers": [
        (b"cookie", b"csrf_token=csrf-value")], "query_string": b""})
    with pytest.raises(HTTPException) as error:
        verify_csrf(invalid_request)
    assert error.value.status_code == 403


def test_task_overdue_calculation_excludes_completed_tasks():
    due_date = datetime(2026, 10, 13, tzinfo=timezone.utc)
    now = datetime(2026, 10, 14, tzinfo=timezone.utc)
    assert is_overdue({"due_date": due_date, "status": "open"}, now)
    assert not is_overdue({"due_date": due_date, "status": "completed"}, now)