from datetime import datetime, timezone
import secrets
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from app.database.mongodb import get_db
from app.core.security import decode_token
from app.core.permissions import has_permission

bearer = HTTPBearer(auto_error=False)

def verify_csrf(request: Request):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    csrf_cookie = request.cookies.get("csrf_token", "")
    csrf_header = request.headers.get("X-CSRF-Token", "")
    if not csrf_cookie or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")

def db_dep():
    return get_db()

def current_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(db_dep)):
    token = credentials.credentials if credentials else request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("Wrong token type")
        user_id = payload.get("sub")
        session_id = payload.get("sid")
        if not session_id:
            raise ValueError("Session required")
        session = db.sessions.find_one({"_id": ObjectId(session_id), "user_id": ObjectId(user_id),
                                        "revoked": False, "expires_at": {"$gt": datetime.now(timezone.utc)}})
        if not session:
            raise ValueError("Session revoked or expired")
        user = db.users.find_one({"_id": ObjectId(user_id), "account_status": "active"})
        if user:
            user["_session_id"] = session_id
    except Exception:
        user = None
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication")
    if not credentials:
        verify_csrf(request)
    user["_id"] = str(user["_id"])
    return user

def optional_user(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db=Depends(db_dep)):
    try:
        return current_user(request, credentials, db)
    except HTTPException:
        return None

def owner_or_admin(user=Depends(current_user)):
    if not has_permission(user, "users:manage:staff"):
        raise HTTPException(status_code=403, detail="Owner or admin access required")
    return user

def admin_only(user=Depends(current_user)):
    if user.get("role") != "admin" or not has_permission(user, "admin:manage"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def require_permission(permission: str):
    def check_permission(user=Depends(current_user)):
        if not has_permission(user, permission):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return check_permission
