from datetime import datetime, timezone
import hashlib

from pymongo.errors import DuplicateKeyError

from app.core.config import settings


def consume_login_attempt(db, ip_address: str, mobile_number: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    window = int(now.timestamp()) // 60
    expires_at = datetime.fromtimestamp((window + 2) * 60, tz=timezone.utc)
    keys = (
        f"login:ip:{hashlib.sha256(ip_address.encode()).hexdigest()}:{window}",
        f"login:mobile:{hashlib.sha256(mobile_number.encode()).hexdigest()}:{window}",
    )
    allowed = True
    for key in keys:
        try:
            db.rate_limits.update_one(
                {"_id": key},
                {"$inc": {"count": 1}, "$setOnInsert": {"expires_at": expires_at}},
                upsert=True,
            )
        except DuplicateKeyError:
            db.rate_limits.update_one({"_id": key}, {"$inc": {"count": 1}})
        attempt = db.rate_limits.find_one({"_id": key})
        if attempt and attempt["count"] > settings.login_attempts_per_minute:
            allowed = False
    return allowed