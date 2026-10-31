from datetime import datetime, timezone
from bson import ObjectId

def audit(db, actor_id, action, resource_type, resource_id=None, details=None):
    db.audit_logs.insert_one({
        "actor_id": ObjectId(actor_id) if actor_id else None,
        "action": action, "resource_type": resource_type,
        "resource_id": str(resource_id) if resource_id else None,
        "details": details or {}, "created_at": datetime.now(timezone.utc)
    })
