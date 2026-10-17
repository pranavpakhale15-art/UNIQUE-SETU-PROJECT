from datetime import datetime, timezone
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from app.api.dependencies import current_user, db_dep, owner_or_admin
from app.core.permissions import has_permission
from app.schemas.application import ApplicationCreate, ApplicationPatch, StatusChange, AssignRequest, CommentCreate, CustomerApplicationResponse, OwnerApplicationFields
from app.utils.identifiers import application_number
from app.services.audit_service import audit
from app.services.notification_service import notify
from app.services.retention_service import (
    application_is_retained,
    completed_work_cutoff,
    retained_application_filter,
)

router = APIRouter()
APPLICATION_PROGRESS_ORDER = (
    "Approved by Authority",
    "Awaiting Government Decision",
    "Submitted to Government Authority",
    "Rejected by Authority",
    "In Progress",
    "Ready for Processing",
    "Correction Requested",
    "Documents Incomplete",
    "Documents Under Review",
    "Received by Shop",
    "Submitted by Customer",
    "Draft",
    "Rejected by Shop",
    "Cancelled",
)
APPLICATION_PROGRESS_RANK = {status: rank for rank, status in enumerate(APPLICATION_PROGRESS_ORDER)}
STATUSES = {"Draft","Submitted by Customer","Received by Shop","Documents Under Review","Documents Incomplete",
"Correction Requested","Ready for Processing","In Progress","Submitted to Government Authority","Awaiting Government Decision",
"Approved by Authority","Rejected by Authority","Completed by Shop","Rejected by Shop","Cancelled"}
TRANSITIONS = {
"Draft": {"Submitted by Customer","Cancelled"},
"Submitted by Customer": {"Received by Shop","Documents Under Review","Rejected by Shop","Cancelled"},
"Received by Shop": {"Documents Under Review","Documents Incomplete","Rejected by Shop","Cancelled"},
"Documents Under Review": {"Documents Incomplete","Correction Requested","Ready for Processing","Rejected by Shop","Cancelled"},
"Documents Incomplete": {"Documents Under Review","Correction Requested","Rejected by Shop","Cancelled"},
"Correction Requested": {"Documents Under Review","Documents Incomplete","Rejected by Shop","Cancelled"},
"Ready for Processing": {"In Progress","Rejected by Shop","Cancelled"},
"In Progress": {"Submitted to Government Authority","Completed by Shop","Rejected by Shop","Cancelled"},
"Submitted to Government Authority": {"Awaiting Government Decision","Approved by Authority","Rejected by Authority"},
"Awaiting Government Decision": {"Approved by Authority","Rejected by Authority"},
"Approved by Authority": {"Completed by Shop"},
"Rejected by Authority": {"Completed by Shop","In Progress"},
"Completed by Shop": set(), "Rejected by Shop": set(), "Cancelled": set()
}

def serial(doc):
    if not doc: return None
    doc["_id"] = str(doc["_id"])
    for k,v in list(doc.items()):
        if isinstance(v, ObjectId): doc[k] = str(v)
        elif isinstance(v, datetime): doc[k] = v.isoformat()
    return doc

def customer_summary(db, customer_id):
    try:
        customer_id = ObjectId(customer_id)
    except Exception:
        return None
    customer = db.users.find_one({"_id": customer_id})
    if not customer:
        return None
    return {
        "full_name": customer.get("full_name"),
        "mobile_number": customer.get("mobile_number"),
        "email": customer.get("email"),
    }

def submission_timestamp(db, application):
    timestamp = application.get("submitted_at")
    if timestamp:
        return timestamp.isoformat() if hasattr(timestamp, "isoformat") else timestamp
    history = db.application_status_history.find_one({
        "application_id": application.get("_id"),
        "new_status": "Submitted by Customer",
    }, sort=[("timestamp", 1)])
    timestamp = history.get("timestamp") if history else None
    if timestamp is None and application.get("status") not in ("Draft", "Cancelled"):
        timestamp = application.get("created_at")
    return timestamp.isoformat() if hasattr(timestamp, "isoformat") else timestamp

def completion_timestamp(db, application):
    timestamp = application.get("completed_at")
    if timestamp:
        return timestamp
    history = db.application_status_history.find_one({
        "application_id": application["_id"],
        "new_status": "Completed by Shop",
    }, sort=[("timestamp", -1)])
    return history.get("timestamp") if history else None


def issued_document_for_application(db, application):
    return db.application_documents.find_one({
        "application_id": application["_id"],
        "customer_id": application.get("customer_id"),
        "document_kind": "issued",
    })


