import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace

import pytest
from bson import ObjectId
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile

from app.api.dependencies import db_dep
from app.api.v1 import documents
from app.api.v1.tasks import can_read_task
from app.main import app as fastapi_app


class FakeCollection:
    def __init__(self, items=()):
        self.items = list(items)

    def find_one(self, query, sort=None):
        for item in self.items:
            if self.matches_query(item, query):
                return item.copy()
        return None

    @staticmethod
    def matches(actual, expected, present=True):
        if isinstance(expected, dict):
            if "$exists" in expected and present != expected["$exists"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$gte" in expected and (actual is None or actual < expected["$gte"]):
                return False
            if "$lt" in expected and (actual is None or actual >= expected["$lt"]):
                return False
            return True
        return actual == expected

    @classmethod
    def matches_query(cls, item, query):
        for key, expected in query.items():
            if key == "$or":
                if not any(cls.matches_query(item, clause) for clause in expected):
                    return False
            elif key == "$and":
                if not all(cls.matches_query(item, clause) for clause in expected):
                    return False
            elif not cls.matches(item.get(key), expected, key in item):
                return False
        return True

    def update_one(self, query, update):
        for item in self.items:
            if self.matches_query(item, query):
                item.update(update.get("$set", {}))
                for key, value in update.get("$push", {}).items():
                    item.setdefault(key, []).append(value)
                return SimpleNamespace(modified_count=1)
        return SimpleNamespace(modified_count=0)

    def insert_one(self, item):
        self.items.append(item.copy())
        return SimpleNamespace(inserted_id=item.get("_id", ObjectId()))


class FakeDatabase:
    def __init__(self, application, task=None, issued_document=None):
        self.applications = FakeCollection([application])
        self.application_tasks = FakeCollection([task] if task else [])
        self.application_documents = FakeCollection([issued_document] if issued_document else [])
        self.audit_logs = FakeCollection()
        self.notifications = FakeCollection()
        self.users = FakeCollection([{"_id": application["customer_id"], "role": "customer"}] if application.get("customer_id") else [])


def test_owner_can_share_completed_application_document_without_a_task():
    application_id = ObjectId()
    customer_id = ObjectId()
    owner_id = ObjectId()
    document_id = ObjectId()
    database = FakeDatabase(
        {"_id": application_id, "customer_id": customer_id, "application_number": "USK-001",
         "status": "Completed by Shop", "completed_at": datetime.now(timezone.utc)},
        issued_document={
            "_id": document_id,
            "application_id": application_id,
            "customer_id": customer_id,
            "document_kind": "issued",
            "storage_key": "private-final.pdf",
            "shared_at": None,
        },
    )
    owner = {"_id": str(owner_id), "role": "owner"}

    first = documents.share_issued_document(str(application_id), owner, database)
    second = documents.share_issued_document(str(application_id), owner, database)

    assert first["message"] == "Document shared with the customer"
    assert second["message"] == "Document is already shared"
    assert database.application_documents.items[0]["shared_by"] == owner_id
    assert len(database.audit_logs.items) == 1
    assert len(database.notifications.items) == 1
    assert database.notifications.items[0]["recipient_id"] == customer_id


def test_unshared_issued_document_is_not_available_to_its_customer():
    application_id = ObjectId()
    customer_id = ObjectId()
    document_id = ObjectId()
    document = {
        "_id": document_id,
        "application_id": application_id,
        "customer_id": customer_id,
        "document_kind": "issued",
        "storage_key": "private-final.pdf",
        "storage_provider": "local",
        "shared_at": None,
    }
    database = FakeDatabase(
        {"_id": application_id, "customer_id": customer_id, "status": "Completed by Shop",
         "completed_at": datetime.now(timezone.utc)},
        {"application_id": application_id, "status": "completed"},
        document,
    )

    for requesting_user_id in (customer_id, ObjectId()):
        with pytest.raises(HTTPException) as error:
            documents.download_url(
                str(document_id),
                {"_id": str(requesting_user_id), "role": "customer"},
                database,
            )
        assert error.value.status_code == 404


def test_only_matching_customer_can_download_a_shared_issued_document():
    application_id = ObjectId()
    customer_id = ObjectId()
    document_id = ObjectId()
    document = {
        "_id": document_id,
        "application_id": application_id,
        "customer_id": customer_id,
        "document_kind": "issued",
        "storage_key": "private-final.pdf",
        "storage_provider": "local",
        "shared_at": datetime.now(timezone.utc),
    }
    database = FakeDatabase(
        {"_id": application_id, "customer_id": customer_id, "status": "Completed by Shop",
         "completed_at": datetime.now(timezone.utc)},
        issued_document=document,
    )

    response = documents.download_url(
        str(document_id), {"_id": str(customer_id), "role": "customer"}, database
    )
    assert response["download_endpoint"] == f"/api/v1/documents/{document_id}/download"

    with pytest.raises(HTTPException) as error:
        documents.download_url(
            str(document_id), {"_id": str(ObjectId()), "role": "customer"}, database
        )
    assert error.value.status_code == 404


def test_issued_document_cannot_be_shared_before_application_completion():
    application_id = ObjectId()
    customer_id = ObjectId()
    database = FakeDatabase(
        {"_id": application_id, "customer_id": customer_id, "application_number": "USK-001",
         "status": "In Progress"},
        {
            "_id": ObjectId(),
            "application_id": application_id,
            "customer_id": customer_id,
            "document_kind": "issued",
            "storage_key": "private-final.pdf",
            "shared_at": None,
        },
    )

    with pytest.raises(HTTPException) as error:
        documents.share_issued_document(str(application_id), {"_id": str(ObjectId()), "role": "owner"}, database)

    assert error.value.status_code == 409


def test_owner_can_upload_final_document_for_completed_application_without_task(monkeypatch):
    application_id = ObjectId()
    customer_id = ObjectId()
    database = FakeDatabase({
        "_id": application_id,
        "customer_id": customer_id,
        "application_number": "USK-002",
        "status": "Completed by Shop",
        "completed_at": datetime.now(timezone.utc),
    })

    class UploadStorage:
        def validate_declared_upload(self, filename, content_type, size):
            assert filename == "final.pdf"
            assert content_type == "application/pdf"
            assert size > 0

        def detect_content_type(self, content):
            return "application/pdf"

        def save_bytes(self, content, filename, content_type):
            return "private-final.pdf", len(content)

    monkeypatch.setattr(documents, "storage", UploadStorage())
    upload = UploadFile(
        filename="final.pdf",
        file=BytesIO(b"fake pdf contents"),
        headers=Headers({"content-type": "application/pdf"}),
    )
    owner = {"_id": str(ObjectId()), "role": "owner"}

    response = asyncio.run(documents.upload_issued_document(str(application_id), upload, owner, database))

    assert response["file_name"] == "final.pdf"
    assert database.application_documents.items[0]["application_id"] == application_id
    assert database.application_documents.items[0]["customer_id"] == customer_id
    assert database.application_documents.items[0]["shared_at"] is None


def test_owner_can_replace_an_uploaded_but_unshared_final_document(monkeypatch):
    application_id = ObjectId()
    customer_id = ObjectId()
    document_id = ObjectId()
    updated_at = datetime.now(timezone.utc)
    issued_document = {
        "_id": document_id,
        "application_id": application_id,
        "customer_id": customer_id,
        "document_kind": "issued",
        "storage_key": "old-final.pdf",
        "storage_provider": "local",
        "original_filename": "old-final.pdf",
        "file_size": 16,
        "detected_content_type": "application/pdf",
        "updated_at": updated_at,
        "shared_at": None,
        "replacement_history": [],
    }
    database = FakeDatabase({
        "_id": application_id,
        "customer_id": customer_id,
        "application_number": "USK-003",
        "status": "Completed by Shop",
        "completed_at": updated_at,
    }, issued_document=issued_document)

    class UploadStorage:
        def validate_declared_upload(self, filename, content_type, size):
            return "application/pdf"

        def detect_content_type(self, content):
            return "application/pdf"

        def save_bytes(self, content, filename, content_type):
            return "new-final.pdf", len(content)

        def delete(self, key, provider=None):
            raise AssertionError(f"unexpected cleanup for {key}")

    monkeypatch.setattr(documents, "storage", UploadStorage())
    upload = UploadFile(
        filename="new-final.pdf",
        file=BytesIO(b"replacement pdf"),
        headers=Headers({"content-type": "application/pdf"}),
    )

    response = asyncio.run(documents.upload_issued_document(
        str(application_id), upload, {"_id": str(ObjectId()), "role": "owner"}, database
    ))

    assert response["id"] == str(document_id)
    assert database.application_documents.items[0]["storage_key"] == "new-final.pdf"
    assert database.application_documents.items[0]["replacement_history"][0]["storage_key"] == "old-final.pdf"


def test_staff_can_read_only_tasks_assigned_to_them():
    staff_id = ObjectId()
    other_staff_id = ObjectId()
    staff = {"_id": str(staff_id), "role": "staff"}

    assert can_read_task({"assigned_staff_id": staff_id}, staff)
    assert not can_read_task({"assigned_staff_id": other_staff_id}, staff)


def test_completed_task_access_expires_after_45_days():
    now = datetime.now(timezone.utc)
    task = {"status": "completed", "completed_at": now - timedelta(days=46)}
    owner = {"_id": str(ObjectId()), "role": "owner"}
    staff = {"_id": str(ObjectId()), "role": "staff", "assigned_staff_id": None}

    assert not can_read_task(task, owner)
    assert not can_read_task(task, staff)
    assert can_read_task({"status": "completed", "completed_at": now - timedelta(days=45)}, owner)


def test_staff_cannot_share_issued_documents():
    with pytest.raises(HTTPException) as error:
        documents.share_issued_document(
            str(ObjectId()),
            {"_id": str(ObjectId()), "role": "staff"},
            FakeDatabase({}, {}, {}),
        )

    assert error.value.status_code == 403


def test_application_creation_requires_login():
    fastapi_app.dependency_overrides[db_dep] = lambda: None

    async def send_request():
        async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as client:
            return await client.post("/api/v1/applications", json={"service_id": str(ObjectId())})

    try:
        response = asyncio.run(send_request())
    finally:
        fastapi_app.dependency_overrides.clear()

    assert response.status_code == 401
