from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from bson import ObjectId
from fastapi import HTTPException
import pytest

from app.api.v1 import documents, notifications


class Cursor:
    def __init__(self, items):
        self.items = list(items)

    def sort(self, key, direction=1):
        self.items.sort(key=lambda item: item.get(key) or datetime.min.replace(tzinfo=timezone.utc), reverse=direction < 0)
        return self

    def skip(self, count):
        self.items = self.items[count:]
        return self

    def limit(self, count):
        self.items = self.items[:count]
        return self

    def __iter__(self):
        return iter([dict(item) for item in self.items])


class Collection:
    def __init__(self, items=()):
        self.items = list(items)

    @staticmethod
    def _matches(item, query):
        for key, expected in query.items():
            value = item.get(key)
            if isinstance(expected, dict):
                if "$exists" in expected and ((key in item) != expected["$exists"]):
                    return False
                if "$ne" in expected and value == expected["$ne"]:
                    return False
                if "$in" in expected and value not in expected["$in"]:
                    return False
            elif value != expected:
                return False
        return True

    def find_one(self, query, sort=None):
        return next((dict(item) for item in self.items if self._matches(item, query)), None)

    def find(self, query):
        return Cursor([item for item in self.items if self._matches(item, query)])

    def count_documents(self, query):
        return sum(self._matches(item, query) for item in self.items)

    def update_one(self, query, update):
        for item in self.items:
            if self._matches(item, query):
                item.update(update.get("$set", {}))
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)


class Database:
    def __init__(self, applications=(), stored_documents=(), notification_records=()):
        self.applications = Collection(applications)
        self.application_documents = Collection(stored_documents)
        self.notifications = Collection(notification_records)
        self.application_tasks = Collection()
        self.services = Collection()


def test_customer_released_document_list_excludes_uploads_unshared_and_other_customers():
    customer_id = ObjectId()
    other_customer_id = ObjectId()
    application_id = ObjectId()
    now = datetime.now(timezone.utc)
    app = {
        "_id": application_id,
        "customer_id": customer_id,
        "application_number": "USK-REL-001",
        "status": "Completed by Shop",
        "completed_at": now,
        "service_snapshot": {"name": {"en": "Domicile certificate"}},
    }
    released = {
        "_id": ObjectId(), "application_id": application_id, "customer_id": customer_id,
        "document_kind": "issued", "storage_key": "private/released.pdf",
        "original_filename": "certificate.pdf", "detected_content_type": "application/pdf",
        "shared_at": now,
    }
    customer_upload = {
        "_id": ObjectId(), "application_id": application_id, "customer_id": customer_id,
        "document_kind": "customer_submission", "storage_key": "private/upload.pdf",
        "original_filename": "identity.pdf", "shared_at": now,
    }
    unshared = {
        "_id": ObjectId(), "application_id": application_id, "customer_id": customer_id,
        "document_kind": "issued", "storage_key": "private/pending.pdf",
        "original_filename": "pending.pdf", "shared_at": None,
    }
    foreign = {
        "_id": ObjectId(), "application_id": application_id, "customer_id": other_customer_id,
        "document_kind": "issued", "storage_key": "private/foreign.pdf",
        "original_filename": "foreign.pdf", "shared_at": now,
    }
    database = Database([app], [released, customer_upload, unshared, foreign])

    response = documents.list_released_documents(1, 20, {"_id": str(customer_id), "role": "customer"}, database)

    assert response["total"] == 1
    assert response["items"][0]["id"] == str(released["_id"])
    assert response["items"][0]["application_number"] == "USK-REL-001"
    assert response["items"][0]["document_type"] == "application/pdf"
    assert "storage_key" not in str(response)


def test_released_document_endpoint_rejects_non_customer():
    with pytest.raises(HTTPException) as error:
        documents.list_released_documents(1, 20, {"_id": str(ObjectId()), "role": "owner"}, Database())
    assert error.value.status_code == 403