def application_dashboard_section(application, issued_document):
    if application.get("status") != "Completed by Shop":
        return "in_progress"
    if issued_document and issued_document.get("shared_at"):
        return "completed"
    return "awaiting_customer_sharing"


def sort_applications_by_progress(items):
    return sorted(
        items,
        key=lambda item: (
            APPLICATION_PROGRESS_RANK.get(item.get("status"), len(APPLICATION_PROGRESS_RANK)),
            -_sort_timestamp(item.get("updated_at")),
            item.get("application_number") or "",
        ),
    )


def _sort_timestamp(value):
    if not value:
        return 0.0
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def _shared_completed_application_ids(db):
    shared_ids = []
    for document in db.application_documents.find({
        "document_kind": "issued",
        "shared_at": {"$exists": True, "$ne": None},
    }):
        application = db.applications.find_one({
            "_id": document.get("application_id"),
            "customer_id": document.get("customer_id"),
            "status": "Completed by Shop",
        })
        if application:
            shared_ids.append(application["_id"])
    return shared_ids


def _final_document_application_query(user):
    role = user.get("role")
    if role in ("owner", "admin"):
        if role == "owner" and not has_permission(user, "applications:manage"):
            raise HTTPException(status_code=403, detail="Application management permission required")
        return {}
    if role == "staff" and has_permission(user, "applications:read:assigned"):
        return {"assigned_staff_id": ObjectId(user["_id"])}
    if role == "customer" and has_permission(user, "applications:read:self"):
        return {"customer_id": ObjectId(user["_id"])}
    raise HTTPException(status_code=403, detail="Forbidden")


def _final_document_work(db, user, shared):
    cutoff = completed_work_cutoff()
    query = {
        "status": "Completed by Shop",
        **_final_document_application_query(user),
        "$and": [retained_application_filter(db)],
    }
    records = []
    for application in db.applications.find(query):
        if not application_is_retained(db, application):
            continue
        issued_document = issued_document_for_application(db, application)
        section = application_dashboard_section(application, issued_document)
        if (section == "completed") != shared:
            continue
        completed_at = completion_timestamp(db, application)
        if not completed_at:
            continue
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)
        if completed_at < cutoff:
            continue
        service = db.services.find_one({"_id": application.get("service_id")})
        service_name = service.get("name", {}) if service else {}
        customer = customer_summary(db, application.get("customer_id"))
        item = {
            "id": str(application["_id"]),
            "application_number": application.get("application_number"),
            "status": application.get("status"),
            "completed_at": completed_at.isoformat(),
            "updated_at": application.get("updated_at").isoformat() if application.get("updated_at") else None,
            "service_name_mr": service_name.get("mr", ""),
            "service_name_en": service_name.get("en", ""),
            "service_name_hi": service_name.get("hi", ""),
            "customer": customer if user.get("role") != "customer" else None,
            "final_document_status": "Shared with customer" if section == "completed" else (
                "Uploaded, not shared" if issued_document and issued_document.get("storage_key") else "Not uploaded"
            ),
            "issued_document": None,
        }
        if issued_document:
            item["issued_document"] = {
                "id": str(issued_document["_id"]),
                "file_name": issued_document.get("original_filename"),
                "created_at": issued_document.get("created_at").isoformat() if issued_document.get("created_at") else None,
                "updated_at": issued_document.get("updated_at").isoformat() if issued_document.get("updated_at") else None,
                "shared_at": issued_document.get("shared_at").isoformat() if issued_document.get("shared_at") else None,
            }
        records.append(item)
    return sorted(records, key=lambda item: (-_sort_timestamp(item["completed_at"]), item["application_number"] or ""))


def can_access(app, user, db=None):
    if db is not None and not application_is_retained(db, app):
        return False
    role = user.get("role")
    return (role == "admin" or
            (role == "customer" and has_permission(user, "applications:read:self") and str(app.get("customer_id")) == user["_id"]) or
            (role == "staff" and has_permission(user, "applications:read:assigned") and str(app.get("assigned_staff_id")) == user["_id"]) or
            (role == "owner" and has_permission(user, "applications:manage")))

