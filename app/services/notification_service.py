from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError
from bson import ObjectId

def notify(db, recipient_id, event_type, title, message, application_id=None, dedupe_key=None):
    doc = {"recipient_id": ObjectId(recipient_id), "event_type": event_type, "title": title, "message": message,
           "related_application_id": ObjectId(application_id) if application_id else None,
           "is_read": False, "created_at": datetime.now(timezone.utc)}
    if dedupe_key:
        doc["dedupe_key"] = dedupe_key
    try:
        db.notifications.insert_one(doc)
    except DuplicateKeyError:
        pass
