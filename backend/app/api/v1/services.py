from datetime import datetime, timezone
from pathlib import Path
import re
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
from fastapi.responses import RedirectResponse, Response
from app.api.dependencies import current_user, optional_user, db_dep, admin_only
from app.schemas.service import (ServiceCategoryCreate, ServiceCategoryPatch, ServiceCreate, ServicePatch,
                                 ServiceThumbnailMetadata)
from app.services.audit_service import audit
from app.services.storage_service import StorageService

router = APIRouter()
storage = StorageService()

def thumbnail_response_metadata(thumbnail):
    if not thumbnail:
        return None
    updated_at = thumbnail.get("updated_at")
    metadata = {
        "original_filename": thumbnail.get("original_filename"),
        "detected_content_type": thumbnail.get("detected_content_type"),
        "file_size": thumbnail.get("file_size"),
        "updated_at": updated_at.isoformat() if isinstance(updated_at, datetime) else updated_at,
        "alt_text": thumbnail.get("alt_text", {}),
    }
    return ServiceThumbnailMetadata.model_validate(metadata).model_dump(mode="json")

def serialize(doc):
    doc["_id"] = str(doc["_id"])
    doc.pop("thumbnail_history", None)
    if doc.get("thumbnail"):
        doc["thumbnail"] = thumbnail_response_metadata(doc["thumbnail"])
        doc["thumbnail_url"] = f"/api/v1/services/{doc['_id']}/thumbnail"
    for key, value in list(doc.items()):
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
    return doc

def _section_object_id(section_id):
    if section_id is None:
        return None
    try:
        return ObjectId(section_id)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid service section") from exc

def _validate_section(db, section_id):
    section_oid = _section_object_id(section_id)
    if section_oid is not None and not db.service_categories.find_one({"_id": section_oid}):
        raise HTTPException(status_code=422, detail="Service section does not exist")
    return section_oid


def _visible_section_ids(db):
    return [record["_id"] for record in db.service_categories.find({"is_visible": True})]

def _thumbnail_references(service, versions):
    references = []
    candidates = [service.get("thumbnail")]
    candidates.extend(service.get("thumbnail_history", []))
    candidates.extend(version.get("snapshot", {}).get("thumbnail") for version in versions)
    candidates.extend(version.get("snapshot", {}).get("thumbnail_history", []) for version in versions)
    for candidate in candidates:
        if isinstance(candidate, list):
            references.extend(item for item in candidate if isinstance(item, dict))
        elif isinstance(candidate, dict):
            references.append(candidate)
    return references

@router.get("/categories")
def list_service_categories(include_hidden: bool = False, user=Depends(optional_user), db=Depends(db_dep)):
    is_admin = bool(user and user.get("role") == "admin")
    if include_hidden and not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    query = {} if include_hidden and is_admin else {"is_visible": True}
    records = db.service_categories.find(query).sort("display_order", 1)
    return [serialize(record) for record in records]

@router.post("/categories", status_code=201)
def create_service_category(payload: ServiceCategoryCreate, user=Depends(admin_only), db=Depends(db_dep)):
    now = datetime.now(timezone.utc)
    record = payload.model_dump() | {"created_at": now, "updated_at": now, "updated_by": ObjectId(user["_id"])}
    try:
        result = db.service_categories.insert_one(record)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Service category slug already exists") from exc
    audit(db, user["_id"], "service_category.created", "service_category", result.inserted_id)
    return {"id": str(result.inserted_id)}

