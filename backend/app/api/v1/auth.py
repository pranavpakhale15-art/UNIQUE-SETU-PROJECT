from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pymongo.errors import DuplicateKeyError
from bson import ObjectId
import secrets
from pathlib import Path
from app.api.dependencies import current_user, db_dep, verify_csrf
from app.core.config import settings
from app.core.permissions import has_permission
from app.core.security import hash_password, verify_password, create_token, token_digest
from app.schemas.auth import (RegisterRequest, LoginRequest, RefreshRequest, ForgotPasswordRequest,
                              ResetPasswordRequest, ProfilePhotoResponse)
from app.services.audit_service import audit
from app.services.rate_limit_service import consume_login_attempt
from app.services.storage_service import StorageService
from app.utils.identifiers import normalize_indian_mobile

router = APIRouter()
PUBLIC_USER_FIELDS = {"full_name", "mobile_number", "email", "role", "preferred_language", "account_status", "created_at"}
photo_storage = StorageService()

def public_user(user):
    result = {k: (str(v) if k == "_id" else v) for k, v in user.items() if k in PUBLIC_USER_FIELDS or k == "_id"}
    photo = user.get("profile_photo")
    if photo:
        result["profile_photo"] = {
            field: photo[field] for field in ("original_filename", "detected_content_type", "file_size", "updated_at")
            if field in photo
        }
    return result

def issue_tokens(db, user_id: str, user_agent: str | None):
    now = datetime.now(timezone.utc)
    session_id = ObjectId()
    refresh = secrets.token_urlsafe(48)
    db.sessions.insert_one({"_id": session_id, "user_id": ObjectId(user_id), "refresh_token_hash": token_digest(refresh),
                            "expires_at": now + timedelta(days=settings.refresh_token_expire_days),
                            "user_agent": user_agent, "revoked": False, "created_at": now})
    access = create_token(user_id, "access", timedelta(minutes=settings.access_token_expire_minutes), session_id=str(session_id))
    return access, refresh

def set_auth_cookies(response: Response, access: str, refresh: str):
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie("access_token", access, httponly=True, secure=settings.cookie_secure, samesite=settings.cookie_samesite, max_age=settings.access_token_expire_minutes*60, path="/")
    response.set_cookie("refresh_token", refresh, httponly=True, secure=settings.cookie_secure, samesite=settings.cookie_samesite, max_age=settings.refresh_token_expire_days*86400, path=f"{settings.api_v1_prefix}/auth")
    response.set_cookie("csrf_token", csrf_token, httponly=False, secure=settings.cookie_secure, samesite=settings.cookie_samesite, max_age=settings.refresh_token_expire_days*86400, path="/")

@router.post("/register", status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, db=Depends(db_dep)):
    now = datetime.now(timezone.utc)
    user = {"full_name": payload.full_name.strip(), "mobile_number": payload.mobile_number,
            "normalized_mobile_number": payload.mobile_number, "email": payload.email,
            "password_hash": hash_password(payload.password), "role": "customer", "permissions": [],
            "account_status": "active", "preferred_language": payload.preferred_language,
            "created_at": now, "updated_at": now, "last_login_at": None, "created_by": None}
    try:
        result = db.users.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="An account with this mobile number already exists")
    access, refresh = issue_tokens(db, str(result.inserted_id), request.headers.get("user-agent"))
    set_auth_cookies(response, access, refresh)
    return {"user": public_user({"_id": str(result.inserted_id), **user}), "token_type": "cookie"}

@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response, db=Depends(db_dep)):
    try:
        digits = normalize_indian_mobile(payload.mobile_number)
    except ValueError:
        digits = payload.mobile_number
    remote_ip = request.client.host if request.client else "unknown"
    if not consume_login_attempt(db, remote_ip, digits):
        raise HTTPException(status_code=429, detail="Too many login attempts; try again in a minute")
    user = db.users.find_one({"normalized_mobile_number": digits})
    if (
        not user
        or not verify_password(payload.password, user.get("password_hash", ""))
        or user.get("account_status") != "active"
        or (payload.account_type is not None and user.get("role") != payload.account_type)
    ):
        raise HTTPException(status_code=401, detail="Invalid account type, mobile number, or password")
    now = datetime.now(timezone.utc)
    db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login_at": now, "updated_at": now}})
    access, refresh = issue_tokens(db, str(user["_id"]), request.headers.get("user-agent"))
    set_auth_cookies(response, access, refresh)
    return {"user": public_user(user), "token_type": "cookie"}

