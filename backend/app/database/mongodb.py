from pymongo import MongoClient
from app.core.config import settings

_client = None
_db = None

def connect():
    global _client, _db
    if not settings.mongodb_uri:
        if settings.app_env == "production":
            raise RuntimeError("MONGODB_URI is required")
        # Local development still uses MongoDB; fail clearly instead of silently using a different DB.
        raise RuntimeError("Set MONGODB_URI in .env to connect to MongoDB Atlas or local MongoDB")
    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
                         maxPoolSize=50, minPoolSize=1, appname="unique-solutions-api")
    try:
        client.admin.command("ping")
    except Exception:
        client.close()
        raise
    _client = client
    _db = client[settings.mongodb_database]
    return _db

def get_db():
    if _db is None:
        raise RuntimeError("Database is not connected")
    return _db

def close():
    global _client, _db
    if _client:
        _client.close()
    _client, _db = None, None

def ping() -> bool:
    try:
        get_db().command("ping")
        return True
    except Exception:
        return False
