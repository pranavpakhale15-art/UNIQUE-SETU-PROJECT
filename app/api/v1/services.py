from datetime import datetime, timezone
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from app.api.dependencies import current_user, optional_user, db_dep, admin_only
from app.schemas.service import ServiceCreate, ServicePatch
from app.services.audit_service import audit

router = APIRouter()

def serialize(doc):
    doc["_id"] = str(doc["_id"])
    for key, value in list(doc.items()):
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
    return doc

@router.get("")
def list_services(q: str | None = None, category: str | None = None, language: str = "mr",
                  include_unpublished: bool = False, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  user=Depends(optional_user), db=Depends(db_dep)):
    query = {}
    if not (include_unpublished and user and user.get("role") == "admin"):
        query["is_published"] = True
    elif not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if category: query["category"] = category
    if q:
        escaped_q = re.escape(q)
        query["$or"] = [{"name.mr": {"$regex": escaped_q, "$options": "i"}}, {"name.en": {"$regex": escaped_q, "$options": "i"}}, {"service_code": {"$regex": escaped_q, "$options": "i"}}]
    total = db.services.count_documents(query)
    items = []
    for d in db.services.find(query).sort("name.mr", 1).skip((page-1)*page_size).limit(page_size):
        d = serialize(d); d["display_name"] = d.get("name", {}).get(language) or d.get("name", {}).get("mr")
        items.append(d)
    return {"items": items, "page": page, "page_size": page_size, "total": total, "pages": (total+page_size-1)//page_size}

@router.get("/{service_id}")
def get_service(service_id: str, user=Depends(optional_user), db=Depends(db_dep)):
    try:
        oid = ObjectId(service_id)
        doc = db.services.find_one({"_id": oid})
    except Exception:
        service_code = service_id.replace("-", "_").upper()
        doc = db.services.find_one({"service_code": service_code})
    if not doc or (not doc.get("is_published") and (not user or user.get("role") != "admin")):
        raise HTTPException(status_code=404, detail="Service not found")
    return serialize(doc)

@router.post("", status_code=201)
def create_service(payload: ServiceCreate, user=Depends(admin_only), db=Depends(db_dep)):
    now = datetime.now(timezone.utc)
    doc = payload.model_dump() | {"is_published": False,"version": 1, "workflow_configuration": {}, "checklist_review_required": True,
                                  "created_at": now, "updated_at": now, "updated_by": ObjectId(user["_id"])}
    try: result = db.services.insert_one(doc)
    except DuplicateKeyError as exc: raise HTTPException(status_code=409, detail="Service code already exists") from exc
    audit(db, user["_id"], "service.created", "service", result.inserted_id, {"service_code": payload.service_code})
    return {"id": str(result.inserted_id)}

@router.patch("/{service_id}")
def update_service(service_id: str, payload: ServicePatch, user=Depends(admin_only), db=Depends(db_dep)):
    try: oid = ObjectId(service_id)
    except Exception: raise HTTPException(status_code=404, detail="Service not found")
    existing = db.services.find_one({"_id": oid})
    if not existing: raise HTTPException(status_code=404, detail="Service not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one service field must be provided")
    for field in ("service_code", "name", "category"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
    if "document_requirements" in changes or "form_requirements" in changes:
        changes["checklist_review_required"] = True
    previous = {key: value for key, value in existing.items() if key != "_id"}
    previous_version = existing.get("version", 1)
    changes["version"] = previous_version + 1
    changes["updated_at"] = datetime.now(timezone.utc); changes["updated_by"] = ObjectId(user["_id"])
    version_filter = {"version": previous_version} if "version" in existing else {"version": {"$exists": False}}
    try:
        result = db.services.update_one({"_id": oid, **version_filter}, {"$set": changes})
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Service code already exists") from exc
    if not result.matched_count:
        raise HTTPException(status_code=409, detail="Service changed concurrently; reload and retry")
    db.service_versions.insert_one({"service_id": oid, "version": previous_version,
                                    "snapshot": previous, "archived_at": datetime.now(timezone.utc)})
    audit(db, user["_id"], "service.updated", "service", oid, {"version": changes["version"]})
    return {"message": "Service updated", "version": changes["version"]}

@router.get("/{service_id}/versions")
def list_service_versions(service_id: str, user=Depends(admin_only), db=Depends(db_dep)):
    try: oid=ObjectId(service_id)
    except Exception: raise HTTPException(status_code=404,detail="Service not found")
    if not db.services.find_one({"_id":oid}): raise HTTPException(status_code=404,detail="Service not found")
    versions=[]
    for item in db.service_versions.find({"service_id":oid}).sort("version",-1):
        item["_id"]=str(item["_id"])
        item["service_id"]=str(item["service_id"])
        if item.get("archived_at"): item["archived_at"]=item["archived_at"].isoformat()
        snapshot=item.get("snapshot",{})
        for field in ("created_at","updated_at"):
            if snapshot.get(field): snapshot[field]=snapshot[field].isoformat()
        if snapshot.get("updated_by"): snapshot["updated_by"]=str(snapshot["updated_by"])
        versions.append(item)
    return versions

@router.post("/{service_id}/publish")
def publish_service(service_id: str, user=Depends(admin_only), db=Depends(db_dep)):
    try: oid = ObjectId(service_id)
    except Exception: raise HTTPException(status_code=404, detail="Service not found")
    doc = db.services.find_one({"_id": oid})
    if not doc: raise HTTPException(status_code=404, detail="Service not found")
    if not doc.get("document_requirements") or doc.get("checklist_review_required", True):
        raise HTTPException(status_code=409, detail="Add document requirements and mark the checklist reviewed before publishing")
    db.services.update_one({"_id": oid}, {"$set": {"is_published": True, "updated_at": datetime.now(timezone.utc), "updated_by": ObjectId(user["_id"])}})
    audit(db, user["_id"], "service.published", "service", oid)
    return {"message": "Service published"}

@router.post("/{service_id}/archive")
def archive_service(service_id: str, user=Depends(admin_only), db=Depends(db_dep)):
    try: oid = ObjectId(service_id)
    except Exception: raise HTTPException(status_code=404, detail="Service not found")
    result = db.services.update_one({"_id": oid}, {"$set": {"is_published": False, "updated_at": datetime.now(timezone.utc), "updated_by": ObjectId(user["_id"])}})
    if not result.matched_count: raise HTTPException(status_code=404, detail="Service not found")
    audit(db, user["_id"], "service.archived", "service", oid)
    return {"message": "Service archived"}

@router.delete("/{service_id}")
def delete_service(service_id: str, user=Depends(admin_only), db=Depends(db_dep)):
    try:
        oid = ObjectId(service_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Service not found") from exc
    service = db.services.find_one({"_id": oid})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if db.applications.count_documents({"service_id": oid}):
        raise HTTPException(status_code=409, detail="This service has applications; archive it instead to preserve their records")
    db.service_versions.delete_many({"service_id": oid})
    db.services.delete_one({"_id": oid})
    audit(db, user["_id"], "service.deleted", "service", oid, {"service_code": service.get("service_code")})
    return {"message": "Service deleted"}