@router.post("", status_code=201)
def create_application(payload: ApplicationCreate, user=Depends(current_user), db=Depends(db_dep)):
    if user.get("role") != "customer" or not has_permission(user,"applications:create:self"):
        raise HTTPException(status_code=403, detail="Only customers can create their own applications")
    try: service_id = ObjectId(payload.service_id)
    except Exception: raise HTTPException(status_code=404, detail="Service not found")
    service = db.services.find_one({"_id": service_id, "is_published": True})
    if not service: raise HTTPException(status_code=404, detail="Published service not found")
    now = datetime.now(timezone.utc)
    app = {"application_number": application_number(), "customer_id": ObjectId(user["_id"]), "service_id": service_id,
           "service_version": service.get("version",1), "checklist_snapshot": service.get("document_requirements",[]),
           "form_requirements_snapshot": service.get("form_requirements",[]), "application_data": {},
           "status":"Draft", "priority":"normal", "assigned_staff_id":None, "internal_due_date":None,
           "customer_notes":payload.customer_notes, "internal_notes":None, "created_at":now, "updated_at":now, "completed_at":None}
    result = db.applications.insert_one(app)
    db.application_status_history.insert_one({"application_id":result.inserted_id,"previous_status":None,"new_status":"Draft",
        "actor_id":ObjectId(user["_id"]),"timestamp":now,"reason":"Application created"})
    return {"id":str(result.inserted_id),"application_number":app["application_number"],"status":"Draft"}