@router.post("/logout")
def logout(response: Response, request: Request, user=Depends(current_user), db=Depends(db_dep)):
    if user.get("_session_id"):
        db.sessions.update_one({"_id": ObjectId(user["_session_id"])}, {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc)}})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path=f"{settings.api_v1_prefix}/auth")
    response.delete_cookie("csrf_token", path="/")
    return {"message": "Logged out"}

@router.post("/refresh")
def refresh(payload: RefreshRequest, request: Request, response: Response, db=Depends(db_dep)):
    token = payload.refresh_token or request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token required")
    if not payload.refresh_token:
        verify_csrf(request)
    now = datetime.now(timezone.utc)
    session = db.sessions.find_one({"refresh_token_hash": token_digest(token), "revoked": False, "expires_at": {"$gt": now}})
    user = db.users.find_one({"_id": session["user_id"], "account_status": "active"}) if session else None
    if not session or not user:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access, new_refresh = issue_tokens(db, str(user["_id"]), request.headers.get("user-agent"))
    result = db.sessions.update_one({"_id": session["_id"], "revoked": False}, {"$set": {"revoked": True, "revoked_at": now, "replaced_by": token_digest(new_refresh)}})
    if not result.modified_count:
        db.sessions.update_one({"refresh_token_hash": token_digest(new_refresh)}, {"$set": {"revoked": True, "revoked_at": now}})
        raise HTTPException(status_code=401, detail="Refresh token has already been used")
    set_auth_cookies(response, access, new_refresh)
    return {"token_type": "cookie"}

@router.get("/me")
def me(user=Depends(current_user)):
    return public_user(user)


@router.put("/me/photo", response_model=ProfilePhotoResponse)
async def update_profile_photo(
    file: UploadFile = File(...),
    user=Depends(current_user),
    db=Depends(db_dep),
):
    if user.get("role") != "customer" or not has_permission(user, "profile:update:self"):
        raise HTTPException(status_code=403, detail="Only customers may update their own profile photo")
    filename = Path((file.filename or "").replace("\\", "/")).name
    extension = Path(filename).suffix.lower()
    expected_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(extension)
    if not filename or len(filename) > 255 or not expected_type or file.content_type != expected_type:
        raise HTTPException(status_code=422, detail="Only JPEG and PNG profile photos are accepted")
    content = await file.read(settings.max_upload_size_mb * 1024 * 1024 + 1)
    if not content:
        raise HTTPException(status_code=422, detail="Empty file")
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds configured maximum size")
    try:
        detected_type = photo_storage.detect_content_type(content)
        if detected_type != expected_type or detected_type not in ("image/jpeg", "image/png"):
            raise ValueError("File content does not match its extension")
        provider = settings.storage_provider.lower()
        key, size = photo_storage.save_bytes(
            content, filename, detected_type, provider=provider,
            resource_type="image", folder="customer-photos",
        )
    except OverflowError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Private storage is unavailable") from exc

    now = datetime.now(timezone.utc)
    previous = user.get("profile_photo")
    photo = {
        "storage_key": key,
        "storage_provider": provider,
        "storage_resource_type": "image",
        "original_filename": filename,
        "detected_content_type": detected_type,
        "file_size": size,
        "updated_at": now,
    }
    try:
        result = db.users.update_one({"_id": ObjectId(user["_id"])}, {"$set": {"profile_photo": photo, "updated_at": now}})
        if not result.matched_count:
            photo_storage.delete(key, provider=provider, resource_type="image")
            raise HTTPException(status_code=404, detail="User not found")
        audit(db, user["_id"], "profile.photo_updated", "user", ObjectId(user["_id"]))
        if previous and previous.get("storage_key"):
            photo_storage.delete(
                previous["storage_key"],
                provider=photo_storage.provider_for_record(previous),
                resource_type=previous.get("storage_resource_type", "image"),
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Profile photo update or cleanup failed") from exc
    return ProfilePhotoResponse(
        original_filename=filename,
        detected_content_type=detected_type,
        file_size=size,
        updated_at=now,
    )

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db=Depends(db_dep)):
    # No SMS provider configured: deliberately do not reveal account existence or return a usable reset token.
    return {"message": "If the account exists, password recovery instructions will be made available when a verified recovery channel is configured."}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    raise HTTPException(status_code=501, detail="Password reset requires a verified recovery channel; configure a provider before enabling this endpoint.")
