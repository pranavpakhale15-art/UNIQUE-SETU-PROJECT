from datetime import datetime, timezone
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from app.api.dependencies import admin_only, db_dep
from app.services.audit_service import audit
from app.schemas.admin import (AdminRoleChange, AdminUserStatusChange, AdminPermissionsChange,
                               TranslationUpdate, SystemSettingsUpdate)

router=APIRouter()

@router.patch("/users/{user_id}/status")
def set_user_status(user_id:str, payload:AdminUserStatusChange, user=Depends(admin_only), db=Depends(db_dep)):
    account_status=payload.account_status
    if account_status not in ("active","suspended","disabled"): raise HTTPException(status_code=422,detail="Invalid account status")
    try: oid=ObjectId(user_id)
    except Exception: raise HTTPException(status_code=404,detail="User not found")
    if str(oid)==user["_id"]: raise HTTPException(status_code=409,detail="You cannot suspend your own account")
    result=db.users.update_one({"_id":oid},{"$set":{"account_status":account_status,"updated_at":datetime.now(timezone.utc)}})
    if not result.matched_count: raise HTTPException(status_code=404,detail="User not found")
    if account_status!="active": db.sessions.update_many({"user_id":oid,"revoked":False},{"$set":{"revoked":True,"revoked_at":datetime.now(timezone.utc)}})
    audit(db,user["_id"],"user.status_changed","user",oid,{"account_status":account_status})
    return {"message":"User status updated"}

@router.patch("/users/{user_id}/role")
def set_role(user_id:str, payload:AdminRoleChange, user=Depends(admin_only), db=Depends(db_dep)):
    role=payload.role
    if role not in ("customer","staff","owner","admin"): raise HTTPException(status_code=422,detail="Invalid role")
    try: oid=ObjectId(user_id)
    except Exception: raise HTTPException(status_code=404,detail="User not found")
    if str(oid)==user["_id"]: raise HTTPException(status_code=409,detail="You cannot change your own role")
    result=db.users.update_one({"_id":oid},{"$set":{"role":role,"permissions":[],"permissions_customized":False,"updated_at":datetime.now(timezone.utc)}})
    if not result.matched_count: raise HTTPException(status_code=404,detail="User not found")
    db.sessions.update_many({"user_id":oid,"revoked":False},{"$set":{"revoked":True,"revoked_at":datetime.now(timezone.utc)}})
    audit(db,user["_id"],"user.role_changed","user",oid,{"role":role})
    return {"message":"Role updated; user sessions revoked"}

@router.patch("/users/{user_id}/permissions")
def set_permissions(user_id:str,payload:AdminPermissionsChange,user=Depends(admin_only),db=Depends(db_dep)):
    try: oid=ObjectId(user_id)
    except Exception: raise HTTPException(status_code=404,detail="User not found")
    if str(oid)==user["_id"]: raise HTTPException(status_code=409,detail="You cannot change your own permissions")
    result=db.users.update_one({"_id":oid},{"$set":{"permissions":payload.permissions,"permissions_customized":True,"updated_at":datetime.now(timezone.utc)}})
    if not result.matched_count: raise HTTPException(status_code=404,detail="User not found")
    db.sessions.update_many({"user_id":oid,"revoked":False},{"$set":{"revoked":True,"revoked_at":datetime.now(timezone.utc)}})
    audit(db,user["_id"],"user.permissions_changed","user",oid,{"permissions":payload.permissions})
    return {"message":"Permissions updated; user sessions revoked"}

@router.post("/users/{user_id}/revoke-sessions")
def revoke_sessions(user_id:str,user=Depends(admin_only),db=Depends(db_dep)):
    try: oid=ObjectId(user_id)
    except Exception: raise HTTPException(status_code=404,detail="User not found")
    if not db.users.find_one({"_id":oid}): raise HTTPException(status_code=404,detail="User not found")
    result=db.sessions.update_many({"user_id":oid,"revoked":False},{"$set":{"revoked":True,"revoked_at":datetime.now(timezone.utc)}})
    audit(db,user["_id"],"user.sessions_revoked","user",oid,{"session_count":result.modified_count})
    return {"revoked_sessions":result.modified_count}

@router.get("/translations")
def list_translations(q:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=200),user=Depends(admin_only),db=Depends(db_dep)):
    query={"key":{"$regex":re.escape(q),"$options":"i"}} if q else {}
    total=db.translations.count_documents(query)
    items=[]
    for item in db.translations.find(query).sort("key",1).skip((page-1)*page_size).limit(page_size):
        item["_id"]=str(item["_id"])
        if item.get("updated_by"): item["updated_by"]=str(item["updated_by"])
        if item.get("updated_at"): item["updated_at"]=item["updated_at"].isoformat()
        items.append(item)
    return {"items":items,"page":page,"page_size":page_size,"total":total}

@router.put("/translations/{translation_key}")
def update_translation(translation_key:str,payload:TranslationUpdate,user=Depends(admin_only),db=Depends(db_dep)):
    now=datetime.now(timezone.utc)
    db.translations.update_one({"key":translation_key},{"$set":{"translations":payload.translations,
        "updated_at":now,"updated_by":ObjectId(user["_id"])},"$setOnInsert":{"created_at":now}},upsert=True)
    audit(db,user["_id"],"translation.updated","translation",translation_key,{"locales":list(payload.translations)})
    return {"key":translation_key,"translations":payload.translations}

@router.get("/system-settings")
def get_system_settings(user=Depends(admin_only),db=Depends(db_dep)):
    record=db.system_settings.find_one({"_id":"global"}) or {"_id":"global"}
    record.pop("_id",None)
    if record.get("updated_by"): record["updated_by"]=str(record["updated_by"])
    if record.get("updated_at"): record["updated_at"]=record["updated_at"].isoformat()
    return record

@router.patch("/system-settings")
def update_system_settings(payload:SystemSettingsUpdate,user=Depends(admin_only),db=Depends(db_dep)):
    changes=payload.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(status_code=422,detail="At least one setting must be provided")
    now=datetime.now(timezone.utc)
    changes.update({"updated_at":now,"updated_by":ObjectId(user["_id"])})
    db.system_settings.update_one({"_id":"global"},{"$set":changes,"$setOnInsert":{"created_at":now}},upsert=True)
    audit(db,user["_id"],"system_settings.updated","system_settings","global",{"keys":list(payload.model_fields_set)})
    return {"message":"System settings updated"}

@router.get("/health/database")
def database_health(user=Depends(admin_only)):
    from app.database.mongodb import ping
    if not ping(): raise HTTPException(status_code=503,detail="MongoDB is unavailable")
    return {"status":"healthy","database":"connected"}

@router.get("/health/storage")
def storage_health(user=Depends(admin_only)):
    from app.core.config import settings
    if settings.storage_provider.lower()=="local":
        return {"provider":"local","status":"development_only","production_ready":False}
    from app.services.storage_service import StorageService
    try:
        StorageService().client.head_bucket(Bucket=settings.storage_bucket)
    except Exception:
        raise HTTPException(status_code=503,detail="Configured object storage is unavailable")
    return {"provider":"s3","status":"healthy","production_ready":True}
