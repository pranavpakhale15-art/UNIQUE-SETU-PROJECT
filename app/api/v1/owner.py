from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from app.api.dependencies import owner_or_admin, admin_only, require_permission, db_dep
from app.core.security import hash_password
from app.services.audit_service import audit
from app.schemas.admin import StaffCreateRequest
from app.utils.identifiers import normalize_indian_mobile
import re

router=APIRouter()

@router.get("/users")
def list_users(role:str|None=None,q:str|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),user=Depends(require_permission("users:manage:staff")),db=Depends(db_dep)):
    query={}
    if role: query["role"]=role
    if q: query["$or"]=[{"full_name":{"$regex":re.escape(q),"$options":"i"}},{"normalized_mobile_number":{"$regex":re.escape(q)}}]
    total=db.users.count_documents(query); items=[]
    for d in db.users.find(query,{"password_hash":0}).sort("created_at",-1).skip((page-1)*page_size).limit(page_size):
        d["_id"]=str(d["_id"])
        if d.get("created_by"): d["created_by"]=str(d["created_by"])
        for k in ("created_at","updated_at","last_login_at"):
            if d.get(k): d[k]=d[k].isoformat()
        items.append(d)
    return {"items":items,"page":page,"page_size":page_size,"total":total,"pages":(total+page_size-1)//page_size}

@router.post("/staff",status_code=201)
def create_staff(payload:StaffCreateRequest,user=Depends(require_permission("users:manage:staff")),db=Depends(db_dep)):
    try:
        digits=normalize_indian_mobile(payload.mobile_number)
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    if len(payload.password)<10 or not any(c.isdigit() for c in payload.password) or not any(c.isalpha() for c in payload.password):
        raise HTTPException(status_code=422,detail="Provide valid Indian mobile and a password of at least 10 characters containing letters and numbers")
    now=datetime.now(timezone.utc)
    from pymongo.errors import DuplicateKeyError
    try:
        result=db.users.insert_one({"full_name":payload.full_name.strip(),"mobile_number":digits,"normalized_mobile_number":digits,"email":None,
            "password_hash":hash_password(payload.password),"role":"staff","permissions":[],"account_status":"active","preferred_language":"mr",
            "created_at":now,"updated_at":now,"last_login_at":None,"created_by":ObjectId(user["_id"])})
    except DuplicateKeyError: raise HTTPException(status_code=409,detail="Mobile number already exists")
    audit(db,user["_id"],"staff.created","user",result.inserted_id)
    return {"id":str(result.inserted_id),"message":"Staff account created"}

@router.get("/reports/summary")
def summary(user=Depends(require_permission("reports:read")),db=Depends(db_dep)):
    return {"users":db.users.count_documents({}),"active_customers":db.users.count_documents({"role":"customer","account_status":"active"}),
            "applications_total":db.applications.count_documents({}),
            "applications_by_status":{s:db.applications.count_documents({"status":s}) for s in ["Draft","Submitted by Customer","In Progress","Completed by Shop","Cancelled"]},
            "open_tasks":db.application_tasks.count_documents({"status":{"$in":["open","in_progress","blocked"]}})}

@router.get("/audit-logs")
def audit_logs(page:int=Query(1,ge=1),page_size:int=Query(50,ge=1,le=100),user=Depends(admin_only),db=Depends(db_dep)):
    total=db.audit_logs.count_documents({})
    items=[]
    for d in db.audit_logs.find({}).sort("created_at",-1).skip((page-1)*page_size).limit(page_size):
        d["_id"]=str(d["_id"])
        if d.get("actor_id"): d["actor_id"]=str(d["actor_id"])
        if d.get("created_at"): d["created_at"]=d["created_at"].isoformat()
        items.append(d)
    return {"items":items,"page":page,"page_size":page_size,"total":total}
