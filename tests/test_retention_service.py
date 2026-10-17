from datetime import datetime, timedelta, timezone

from bson import ObjectId

from app.services import retention_service


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
            actual = record.get(field)
            if isinstance(expected, dict):
                if "$exists" in expected and (field in record) != expected["$exists"]:
                    return False
                if "$lt" in expected and (actual is None or actual >= expected["$lt"]):
                    return False
                if "$lte" in expected and (actual is None or actual > expected["$lte"]):
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$ne" in expected and actual == expected["$ne"]:
                    return False
            elif actual != expected:
                return False
        return True

    def find(self, query, projection=None):
        return [record.copy() for record in self.records if self.matches(record, query)]

    def find_one(self, query, sort=None):
        return next((record.copy() for record in self.records if self.matches(record, query)), None)

    def update_one(self, query, update):
        for record in self.records:
            if self.matches(record, query):
                record.update(update.get("$set", {}))
                return

    def delete_many(self, query):
        self.records = [record for record in self.records if not self.matches(record, query)]

    def delete_one(self, query):
        for index, record in enumerate(self.records):
            if self.matches(record, query):
                del self.records[index]
                return type("DeleteResult", (), {"deleted_count": 1})()
        return type("DeleteResult", (), {"deleted_count": 0})()


class FakeDatabase:
    def __init__(self, application, tasks, documents):
        self.applications = FakeCollection([application])
        self.application_tasks = FakeCollection(tasks)
        self.application_documents = FakeCollection(documents)
        self.application_status_history = FakeCollection()
        self.application_comments = FakeCollection()
        self.document_upload_intents = FakeCollection()
        self.notifications = FakeCollection()
        self.maintenance_locks = FakeCollection()


class FakeStorage:
    def __init__(self, fail=False):
        self.deleted = []
        self.fail = fail

    def delete(self, key, provider=None, resource_type="raw"):
        if self.fail:
            raise OSError("storage unavailable")
        self.deleted.append((key, provider, resource_type))


def make_completed_records(completed_at):
    application_id = ObjectId()
    customer_id = ObjectId()
    application = {
        "_id": application_id,
        "customer_id": customer_id,
        "status": "Completed by Shop",
        "completed_at": completed_at,
    }
    task = {
        "_id": ObjectId(),
        "application_id": application_id,
        "status": "completed",
        "completed_at": completed_at,
    }
    document = {
        "_id": ObjectId(),
        "application_id": application_id,
        "customer_id": customer_id,
        "document_kind": "issued",
        "storage_key": "issued.pdf",
        "storage_provider": "local",
        "replacement_history": [{"storage_key": "previous.pdf"}],
    }
    return application, task, document


def test_completed_records_are_retained_at_day_45_then_files_and_data_are_deleted(monkeypatch):
    completed_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    application, task, document = make_completed_records(completed_at)
    database = FakeDatabase(application, [task], [document])
    storage = FakeStorage()
    monkeypatch.setattr(retention_service, "_acquire_lock", lambda db, now: "worker")

    on_boundary = retention_service.cleanup_expired_completed_work(
        database, storage, now=completed_at + timedelta(days=45)
    )
    assert on_boundary["applications"] == 0
    assert len(database.applications.records) == 1

    after_boundary = retention_service.cleanup_expired_completed_work(
        database, storage, now=completed_at + timedelta(days=45, microseconds=1)
    )

    assert after_boundary["applications"] == 1
    assert after_boundary["tasks"] == 1
    assert after_boundary["files"] == 2
    assert database.applications.records == []
    assert database.application_tasks.records == []
    assert database.application_documents.records == []
    assert {key for key, _, _ in storage.deleted} == {"issued.pdf", "previous.pdf"}


def test_storage_failure_keeps_database_references_for_retry(monkeypatch):
    completed_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    application, task, document = make_completed_records(completed_at)
    database = FakeDatabase(application, [task], [document])
    monkeypatch.setattr(retention_service, "_acquire_lock", lambda db, now: "worker")
    expired_at = completed_at + timedelta(days=46)

    failed = retention_service.cleanup_expired_completed_work(
        database, FakeStorage(fail=True), now=expired_at
    )
    assert failed["errors"] == 1
    assert len(database.applications.records) == 1

    retried_storage = FakeStorage()
    retried = retention_service.cleanup_expired_completed_work(
        database, retried_storage, now=expired_at
    )

    assert retried["applications"] == 1
    assert database.applications.records == []


def test_active_application_is_preserved_but_expired_completed_task_is_removed(monkeypatch):
    completed_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    application, task, document = make_completed_records(completed_at)
    application["status"] = "In Progress"
    database = FakeDatabase(application, [task], [document])
    monkeypatch.setattr(retention_service, "_acquire_lock", lambda db, now: "worker")

    result = retention_service.cleanup_expired_completed_work(
        database, FakeStorage(), now=completed_at + timedelta(days=46)
    )

    assert result["applications"] == 0
    assert result["tasks"] == 1
    assert len(database.applications.records) == 1
    assert database.application_tasks.records == []
    assert len(database.application_documents.records) == 1


def test_old_task_is_removed_while_recently_completed_application_is_retained(monkeypatch):
    completed_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    application, task, document = make_completed_records(completed_at)
    application["completed_at"] = completed_at + timedelta(days=10)
    database = FakeDatabase(application, [task], [document])
    monkeypatch.setattr(retention_service, "_acquire_lock", lambda db, now: "worker")

    result = retention_service.cleanup_expired_completed_work(
        database, FakeStorage(), now=completed_at + timedelta(days=46)
    )

    assert result["applications"] == 0
    assert result["tasks"] == 1
    assert len(database.applications.records) == 1
    assert database.application_tasks.records == []
    assert len(database.application_documents.records) == 1