@router.patch("/categories/{category_id}")
def update_service_category(category_id: str, payload: ServiceCategoryPatch,
                            user=Depends(admin_only), db=Depends(db_dep)):
    try:
        oid = ObjectId(category_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Service category not found") from exc
    existing = db.service_categories.find_one({"_id": oid})
    if not existing:
        raise HTTPException(status_code=404, detail="Service category not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one category field must be provided")
    for field in ("slug", "name", "is_visible", "display_order"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
    changes.update({"updated_at": datetime.now(timezone.utc), "updated_by": ObjectId(user["_id"])})
    try:
        db.service_categories.update_one({"_id": oid}, {"$set": changes})
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Service category slug already exists") from exc
    audit(db, user["_id"], "service_category.updated", "service_category", oid, {"fields": list(payload.model_fields_set)})
    return {"message": "Service category updated"}

@router.delete("/categories/{category_id}")
def delete_service_category(category_id: str, user=Depends(admin_only), db=Depends(db_dep)):
    try:
        oid = ObjectId(category_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Service category not found") from exc
    category = db.service_categories.find_one({"_id": oid})
    if not category:
        raise HTTPException(status_code=404, detail="Service category not found")
    in_use = db.services.count_documents({"section_id": oid})
    historical_use = db.service_versions.count_documents({"snapshot.section_id": oid})
    if in_use or historical_use:
        raise HTTPException(status_code=409, detail="This category is referenced by services; hide it instead")
    db.service_categories.delete_one({"_id": oid})
    audit(db, user["_id"], "service_category.deleted", "service_category", oid, {"slug": category.get("slug")})
    return {"message": "Service category deleted"}

@router.get("")
def list_services(q: str | None = None, category: str | None = None, language: str = "mr",
                  section_id: str | None = None,
                  include_unpublished: bool = False, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                  user=Depends(optional_user), db=Depends(db_dep)):
    query = {}
    is_admin = bool(user and user.get("role") == "admin")
    if not (include_unpublished and is_admin):
        query["is_published"] = True
    if include_unpublished and not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    if not is_admin:
        visible_ids = _visible_section_ids(db)
        query.setdefault("$and", []).append({"$or": [
            {"section_id": {"$in": visible_ids}},
            {"section_id": {"$exists": False}},
            {"section_id": None},
        ]})
    if category: query["category"] = category
    if section_id:
        query["section_id"] = _section_object_id(section_id)
    if q:
        escaped_q = re.escape(q)
        query["$or"] = [{"name.mr": {"$regex": escaped_q, "$options": "i"}}, {"name.en": {"$regex": escaped_q, "$options": "i"}}, {"service_code": {"$regex": escaped_q, "$options": "i"}}]
    total = db.services.count_documents(query)
    items = []
    for d in db.services.find(query).sort([("display_order", 1), ("name.mr", 1)]).skip((page-1)*page_size).limit(page_size):
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
    is_admin = bool(user and user.get("role") == "admin")
    if doc and doc.get("section_id") and not is_admin:
        visible_section = db.service_categories.find_one({"_id": doc["section_id"], "is_visible": True})
        if not visible_section:
            raise HTTPException(status_code=404, detail="Service not found")
    if not doc or (not doc.get("is_published") and not is_admin):
        raise HTTPException(status_code=404, detail="Service not found")
    return serialize(doc)

@router.post("", status_code=201)
def create_service(payload: ServiceCreate, user=Depends(admin_only), db=Depends(db_dep)):
    now = datetime.now(timezone.utc)
    values = payload.model_dump()
    values["section_id"] = _validate_section(db, values.get("section_id"))
    doc = values | {"is_published": False,"version": 1, "workflow_configuration": {}, "checklist_review_required": True,
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
    if "section_id" in changes:
        changes["section_id"] = _validate_section(db, changes["section_id"])
    if "thumbnail_alt_text" in changes and existing.get("thumbnail"):
        changes["thumbnail.alt_text"] = changes["thumbnail_alt_text"] or {}
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
        if snapshot.get("section_id"):
            snapshot["section_id"] = str(snapshot["section_id"])
        if snapshot.get("thumbnail"):
            snapshot["thumbnail"] = thumbnail_response_metadata(snapshot["thumbnail"])
            snapshot["thumbnail_url"] = None
        snapshot.pop("thumbnail_history", None)
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
    if doc.get("section_id") and not db.service_categories.find_one({"_id": doc["section_id"], "is_visible": True}):
        raise HTTPException(status_code=409, detail="Make the assigned service section visible before publishing")
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
    versions = list(db.service_versions.find({"service_id": oid}))
    thumbnail_refs = _thumbnail_references(service, versions)
    db.service_versions.delete_many({"service_id": oid})
    db.services.delete_one({"_id": oid})
    for thumbnail in thumbnail_refs:
        try:
            storage.delete(thumbnail["storage_key"], provider=thumbnail.get("storage_provider"), resource_type="image")
        except Exception:
            # Database deletion must not be rolled back by a provider cleanup outage.
            pass
    audit(db, user["_id"], "service.deleted", "service", oid, {"service_code": service.get("service_code")})
    return {"message": "Service deleted"}

@router.put("/{service_id}/thumbnail", status_code=200)
async def upload_service_thumbnail(service_id: str, file: UploadFile = File(...),
                                   user=Depends(admin_only), db=Depends(db_dep)):
    try:
        oid = ObjectId(service_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Service not found") from exc
    service = db.services.find_one({"_id": oid})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    filename = Path((file.filename or "").replace("\\", "/")).name
    try:
        content = await file.read(storage_max_bytes() + 1)
        if len(content) > storage_max_bytes():
            raise OverflowError("File exceeds configured maximum size")
        content_type = storage.validate_declared_image_upload(filename, file.content_type or "", len(content))
        detected_type = storage._validate_content(content, filename)
        if detected_type != content_type:
            raise ValueError("File content does not match its declared image type")
        key, size = storage.save_bytes(content, filename, content_type, resource_type="image", folder="service-thumbnails")
    except OverflowError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Private storage is unavailable") from exc
    now = datetime.now(timezone.utc)
    previous_version = service.get("version", 1)
    previous = {key: value for key, value in service.items() if key != "_id"}
    old_thumbnail = service.get("thumbnail")
    thumbnail = {
        "storage_key": key,
        "storage_provider": storage.provider,
        "storage_resource_type": "image",
        "original_filename": filename,
        "detected_content_type": detected_type,
        "file_size": size,
        "updated_at": now,
        "updated_by": ObjectId(user["_id"]),
        "alt_text": service.get("thumbnail_alt_text", {}),
    }
    history = list(service.get("thumbnail_history", []))
    if old_thumbnail:
        history.append({**old_thumbnail, "replaced_at": now, "replaced_by": ObjectId(user["_id"])})
    changes = {"thumbnail": thumbnail, "thumbnail_history": history, "version": previous_version + 1,
               "updated_at": now, "updated_by": ObjectId(user["_id"])}
    version_filter = {"version": previous_version} if "version" in service else {"version": {"$exists": False}}
    result = db.services.update_one({"_id": oid, **version_filter}, {"$set": changes})
    if not result.matched_count:
        try:
            storage.delete(key, provider=storage.provider, resource_type="image")
        except Exception:
            pass
        raise HTTPException(status_code=409, detail="Service changed concurrently; reload and retry")
    db.service_versions.insert_one({"service_id": oid, "version": previous_version,
                                    "snapshot": previous, "archived_at": now})
    audit(db, user["_id"], "service.thumbnail_updated", "service", oid, {"version": previous_version + 1})
    return {"thumbnail": thumbnail_response_metadata(thumbnail), "thumbnail_url": f"/api/v1/services/{oid}/thumbnail"}

def storage_max_bytes():
    from app.core.config import settings
    return settings.max_upload_size_mb * 1024 * 1024

@router.get("/{service_id}/thumbnail")
def get_service_thumbnail(service_id: str, user=Depends(optional_user), db=Depends(db_dep)):
    try:
        oid = ObjectId(service_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Service thumbnail not found") from exc
    service = db.services.find_one({"_id": oid})
    is_admin = bool(user and user.get("role") == "admin")
    thumbnail = (service or {}).get("thumbnail")
    if not service or not thumbnail or (not service.get("is_published") and not is_admin):
        raise HTTPException(status_code=404, detail="Service thumbnail not found")
    provider = thumbnail.get("storage_provider") or "local"
    content_type = thumbnail.get("detected_content_type")
    if content_type not in ("image/jpeg", "image/png"):
        raise HTTPException(status_code=404, detail="Service thumbnail not found")
    if provider == "cloudinary":
        try:
            url = storage.generate_download_url(
                thumbnail["storage_key"], provider=provider, resource_type="image", expires_in_seconds=300,
                file_format=Path(thumbnail.get("original_filename", "")).suffix.lstrip("."), attachment=False,
            )
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Private storage is unavailable") from exc
        return RedirectResponse(url, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
    try:
        content = storage.read_bytes(thumbnail["storage_key"], provider=provider)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Service thumbnail not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Private storage is unavailable") from exc
    return Response(content, media_type=content_type, headers={
        "Content-Disposition": 'inline; filename="service-thumbnail"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })
