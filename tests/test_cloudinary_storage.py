import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.api.dependencies import current_user, db_dep
from app.api.v1 import auth, documents
from app.core.config import Settings, settings
from app.main import app
from app.services.storage_service import StorageService


PDF_CONTENT = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
JPEG_CONTENT = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


class FakeCloudinaryAPI:
    def __init__(self):
        self.upload_request = None
        self.deleted = None

    def upload(self, file, **kwargs):
        self.upload_request = (file.read(), kwargs)
        return {"public_id": kwargs["public_id"]}

    def destroy(self, public_id, **kwargs):
        self.deleted = (public_id, kwargs)
        return {"result": "ok"}


class FakeCloudinarySigner:
    def __init__(self):
        self.request = None

    def private_download_url(self, public_id, file_format, **kwargs):
        self.request = (public_id, file_format, kwargs)
        return "https://cloudinary.example/signed-private-download"


def configure_cloudinary(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "cloudinary")
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "test-cloud")
    monkeypatch.setattr(settings, "cloudinary_api_key", "test-key")
    monkeypatch.setattr(settings, "cloudinary_api_secret", "test-secret")


def test_cloudinary_settings_require_credentials_and_are_allowed_in_production():
    with pytest.raises(ValidationError, match="CLOUDINARY_CLOUD_NAME"):
        Settings(
            _env_file=None,
            app_env="development",
            jwt_secret_key="test-secret-key-that-is-long-enough",
            storage_provider="cloudinary",
        )

    configured = Settings(
        _env_file=None,
        app_env="production",
        jwt_secret_key="test-secret-key-that-is-long-enough",
        mongodb_uri="mongodb://localhost:27017",
        frontend_origins="https://frontend.example",
        cookie_secure=True,
        storage_provider="cloudinary",
        cloudinary_cloud_name="test-cloud",
        cloudinary_api_key="test-key",
        cloudinary_api_secret="test-secret",
    )

    assert configured.storage_provider == "cloudinary"


def test_cloudinary_upload_uses_backend_generated_private_asset_id(monkeypatch):
    configure_cloudinary(monkeypatch)
    api = FakeCloudinaryAPI()
    storage = StorageService(cloudinary_api=api)

    key, size = storage.save_bytes(PDF_CONTENT, "untrusted-name.pdf", "application/pdf")

    assert key.startswith("application-documents/")
    assert key.endswith(".pdf")
    assert "untrusted-name" not in key
    assert size == len(PDF_CONTENT)
    assert api.upload_request[0] == PDF_CONTENT
    assert api.upload_request[1]["resource_type"] == "raw"
    assert api.upload_request[1]["type"] == "authenticated"
    assert api.upload_request[1]["overwrite"] is False
    assert api.upload_request[1]["use_filename"] is False


def test_cloudinary_signed_download_expires_and_delete_targets_private_asset(monkeypatch):
    configure_cloudinary(monkeypatch)
    api = FakeCloudinaryAPI()
    signer = FakeCloudinarySigner()
    storage = StorageService(cloudinary_api=api, cloudinary_signer=signer)
    monkeypatch.setattr("app.services.storage_service.time.time", lambda: 1_000)

    url = storage.generate_download_url(
        "application-documents/server-id.pdf", provider="cloudinary", expires_in_seconds=300
    )
    storage.delete("application-documents/server-id.pdf", provider="cloudinary")

    assert url.endswith("signed-private-download")
    assert signer.request[0:2] == ("application-documents/server-id.pdf", "pdf")
    assert signer.request[2]["type"] == "authenticated"
    assert signer.request[2]["resource_type"] == "raw"
    assert signer.request[2]["expires_at"] == 1_300
    assert api.deleted[0] == "application-documents/server-id.pdf"
    assert api.deleted[1]["type"] == "authenticated"
    assert api.deleted[1]["resource_type"] == "raw"


def test_legacy_document_provider_is_resolved_without_migration():
    assert StorageService.provider_for_record({"storage_key": "applications/app/file.pdf"}) == "s3"
    assert StorageService.provider_for_record({"storage_key": "a" * 32 + ".pdf"}) == "local"


class FakeCollection:
    def __init__(self, documents=()):
        self.documents = list(documents)

    def find_one(self, query):
        for document in self.documents:
            if all(self._matches(document.get(key), value) for key, value in query.items()):
                return document.copy()
        return None

    @staticmethod
    def _matches(actual, expected):
        if isinstance(expected, dict) and "$gt" in expected:
            return actual is not None and actual > expected["$gt"]
        return actual == expected

    def insert_one(self, document):
        stored = document.copy()
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    def update_one(self, query, update):
        for document in self.documents:
            if not all(self._matches(document.get(key), value) for key, value in query.items()):
                continue
            for key, value in update.get("$set", {}).items():
                document[key] = value
            for key, value in update.get("$push", {}).items():
                document.setdefault(key, []).append(value)
            return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)


class FakeDatabase:
    def __init__(self, application=None, documents=(), users=()):
        self.applications = FakeCollection([application])
        self.application_documents = FakeCollection(documents)
        self.document_upload_intents = FakeCollection()
        self.audit_logs = FakeCollection()
        self.users = FakeCollection(users)


def request(method, path, **kwargs):
    async def send():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(send())


def setup_document_api(monkeypatch, database, user):
    monkeypatch.setattr(settings, "storage_provider", "cloudinary")
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "test-cloud")
    monkeypatch.setattr(settings, "cloudinary_api_key", "test-key")
    monkeypatch.setattr(settings, "cloudinary_api_secret", "test-secret")
    monkeypatch.setattr(documents, "storage", StorageService(cloudinary_api=FakeCloudinaryAPI()))
    app.dependency_overrides[db_dep] = lambda: database
    app.dependency_overrides[current_user] = lambda: user


