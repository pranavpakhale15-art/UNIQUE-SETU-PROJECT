from pymongo import ASCENDING, DESCENDING

def create_indexes(db):
    db.users.create_index([("normalized_mobile_number", ASCENDING)], unique=True, name="uniq_mobile")
    db.users.create_index([("role", ASCENDING), ("account_status", ASCENDING)])
    db.services.create_index([("service_code", ASCENDING)], unique=True, name="uniq_service_code")
    db.service_versions.create_index([("service_id", ASCENDING), ("version", DESCENDING)])
    db.translations.create_index([("key", ASCENDING)], unique=True, name="uniq_translation_key")
    db.services.create_index([("is_published", ASCENDING), ("category", ASCENDING)])
    db.applications.create_index([("application_number", ASCENDING)], unique=True, name="uniq_application_number")
    db.applications.create_index([("customer_id", ASCENDING), ("created_at", DESCENDING)])
    db.applications.create_index([("assigned_staff_id", ASCENDING), ("status", ASCENDING)])
    db.application_documents.create_index([("application_id", ASCENDING), ("created_at", DESCENDING)])
    db.document_upload_intents.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    db.document_upload_intents.create_index([("application_id", ASCENDING), ("user_id", ASCENDING), ("state", ASCENDING)])
    db.application_status_history.create_index([("application_id", ASCENDING), ("timestamp", ASCENDING)])
    db.application_tasks.create_index([("assigned_staff_id", ASCENDING), ("status", ASCENDING), ("due_date", ASCENDING)])
    db.notifications.create_index([("recipient_id", ASCENDING), ("is_read", ASCENDING), ("created_at", DESCENDING)])
    for name, index in db.notifications.index_information().items():
        if index.get("key") == [("dedupe_key", ASCENDING)] and index.get("unique") and index.get("sparse"):
            db.notifications.drop_index(name)
    db.notifications.create_index([("dedupe_key", ASCENDING)], unique=True, name="uniq_notification_dedupe_key",
                                  partialFilterExpression={"dedupe_key": {"$type": "string"}})
    db.audit_logs.create_index([("created_at", DESCENDING)])
    db.sessions.create_index([("refresh_token_hash", ASCENDING)], unique=True, name="uniq_refresh_token_hash")
    db.sessions.create_index([("user_id", ASCENDING), ("revoked", ASCENDING)])
    db.sessions.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
    db.rate_limits.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0)