@router.get("")
def list_applications(status: str | None = None, q: str | None = None, page: int = Query(1,ge=1),
                      page_size: int = Query(20,ge=1,le=100), user=Depends(current_user), db=Depends(db_dep)):
    query = {}
    role = user.get("role")
    if role == "customer" and has_permission(user,"applications:read:self"): query["customer_id"] = ObjectId(user["_id"])
    elif role == "staff" and has_permission(user,"applications:read:assigned"): query["assigned_staff_id"] = ObjectId(user["_id"])
    elif role == "admin" or (role=="owner" and has_permission(user,"applications:manage")): pass
    else: raise HTTPException(status_code=403,detail="Forbidden")
    if status: query["status"] = status
    if q: query["application_number"] = {"$regex": re.escape(q), "$options":"i"}
    section_filter = {"status": {"$ne": "Completed by Shop"}}
    if role == "customer":
        section_filter = {"_id": {"$nin": _shared_completed_application_ids(db)}}
    query["$and"] = [retained_application_filter(db), section_filter]
    applications = [serial(x) for x in db.applications.find(query)]
    total = len(applications)
    items = sort_applications_by_progress(applications)
    items = items[(page-1)*page_size:page*page_size]
    for item in items:
        service_id = item.get("service_id")
        item["submitted_at"] = submission_timestamp(db, {
            "_id": ObjectId(item["_id"]),
            "status": item.get("status"),
            "created_at": item.get("created_at"),
            "submitted_at": item.get("submitted_at"),
        })
        service = db.services.find_one({"_id": ObjectId(service_id)}) if service_id else None
        item["service"] = serial(service) if service else None
        if role in ("owner", "staff", "admin"):
            customer_id = item.get("customer_id")
            item["customer"] = customer_summary(db, customer_id) if customer_id else None
        if service:
            item["service_name_mr"] = service.get("name", {}).get("mr", "")
            item["service_name_en"] = service.get("name", {}).get("en", "")
            item["service_name_hi"] = service.get("name", {}).get("hi", "")
        if role == "staff":
            item.pop("internal_notes", None)
    if role == "customer":
        items = [CustomerApplicationResponse.model_validate(item).model_dump(by_alias=True) for item in items]
    return {"items":items,"page":page,"page_size":page_size,"total":total,"pages":(total+page_size-1)//page_size}

@router.get("/completed-work")
def list_completed_work(user=Depends(current_user), db=Depends(db_dep)):
    items = _final_document_work(db, user, shared=True)
    return {"items": items, "total": len(items)}


@router.get("/awaiting-customer-sharing")
def list_awaiting_customer_sharing(user=Depends(current_user), db=Depends(db_dep)):
    items = _final_document_work(db, user, shared=False)
    return {"items": items, "total": len(items)}

@router.get("/{application_id}")
def get_application(application_id: str, user=Depends(current_user), db=Depends(db_dep)):
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    app=db.applications.find_one({"_id":oid})
    if not app or not can_access(app,user,db): raise HTTPException(status_code=404,detail="Application not found")
    submitted_at = submission_timestamp(db, app)
    app=serial(app)
    app["submitted_at"] = submitted_at
    app["service"] = serial(db.services.find_one({"_id":ObjectId(app["service_id"])})) if app.get("service_id") else None
    if user.get("role") == "customer":
        return CustomerApplicationResponse.model_validate(app)
    customer_id = app.get("customer_id")
    app["customer"] = customer_summary(db, customer_id) if customer_id else None
    if user.get("role") == "staff":
        app.pop("internal_notes", None)
    return app

@router.patch("/{application_id}")
def patch_application(application_id: str, payload: ApplicationPatch, user=Depends(current_user), db=Depends(db_dep)):
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    app=db.applications.find_one({"_id":oid})
    if (user.get("role")!="customer" or not has_permission(user,"applications:create:self") or not app or
            str(app["customer_id"]) != user["_id"] or app["status"] != "Draft"):
        raise HTTPException(status_code=404,detail="Draft application not found")
    changes = payload.model_dump(exclude_unset=True)
    if "application_data" in changes:
        values = changes["application_data"] or {}
        allowed_ids = {
            str(item.get("id"))
            for item in app.get("form_requirements_snapshot", [])
            if isinstance(item, dict) and item.get("id")
        }
        if set(values) - allowed_ids:
            raise HTTPException(status_code=422, detail="Unknown application data field")
        if any(not isinstance(value, str) or len(value) > 2000 for value in values.values()):
            raise HTTPException(status_code=422, detail="Application data values must be text up to 2000 characters")
        changes["application_data"] = (app.get("application_data") or {}) | values
    db.applications.update_one({"_id":oid},{"$set":changes|{"updated_at":datetime.now(timezone.utc)}})
    return {"message":"Draft updated"}

@router.post("/{application_id}/submit")
def submit_application(application_id: str, user=Depends(current_user), db=Depends(db_dep)):
    return change_status(application_id, StatusChange(status="Submitted by Customer"), user, db)

def change_status(application_id, payload, user, db):
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    app=db.applications.find_one({"_id":oid})
    if not app or not can_access(app,user,db): raise HTTPException(status_code=404,detail="Application not found")
    target=payload.status
    if target not in STATUSES: raise HTTPException(status_code=422,detail="Unknown application status")
    if user.get("role")=="customer":
        if not has_permission(user,"applications:create:self"):
            raise HTTPException(status_code=403,detail="Application permission required")
        if target == "Cancelled" and app["status"] in ("Draft", "Submitted by Customer"):
            pass
        elif target != "Submitted by Customer" or app["status"] != "Draft":
            raise HTTPException(status_code=403,detail="Customers may only submit drafts or cancel early applications")
    elif user.get("role")=="staff":
        raise HTTPException(status_code=403,detail="Staff accounts are read-only")
    elif user.get("role")=="owner" and not has_permission(user,"applications:manage"):
        raise HTTPException(status_code=403,detail="Application management permission required")
    elif user.get("role") not in ("owner","admin"): raise HTTPException(status_code=403,detail="Forbidden")
    if target not in TRANSITIONS.get(app["status"],set()): raise HTTPException(status_code=409,detail=f"Invalid status transition: {app['status']} -> {target}")
    if target == "Submitted by Customer":
        required_data_ids = {
            str(item.get("id"))
            for item in app.get("form_requirements_snapshot", [])
            if isinstance(item, dict) and item.get("required", True)
        }
        application_data = app.get("application_data") or {}
        missing_data_ids = sorted(
            field_id for field_id in required_data_ids
            if not str(application_data.get(field_id, "")).strip()
        )
        if missing_data_ids:
            raise HTTPException(
                status_code=409,
                detail={"message": "Required application details are missing", "missing_form_field_ids": missing_data_ids},
            )
        required_ids = {str(item.get("id") or item.get("item_id") or item.get("_id"))
                for item in app.get("checklist_snapshot", []) if isinstance(item,dict) and item.get("required", True)}
        uploaded_ids = {str(item) for item in db.application_documents.distinct("checklist_item_id", {"application_id": oid})}
        missing_ids = sorted(required_ids - uploaded_ids)
        if missing_ids:
            raise HTTPException(status_code=409, detail={"message": "Required documents are missing", "missing_checklist_item_ids": missing_ids})
    now=datetime.now(timezone.utc)
    result=db.applications.update_one({"_id":oid,"status":app["status"]},{"$set":{
        "status":target,
        "updated_at":now,
        "completed_at":now if target=="Completed by Shop" else app.get("completed_at"),
        "submitted_at":now if target=="Submitted by Customer" else app.get("submitted_at"),
    }})
    if not result.modified_count: raise HTTPException(status_code=409,detail="Application changed concurrently; reload and retry")
    history_result = db.application_status_history.insert_one({"application_id":oid,"previous_status":app["status"],"new_status":target,"actor_id":ObjectId(user["_id"]),"timestamp":now,"reason":payload.reason})
    audit(db,user["_id"],"application.status_changed","application",oid,{"from":app["status"],"to":target})
    notify(db,str(app["customer_id"]),"application.status_changed","Application status updated",f"Your application {app['application_number']} is now: {target}",str(oid),f"application:{oid}:status:{history_result.inserted_id}")
    return {"message":"Status updated","status":target}

@router.post("/{application_id}/status")
def status_endpoint(application_id: str, payload: StatusChange, user=Depends(current_user), db=Depends(db_dep)):
    return change_status(application_id,payload,user,db)

@router.post("/{application_id}/assign")
def assign(application_id: str, payload: AssignRequest, user=Depends(owner_or_admin), db=Depends(db_dep)):
    try: oid=ObjectId(application_id); staff_oid=ObjectId(payload.staff_id)
    except Exception: raise HTTPException(status_code=404,detail="Application or staff member not found")
    staff=db.users.find_one({"_id":staff_oid,"role":"staff","account_status":"active"})
    if not staff: raise HTTPException(status_code=404,detail="Active staff member not found")
    result=db.applications.update_one({"_id":oid},{"$set":{"assigned_staff_id":staff_oid,"updated_at":datetime.now(timezone.utc)}})
    if not result.matched_count: raise HTTPException(status_code=404,detail="Application not found")
    notify(db,str(staff_oid),"application.assigned","Application assigned","An application has been assigned to you",str(oid),f"{oid}:assigned:{staff_oid}")
    audit(db,user["_id"],"application.assigned","application",oid,{"staff_id":str(staff_oid)})
    return {"message":"Application assigned"}

@router.patch("/{application_id}/owner-fields")
def update_owner_fields(application_id: str, payload: OwnerApplicationFields, user=Depends(owner_or_admin), db=Depends(db_dep)):
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    changes=payload.model_dump(exclude_unset=True)
    if not changes: raise HTTPException(status_code=422,detail="At least one owner field must be provided")
    changes["updated_at"]=datetime.now(timezone.utc)
    result=db.applications.update_one({"_id":oid},{"$set":changes})
    if not result.matched_count: raise HTTPException(status_code=404,detail="Application not found")
    audit(db,user["_id"],"application.owner_fields_updated","application",oid,{"fields":list(payload.model_fields_set)})
    return {"message":"Owner fields updated"}

@router.get("/{application_id}/history")
def history(application_id: str, user=Depends(current_user), db=Depends(db_dep)):
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    app=db.applications.find_one({"_id":oid})
    if not app or not can_access(app,user,db): raise HTTPException(status_code=404,detail="Application not found")
    return [serial(x) for x in db.application_status_history.find({"application_id":oid}).sort("timestamp",1)]

@router.post("/{application_id}/comments", status_code=201)
def add_comment(application_id: str, payload: CommentCreate, user=Depends(current_user), db=Depends(db_dep)):
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    app=db.applications.find_one({"_id":oid})
    if not app or not can_access(app,user,db): raise HTTPException(status_code=404,detail="Application not found")
    if payload.visibility not in ("customer","internal"): raise HTTPException(status_code=422,detail="Invalid visibility")
    if user.get("role") == "staff":
        raise HTTPException(status_code=403,detail="Staff accounts are read-only")
    if payload.visibility=="internal" and not has_permission(user,"applications:manage"):
        raise HTTPException(status_code=403,detail="Internal comments are owner-only")
    comment={"application_id":oid,"author_id":ObjectId(user["_id"]),"message":payload.message,"visibility":payload.visibility,"created_at":datetime.now(timezone.utc)}
    db.application_comments.insert_one(comment)
    if payload.visibility=="customer":
        notify(db,str(app["customer_id"]),"application.comment","New application comment","A comment was added to your application",str(oid))
    return {"message":"Comment added"}

@router.get("/{application_id}/comments")
def list_comments(application_id: str, user=Depends(current_user), db=Depends(db_dep)):
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    app=db.applications.find_one({"_id":oid})
    if not app or not can_access(app,user,db): raise HTTPException(status_code=404,detail="Application not found")
    query={"application_id":oid}
    if user.get("role") in ("customer", "staff"): query["visibility"]="customer"
    comments=[]
    for comment in db.application_comments.find(query).sort("created_at",1):
        comment["_id"]=str(comment["_id"])
        comment["application_id"]=str(comment["application_id"])
        comment["author_id"]=str(comment["author_id"])
        comment["created_at"]=comment["created_at"].isoformat()
        comments.append(comment)
    return comments