def test_unread_document_notifications_are_customer_scoped_and_mark_read_persistently():
    customer_id = ObjectId()
    other_customer_id = ObjectId()
    document_id = ObjectId()
    application_id = ObjectId()
    notification_id = ObjectId()
    unread = {
        "_id": notification_id, "recipient_id": customer_id, "related_application_id": application_id,
        "related_document_id": document_id, "event_type": "document.issued_available", "is_read": False,
        "title": "New document", "message": "Your document is ready", "created_at": datetime.now(timezone.utc),
    }
    foreign = {**unread, "_id": ObjectId(), "recipient_id": other_customer_id}
    document = {"_id": document_id, "application_id": application_id, "customer_id": customer_id, "document_kind": "issued", "shared_at": datetime.now(timezone.utc)}
    application = {"_id": application_id, "customer_id": customer_id, "status": "Completed by Shop", "completed_at": datetime.now(timezone.utc)}
    database = Database(applications=[application], stored_documents=[document], notification_records=[unread, foreign])
    customer = {"_id": str(customer_id), "role": "customer"}

    result = notifications.unread_document_notifications(customer, database)
    assert [item["_id"] for item in result["items"]] == [str(notification_id)]

    with pytest.raises(HTTPException) as error:
        notifications.mark_read(str(notification_id), str(ObjectId()), customer, database)
    assert error.value.status_code == 404
    assert database.notifications.items[0]["is_read"] is False

    notifications.mark_read(str(notification_id), None, customer, database)
    assert database.notifications.items[0]["is_read"] is True
    assert notifications.unread_document_notifications(customer, database)["items"] == []


def test_unread_document_review_message_is_available_without_releasing_customer_upload():
    customer_id = ObjectId()
    application_id = ObjectId()
    uploaded_document_id = ObjectId()
    notification = {
        "_id": ObjectId(), "recipient_id": customer_id, "related_application_id": application_id,
        "related_document_id": uploaded_document_id, "event_type": "document.replacement_requested", "is_read": False,
        "title": "Correction requested", "message": "Please replace the image", "created_at": datetime.now(timezone.utc),
    }
    app = {"_id": application_id, "customer_id": customer_id, "status": "Correction Requested"}
    uploaded_document = {
        "_id": uploaded_document_id, "application_id": application_id, "customer_id": customer_id,
        "document_kind": "customer_submission", "shared_at": None,
    }
    database = Database(applications=[app], stored_documents=[uploaded_document], notification_records=[notification])

    result = notifications.unread_document_notifications({"_id": str(customer_id), "role": "customer"}, database)

    assert len(result["items"]) == 1
    assert result["items"][0]["event_type"] == "document.replacement_requested"


def test_completed_document_search_pipeline_is_paginated_and_searches_document_and_customer_fields():
    from app.api.v1.applications import _completed_documents_pipeline, list_completed_documents

    class Tasks:
        @staticmethod
        def distinct(*_args, **_kwargs):
            return []

    class PipelineDatabase:
        application_tasks = Tasks()

    user_id = ObjectId()
    pipeline = _completed_documents_pipeline(
        {"_id": str(user_id), "role": "owner"}, "Name (A)", 3, 10, PipelineDatabase()
    )

    assert pipeline[0]["$match"]["status"] == "Completed by Shop"
    assert pipeline[-1]["$facet"]["items"][1] == {"$skip": 20}
    assert pipeline[-1]["$facet"]["items"][2] == {"$limit": 10}
    query_stage = next(stage["$match"] for stage in pipeline if "$match" in stage and "$or" in stage["$match"])
    assert query_stage["$or"][0]["issued_document.original_filename"]["$regex"] == r"Name\ \(A\)"
    assert query_stage["$or"][1]["application_number"]["$regex"] == r"Name\ \(A\)"
    assert query_stage["$or"][2]["customer_record.full_name"]["$regex"] == r"Name\ \(A\)"
    assert "$regexMatch" in query_stage["$or"][3]["$expr"]["$or"][0]

    app_id = ObjectId()
    doc_id = ObjectId()
    shared_at = datetime.now(timezone.utc)

    class Applications:
        def __init__(self):
            self.pipeline = None

        def aggregate(self, stages):
            self.pipeline = stages
            return [{"items": [{
                "_id": app_id,
                "application_number": "USK-DOC-01",
                "completed_at": shared_at,
                "service_name_en": "Certificate",
                "customer": {"full_name": "Test Customer"},
                "issued_document": {"id": doc_id, "file_name": "final.pdf", "document_type": "application/pdf", "shared_at": shared_at},
            }], "total": [{"count": 1}]}]

    class EndpointDatabase:
        application_tasks = Tasks()

        def __init__(self):
            self.applications = Applications()

    endpoint_db = EndpointDatabase()
    result = list_completed_documents("final", 2, 5, {"_id": str(user_id), "role": "owner"}, endpoint_db)

    assert result["page"] == 2
    assert result["total"] == 1
    assert result["items"][0]["id"] == str(app_id)
    assert result["items"][0]["issued_document"]["id"] == str(doc_id)

    with pytest.raises(HTTPException) as error:
        list_completed_documents(None, 1, 20, {"_id": str(user_id), "role": "customer"}, endpoint_db)
    assert error.value.status_code == 403
