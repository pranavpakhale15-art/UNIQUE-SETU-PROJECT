from datetime import datetime, timedelta, timezone

from bson import ObjectId

from app.api.v1.applications import (
    _final_document_work,
    _shared_completed_application_ids,
    application_dashboard_section,
    sort_applications_by_progress,
)


class FakeCollection:
    def __init__(self, records=()):
        self.records = list(records)

    @classmethod
    def matches(cls, record, query):
        for field, expected in query.items():
            if field == "$or":
                if not any(cls.matches(record, clause) for clause in expected):
                    return False
                continue
            if field == "$and":
                if not all(cls.matches(record, clause) for clause in expected):
                    return False
                continue
            actual = record.get(field)
            if isinstance(expected, dict):
                if "$exists" in expected and (field in record) != expected["$exists"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$gte" in expected and (actual is None or actual < expected["$gte"]):
                    return False
                if "$lt" in expected and (actual is None or actual >= expected["$lt"]):
                    return False
                if "$nin" in expected and actual in expected["$nin"]:
                    return False
            elif actual != expected:
                return False
        return True

    def find(self, query):
        return [record.copy() for record in self.records if self.matches(record, query)]

    def find_one(self, query, sort=None):
        return next((record.copy() for record in self.records if self.matches(record, query)), None)

    def distinct(self, field, query):
        return list({
            record.get(field)
            for record in self.records
            if self.matches(record, query) and record.get(field) is not None
        })


class FakeDatabase:
    def __init__(self, applications, documents, customer_id, tasks=()):
        self.applications = FakeCollection(applications)
        self.application_documents = FakeCollection(documents)
        self.application_tasks = FakeCollection(tasks)
        self.application_status_history = FakeCollection()
        self.services = FakeCollection()
        self.users = FakeCollection([{
            "_id": customer_id,
            "full_name": "Test Customer",
            "mobile_number": "9999999999",
            "email": "customer@example.test",
        }])


def test_completed_application_sections_are_exclusive_and_bound_to_matching_customer():
    now = datetime.now(timezone.utc)
    customer_id = ObjectId()
    application_without_document = ObjectId()
    application_with_unshared_document = ObjectId()
    application_with_foreign_shared_document = ObjectId()
    application_with_shared_document = ObjectId()
    applications = [
        {
            "_id": application_id,
            "customer_id": customer_id,
            "application_number": str(index),
            "service_id": ObjectId(),
            "status": "Completed by Shop",
            "completed_at": now - timedelta(days=index),
            "updated_at": now,
        }
        for index, application_id in enumerate((
            application_without_document,
            application_with_unshared_document,
            application_with_foreign_shared_document,
            application_with_shared_document,
        ))
    ]
    documents = [
        {
            "_id": ObjectId(),
            "application_id": application_with_unshared_document,
            "customer_id": customer_id,
            "document_kind": "issued",
            "storage_key": "pending-share.pdf",
            "original_filename": "pending-share.pdf",
        },
        {
            "_id": ObjectId(),
            "application_id": application_with_foreign_shared_document,
            "customer_id": ObjectId(),
            "document_kind": "issued",
            "storage_key": "foreign.pdf",
            "shared_at": now,
        },
        {
            "_id": ObjectId(),
            "application_id": application_with_shared_document,
            "customer_id": customer_id,
            "document_kind": "issued",
            "storage_key": "shared.pdf",
            "original_filename": "shared.pdf",
            "shared_at": now,
        },
    ]
    database = FakeDatabase(applications, documents, customer_id)
    owner = {"_id": str(ObjectId()), "role": "owner"}

    awaiting = _final_document_work(database, owner, shared=False)
    completed = _final_document_work(database, owner, shared=True)

    assert {item["id"] for item in awaiting} == {
        str(application_without_document),
        str(application_with_unshared_document),
        str(application_with_foreign_shared_document),
    }
    assert {item["id"] for item in completed} == {str(application_with_shared_document)}
    assert {item["id"] for item in awaiting}.isdisjoint({item["id"] for item in completed})
    assert next(item for item in awaiting if item["id"] == str(application_with_unshared_document))[
        "final_document_status"
    ] == "Uploaded, not shared"


def test_active_application_filter_uses_only_a_matching_shared_issued_document():
    customer_id = ObjectId()
    shared_application_id = ObjectId()
    mismatched_application_id = ObjectId()
    applications = [
        {
            "_id": shared_application_id,
            "customer_id": customer_id,
            "status": "Completed by Shop",
        },
        {
            "_id": mismatched_application_id,
            "customer_id": customer_id,
            "status": "Completed by Shop",
        },
    ]
    documents = [
        {
            "_id": ObjectId(),
            "application_id": shared_application_id,
            "customer_id": customer_id,
            "document_kind": "issued",
            "shared_at": datetime.now(timezone.utc),
        },
        {
            "_id": ObjectId(),
            "application_id": mismatched_application_id,
            "customer_id": ObjectId(),
            "document_kind": "issued",
            "shared_at": datetime.now(timezone.utc),
        },
    ]
    database = FakeDatabase(applications, documents, customer_id)

    assert _shared_completed_application_ids(database) == [shared_application_id]


def test_in_progress_applications_sort_by_workflow_then_recent_update():
    now = datetime.now(timezone.utc)
    records = [
        {"application_number": "draft", "status": "Draft", "updated_at": now},
        {"application_number": "processing-old", "status": "In Progress", "updated_at": now - timedelta(days=1)},
        {"application_number": "processing-new", "status": "In Progress", "updated_at": now},
        {"application_number": "authority", "status": "Awaiting Government Decision", "updated_at": now},
    ]

    result = sort_applications_by_progress(records)

    assert [record["application_number"] for record in result] == [
        "authority",
        "processing-new",
        "processing-old",
        "draft",
    ]


def test_only_centre_completed_applications_enter_share_or_completed_sections():
    issued_shared = {"shared_at": datetime.now(timezone.utc)}
    issued_unshared = {"storage_key": "private.pdf"}

    assert application_dashboard_section({"status": "In Progress"}, issued_shared) == "in_progress"
    assert application_dashboard_section({"status": "Completed by Shop"}, issued_unshared) == "awaiting_customer_sharing"
    assert application_dashboard_section({"status": "Completed by Shop"}, issued_shared) == "completed"


def test_customer_completed_applications_are_scoped_to_their_own_records():
    now = datetime.now(timezone.utc)
    customer_id = ObjectId()
    other_customer_id = ObjectId()
    own_application_id = ObjectId()
    other_application_id = ObjectId()
    applications = [
        {
            "_id": own_application_id,
            "customer_id": customer_id,
            "application_number": "OWN-001",
            "status": "Completed by Shop",
            "completed_at": now,
        },
        {
            "_id": other_application_id,
            "customer_id": other_customer_id,
            "application_number": "OTHER-001",
            "status": "Completed by Shop",
            "completed_at": now,
        },
    ]
    documents = [
        {
            "_id": ObjectId(),
            "application_id": application["_id"],
            "customer_id": application["customer_id"],
            "document_kind": "issued",
            "storage_key": "private.pdf",
            "shared_at": now,
        }
        for application in applications
    ]
    database = FakeDatabase(applications, documents, customer_id)

    result = _final_document_work(database, {"_id": str(customer_id), "role": "customer"}, shared=True)

    assert [item["id"] for item in result] == [str(own_application_id)]
    assert result[0]["customer"] is None


def test_completed_application_is_not_listed_after_its_45_day_window():
    now = datetime.now(timezone.utc)
    customer_id = ObjectId()
    application_id = ObjectId()
    old_completed_at = now - timedelta(days=46)
    application = {
        "_id": application_id,
        "customer_id": customer_id,
        "application_number": "OLD-001",
        "status": "Completed by Shop",
        "completed_at": old_completed_at,
    }
    document = {
        "_id": ObjectId(),
        "application_id": application_id,
        "customer_id": customer_id,
        "document_kind": "issued",
        "storage_key": "private.pdf",
        "shared_at": now,
    }
    task = {
        "_id": ObjectId(),
        "application_id": application_id,
        "status": "completed",
        "completed_at": now - timedelta(days=1),
    }
    database = FakeDatabase([application], [document], customer_id, [task])

    assert _final_document_work(database, {"_id": str(ObjectId()), "role": "owner"}, shared=True) == []
