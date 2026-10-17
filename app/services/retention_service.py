from datetime import datetime, timedelta, timezone
import logging
import uuid

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.services.storage_service import StorageService

RETENTION_DAYS = 45
RETENTION_LOCK_ID = "completed-work-retention"
RETENTION_LOCK_MINUTES = 10
logger = logging.getLogger(__name__)


def _acquire_lock(db, now):
    owner = uuid.uuid4().hex
    try:
        lock = db.maintenance_locks.find_one_and_update(
            {
                "_id": RETENTION_LOCK_ID,
                "$or": [
                    {"lease_expires_at": {"$lte": now}},
                    {"lease_expires_at": {"$exists": False}},
                ],
            },
            {
                "$set": {
                    "owner": owner,
                    "lease_expires_at": now + timedelta(minutes=RETENTION_LOCK_MINUTES),
                }
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
    except DuplicateKeyError:
        return None
    return owner if lock and lock.get("owner") == owner else None


def _document_storage_references(document):
    provider = document.get("storage_provider")
    resource_type = document.get("storage_resource_type") or "raw"
    references = []
    if document.get("storage_key"):
        references.append((document["storage_key"], provider, resource_type))
    for entry in document.get("replacement_history", []):
        if entry.get("storage_key"):
            references.append((
                entry["storage_key"],
                entry.get("storage_provider") or provider,
                entry.get("storage_resource_type") or resource_type,
            ))
    return references


def _purge_application(db, storage, application):
    application_id = application["_id"]
    documents = list(db.application_documents.find({"application_id": application_id}))
    references = {
        reference
        for document in documents
        for reference in _document_storage_references(document)
    }
    for key, provider, resource_type in references:
        storage.delete(key, provider=provider, resource_type=resource_type)

    tasks = list(db.application_tasks.find({"application_id": application_id}, {"_id": 1}))
    task_ids = [task["_id"] for task in tasks]

    db.application_documents.delete_many({"application_id": application_id})
    db.application_status_history.delete_many({"application_id": application_id})
    db.application_comments.delete_many({"application_id": application_id})
    db.document_upload_intents.delete_many({"application_id": application_id})
    db.notifications.delete_many({"related_application_id": application_id})
    db.application_tasks.delete_many({"application_id": application_id})
    db.applications.delete_one({"_id": application_id})

    # Audit events are retained for operational accountability; application identifiers are
    # preserved there, but customer profile data and application contents are removed.
    return {
        "application_id": str(application_id),
        "task_count": len(task_ids),
        "files": len(references),
    }


def cleanup_expired_completed_work(db, storage=None, now=None):
    """Purge completed applications and task data after their 45-day retention window."""
    storage = storage or StorageService()
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    lock_owner = _acquire_lock(db, now)
    if not lock_owner:
        return {"skipped": True, "applications": 0, "tasks": 0, "files": 0, "errors": 0}

    result = {"skipped": False, "applications": 0, "tasks": 0, "files": 0, "errors": 0}
    try:
        for application in db.applications.find({
            "status": "Completed by Shop",
            "$or": [{"completed_at": {"$exists": False}}, {"completed_at": None}],
        }):
            history = db.application_status_history.find_one(
                {
                    "application_id": application["_id"],
                    "new_status": "Completed by Shop",
                },
                sort=[("timestamp", -1)],
            )
            if history and history.get("timestamp"):
                db.applications.update_one(
                    {"_id": application["_id"], "$or": [{"completed_at": {"$exists": False}}, {"completed_at": None}]},
                    {"$set": {"completed_at": history["timestamp"]}},
                )

        expired_applications = db.applications.find({
            "status": "Completed by Shop",
            "completed_at": {"$lt": cutoff},
        })
        for application in expired_applications:
            application_id = application["_id"]
            tasks = list(db.application_tasks.find({"application_id": application_id}))
            if any(
                task.get("status") in ("open", "in_progress", "blocked")
                or (task.get("status") == "completed" and completed_task_is_retained(task, now))
                or (task.get("status") == "completed" and not task.get("completed_at"))
                for task in tasks
            ):
                continue
            try:
                purged = _purge_application(db, storage, application)
            except Exception:
                result["errors"] += 1
                logger.exception("Completed-work retention purge failed application_id=%s", application_id)
                continue
            result["applications"] += 1
            result["tasks"] += purged["task_count"]
            result["files"] += purged["files"]

        expired_tasks = db.application_tasks.find({
            "status": "completed",
            "completed_at": {"$lt": cutoff},
        })
        for task in expired_tasks:
            try:
                deleted = db.application_tasks.delete_one({
                    "_id": task["_id"],
                    "status": "completed",
                    "completed_at": {"$lt": cutoff},
                })
            except Exception:
                result["errors"] += 1
                logger.exception("Completed-task retention deletion failed task_id=%s", task.get("_id"))
                continue
            result["tasks"] += deleted.deleted_count
    finally:
        db.maintenance_locks.update_one(
            {"_id": RETENTION_LOCK_ID, "owner": lock_owner},
            {"$set": {"lease_expires_at": now}},
        )
    return result


def completed_work_cutoff(now=None):
    now = now or datetime.now(timezone.utc)
    return now - timedelta(days=RETENTION_DAYS)


def _as_utc(value):
    if value and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def application_retention_timestamp(db, application):
    timestamps = [_as_utc(application.get("completed_at"))]
    latest_task = db.application_tasks.find_one(
        {"application_id": application["_id"], "status": "completed", "completed_at": {"$exists": True}},
        sort=[("completed_at", -1)],
    )
    if latest_task:
        timestamps.append(_as_utc(latest_task.get("completed_at")))
    timestamps = [timestamp for timestamp in timestamps if timestamp]
    return max(timestamps) if timestamps else None


def application_is_retained(db, application, now=None):
    if application.get("status") != "Completed by Shop":
        return True
    if db.application_tasks.find_one({
        "application_id": application["_id"],
        "status": {"$in": ["open", "in_progress", "blocked"]},
    }):
        return True
    if db.application_tasks.find_one({
        "application_id": application["_id"],
        "status": "completed",
        "$or": [{"completed_at": {"$exists": False}}, {"completed_at": None}],
    }):
        return True
    completed_at = application_retention_timestamp(db, application)
    return completed_at is None or completed_at >= completed_work_cutoff(now)


def retained_application_filter(db, cutoff=None):
    cutoff = cutoff or completed_work_cutoff()
    retained_task_applications = db.application_tasks.distinct("application_id", {
        "$or": [
            {"status": {"$in": ["open", "in_progress", "blocked"]}},
            {"status": "completed", "completed_at": {"$gte": cutoff}},
            {"status": "completed", "completed_at": {"$exists": False}},
            {"status": "completed", "completed_at": None},
        ],
    })
    return {"$or": [
        {"status": {"$ne": "Completed by Shop"}},
        {"completed_at": {"$gte": cutoff}},
        {"completed_at": {"$exists": False}},
        {"completed_at": None},
        {"_id": {"$in": retained_task_applications}},
    ]}


def completed_task_is_retained(task, now=None):
    completed_at = _as_utc(task.get("completed_at"))
    if not completed_at:
        return False
    return completed_at >= completed_work_cutoff(now)