def test_upload_intent_rejects_invalid_cloudinary_file_content(monkeypatch):
    user_id = ObjectId()
    application_id = ObjectId()
    database = FakeDatabase({
        "_id": application_id,
        "customer_id": user_id,
        "checklist_snapshot": [{"id": "identity"}],
        "status": "Draft",
    })
    user = {"_id": str(user_id), "role": "customer"}
    setup_document_api(monkeypatch, database, user)
    try:
        intent_response = request(
            "POST",
            f"/api/v1/applications/{application_id}/documents/upload-url",
            json={"filename": "identity.pdf", "content_type": "application/pdf",
                  "file_size": 8, "checklist_item_id": "identity"},
        )
        assert intent_response.status_code == 200
        upload_id = intent_response.json()["upload_id"]

        response = request(
            "POST",
            f"/api/v1/applications/{application_id}/documents/confirm",
            data={"upload_id": upload_id},
            files={"file": ("identity.pdf", b"not pdf!", "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert database.document_upload_intents.documents[0]["state"] == "failed"
    assert not database.application_documents.documents


def test_cloudinary_download_authorizes_before_signing(monkeypatch):
    application_id = ObjectId()
    document_id = ObjectId()
    customer_id = ObjectId()
    record = {
        "_id": document_id,
        "application_id": application_id,
        "customer_id": customer_id,
        "storage_key": "application-documents/server-generated.pdf",
        "storage_provider": "cloudinary",
        "storage_resource_type": "raw",
    }
    database = FakeDatabase({"_id": application_id, "customer_id": customer_id}, [record])

    class DownloadStorage:
        def __init__(self):
            self.requests = []

        @staticmethod
        def provider_for_record(_record):
            return "cloudinary"

        def generate_download_url(self, key, **kwargs):
            self.requests.append((key, kwargs))
            return "https://cloudinary.example/short-lived"

    storage = DownloadStorage()
    monkeypatch.setattr(documents, "storage", storage)
    with pytest.raises(HTTPException) as error:
        documents.download_url(
            str(document_id),
            {"_id": str(ObjectId()), "role": "customer"},
            database,
        )
    assert error.value.status_code == 404
    assert not storage.requests

    response = documents.download_url(
        str(document_id),
        {"_id": str(customer_id), "role": "customer"},
        database,
    )

    assert response == {"url": "https://cloudinary.example/short-lived", "expires_in_seconds": 300}
    assert storage.requests[0][1]["provider"] == "cloudinary"

    with pytest.raises(HTTPException) as error:
        documents.download_document(
            str(document_id),
            {"_id": str(ObjectId()), "role": "customer"},
            database,
        )
    assert error.value.status_code == 404
    assert len(storage.requests) == 1

    redirect = documents.download_document(
        str(document_id),
        {"_id": str(customer_id), "role": "customer"},
        database,
    )
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "https://cloudinary.example/short-lived"
    assert len(storage.requests) == 2


def test_cloudinary_replacement_keeps_previous_storage_history(monkeypatch):
    user_id = ObjectId()
    application_id = ObjectId()
    document_id = ObjectId()
    old_record = {
        "_id": document_id,
        "application_id": application_id,
        "customer_id": user_id,
        "checklist_item_id": "identity",
        "storage_key": "legacy-local.pdf",
        "storage_provider": "local",
        "original_filename": "old.pdf",
        "detected_content_type": "application/pdf",
        "file_size": 12,
        "uploaded_by": user_id,
        "created_at": datetime.now(timezone.utc) - timedelta(days=1),
        "verification_status": "correction_requested",
    }
    database = FakeDatabase({
        "_id": application_id,
        "customer_id": user_id,
        "checklist_snapshot": [{"id": "identity"}],
        "status": "Correction Requested",
    }, [old_record])
    user = {"_id": str(user_id), "role": "customer"}
    setup_document_api(monkeypatch, database, user)
    try:
        intent_response = request(
            "POST",
            f"/api/v1/applications/{application_id}/documents/upload-url",
            json={"filename": "replacement.pdf", "content_type": "application/pdf",
                  "file_size": len(PDF_CONTENT), "checklist_item_id": "identity",
                  "replace_document_id": str(document_id)},
        )
        assert intent_response.status_code == 200
        response = request(
            "POST",
            f"/api/v1/applications/{application_id}/documents/confirm",
            data={"upload_id": intent_response.json()["upload_id"]},
            files={"file": ("replacement.pdf", PDF_CONTENT, "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    updated = database.application_documents.documents[0]
    assert updated["storage_provider"] == "cloudinary"
    assert updated["storage_key"].startswith("application-documents/")
    assert updated["replacement_history"][0]["storage_key"] == "legacy-local.pdf"
    assert updated["replacement_history"][0]["storage_provider"] == "local"


def test_customer_can_upload_only_own_profile_photo_to_cloudinary(monkeypatch):
    configure_cloudinary(monkeypatch)
    user_id = ObjectId()
    database = FakeDatabase(users=[{"_id": user_id}])
    user = {"_id": str(user_id), "role": "customer"}
    api = FakeCloudinaryAPI()
    monkeypatch.setattr(auth, "photo_storage", StorageService(cloudinary_api=api))
    app.dependency_overrides[db_dep] = lambda: database
    app.dependency_overrides[current_user] = lambda: user
    try:
        response = request(
            "PUT",
            "/api/v1/auth/me/photo",
            files={"file": ("profile.jpg", JPEG_CONTENT, "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["detected_content_type"] == "image/jpeg"
    photo = database.users.documents[0]["profile_photo"]
    assert photo["storage_provider"] == "cloudinary"
    assert photo["storage_resource_type"] == "image"
    assert photo["storage_key"].startswith("customer-photos/")
    assert api.upload_request[1]["type"] == "authenticated"
    assert api.upload_request[1]["resource_type"] == "image"
    assert "storage_key" not in response.json()


def test_non_customer_cannot_upload_profile_photo(monkeypatch):
    configure_cloudinary(monkeypatch)
    database = FakeDatabase(users=[{"_id": ObjectId()}])
    api = FakeCloudinaryAPI()
    monkeypatch.setattr(auth, "photo_storage", StorageService(cloudinary_api=api))
    app.dependency_overrides[db_dep] = lambda: database
    app.dependency_overrides[current_user] = lambda: {"_id": str(ObjectId()), "role": "staff"}
    try:
        response = request(
            "PUT",
            "/api/v1/auth/me/photo",
            files={"file": ("profile.jpg", JPEG_CONTENT, "image/jpeg")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert api.upload_request is None
