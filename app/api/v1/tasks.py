from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from app.api.dependencies import current_user, db_dep
from app.core.permissions import has_permission
from app.schemas.task import TaskCreate, TaskPatch, TaskComplete
from app.services.audit_service import audit
from app.services.notification_service import notify
from app.services.retention_service import application_is_retained, completed_task_is_retained, completed_work_cutoff

router=APIRouter()

def can_manage_task(task, user):
    completed_at = task.get("completed_at")
    if (
        task.get("status") == "completed"
        and completed_at
        and not completed_task_is_retained(task)
    ):
        return False
    return has_permission(user,"tasks:manage") and user.get("role") in ("owner", "admin")

def can_read_task(task, user):
    completed_at = task.get("completed_at")
    if (
        task.get("status") == "completed"
        and completed_at
        and not completed_task_is_retained(task)
    ):
        return False
    if can_manage_task(task, user):
        return True
    return (
        user.get("role") == "staff"
        and has_permission(user, "tasks:read:assigned")
        and str(task.get("assigned_staff_id")) == user.get("_id")
    )

def serialize(d):
    d["_id"]=str(d["_id"])
    for k,v in list(d.items()):
        if isinstance(v,ObjectId): d[k]=str(v)
        elif isinstance(v,datetime): d[k]=v.isoformat()
    return d

def task_context(task, user, db):
    application_id = task.get("application_id")
    if not application_id:
        return {"application": None, "customer": None, "documents": []}
    application = db.applications.find_one({"_id": application_id})
    if not application or not application_is_retained(db, application):
        return {"application": None, "customer": None, "documents": []}
    if user.get("role") == "staff" and str(application.get("assigned_staff_id")) != user.get("_id"):
        return {"application": None, "customer": None, "documents": []}

    customer_record = db.users.find_one({"_id": application.get("customer_id")})
    customer = None
    if customer_record:
        customer = {
            "full_name": customer_record.get("full_name"),
            "mobile_number": customer_record.get("mobile_number"),
            "email": customer_record.get("email"),
        }
    service = db.services.find_one({"_id": application.get("service_id")})
    service_name = service.get("name", {}) if service else {}
    submitted_at = application.get("submitted_at")
    if not submitted_at:
        submitted_status = db.application_status_history.find_one({
            "application_id": application["_id"],
            "new_status": "Submitted by Customer",
        }, sort=[("timestamp", 1)])
        submitted_at = submitted_status.get("timestamp") if submitted_status else None
    if submitted_at is None and application.get("status") not in ("Draft", "Cancelled"):
        submitted_at = application.get("created_at")
    documents = []
    for document in db.application_documents.find({"application_id": application_id}):
        if document.get("document_kind") == "issued":
            continue
        documents.append({
            "id": str(document["_id"]),
            "file_name": document.get("original_filename"),
            "document_kind": document.get("document_kind", "customer_submission"),
            "verification_status": document.get("verification_status"),
            "submission_method": document.get("submission_method"),
            "created_at": document.get("created_at").isoformat() if document.get("created_at") else None,
        })
    return {
        "application": {
            "id": str(application["_id"]),
            "application_number": application.get("application_number"),
            "service_name_mr": service_name.get("mr", ""),
            "service_name_en": service_name.get("en", ""),
            "service_name_hi": service_name.get("hi", ""),
            "status": application.get("status"),
            "created_at": application.get("created_at").isoformat() if application.get("created_at") else None,
            "submitted_at": submitted_at.isoformat() if hasattr(submitted_at, "isoformat") else submitted_at,
            "application_data": application.get("application_data", {}),
            "form_requirements_snapshot": application.get("form_requirements_snapshot", []),
            "checklist_snapshot": application.get("checklist_snapshot", []),
            "customer_notes": application.get("customer_notes"),
        },
        "customer": customer,
        "documents": documents,
    }

def add_task_context(item, task, user, db):
    item.update(task_context(task, user, db))
    issued_document = db.application_documents.find_one({
        "application_id": task.get("application_id"),
        "document_kind": "issued",
    }) if task.get("application_id") else None
    item["issued_document"] = None
    if issued_document and item.get("application") and (user.get("role") != "staff" or issued_document.get("shared_at")):
        item["issued_document"] = {
            "id": str(issued_document["_id"]),
            "file_name": issued_document.get("original_filename"),
            "shared_at": issued_document.get("shared_at").isoformat() if issued_document.get("shared_at") else None,
        }
    return item

def is_overdue(task, now=None):
    now = now or datetime.now(timezone.utc)
    due_date = task.get("due_date")
    if due_date and due_date.tzinfo is None:
        due_date = due_date.replace(tzinfo=timezone.utc)
    return bool(due_date and due_date < now and task.get("status") not in ("completed", "cancelled"))

@router.post("",status_code=201)
def create_task(payload:TaskCreate,user=Depends(current_user),db=Depends(db_dep)):
    if not has_permission(user,"tasks:manage"): raise HTTPException(status_code=403,detail="Task management permission required")
    try: staff_id=ObjectId(payload.assigned_staff_id)
    except Exception: raise HTTPException(status_code=404,detail="Staff not found")
    if not db.users.find_one({"_id":staff_id,"role":"staff","account_status":"active"}): raise HTTPException(status_code=404,detail="Active staff not found")
    app_id=None
    if payload.application_id:
        try: app_id=ObjectId(payload.application_id)
        except Exception: raise HTTPException(status_code=404,detail="Application not found")
        if not db.applications.find_one({"_id":app_id}): raise HTTPException(status_code=404,detail="Application not found")
    now=datetime.now(timezone.utc)
    doc=payload.model_dump()|{"application_id":app_id,"assigned_staff_id":staff_id,"created_by":ObjectId(user["_id"]),"status":"open","created_at":now,"updated_at":now,"completed_at":None,"completion_notes":None}
    result=db.application_tasks.insert_one(doc)
    notify(db,str(staff_id),"task.assigned","Task assigned",payload.title,str(app_id) if app_id else None,f"task:{result.inserted_id}:assigned")
    audit(db,user["_id"],"task.created","task",result.inserted_id)
    return {"id":str(result.inserted_id)}

@router.get("")
def list_tasks(status:str|None=None,assignee_id:str|None=None,overdue:bool|None=None,page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),user=Depends(current_user),db=Depends(db_dep)):
    query={}
    role = user.get("role")
    if role == "staff" and has_permission(user, "tasks:read:assigned"):
        if assignee_id:
            raise HTTPException(status_code=403,detail="Staff may only view their own tasks")
        query["assigned_staff_id"] = ObjectId(user["_id"])
    elif not can_manage_task({}, user):
        raise HTTPException(status_code=403,detail="Forbidden")
    if assignee_id:
        if user.get("role") not in ("owner","admin"): raise HTTPException(status_code=403,detail="Only owners and administrators may filter by assignee")
        try: query["assigned_staff_id"]=ObjectId(assignee_id)
        except Exception: raise HTTPException(status_code=422,detail="Invalid assignee id")
    conditions=[]
    cutoff = completed_work_cutoff()
    conditions.append({"$or": [
        {"status": {"$ne": "completed"}},
        {"completed_at": {"$gte": cutoff}},
        {"completed_at": {"$exists": False}},
        {"completed_at": None},
    ]})
    if status: conditions.append({"status":status})
    if overdue: conditions.append({"due_date":{"$lt":datetime.now(timezone.utc)},"status":{"$nin":["completed","cancelled"]}})
    if conditions: query["$and"]=conditions
    total=db.application_tasks.count_documents(query)
    items=[]
    for task in db.application_tasks.find(query).sort("created_at",-1).skip((page-1)*page_size).limit(page_size):
        overdue_value=is_overdue(task)
        original_task = task.copy()
        item=serialize(task)
        item["overdue"]=overdue_value
        add_task_context(item, original_task, user, db)
        items.append(item)
    return {"items":items,"page":page,"page_size":page_size,"total":total,"pages":(total+page_size-1)//page_size}

@router.get("/{task_id}")
def get_task(task_id:str,user=Depends(current_user),db=Depends(db_dep)):
    try: oid=ObjectId(task_id)
    except Exception: raise HTTPException(status_code=404,detail="Task not found")
    d=db.application_tasks.find_one({"_id":oid})
    if not d or not can_read_task(d,user): raise HTTPException(status_code=404,detail="Task not found")
    original_task = d.copy()
    item=serialize(d)
    item["overdue"]=is_overdue(d)
    return add_task_context(item, original_task, user, db)

@router.patch("/{task_id}")
def patch_task(task_id:str,payload:TaskPatch,user=Depends(current_user),db=Depends(db_dep)):
    try: oid=ObjectId(task_id)
    except Exception: raise HTTPException(status_code=404,detail="Task not found")
    d=db.application_tasks.find_one({"_id":oid})
    if not d or not can_manage_task(d,user): raise HTTPException(status_code=404,detail="Task not found")
    changes=payload.model_dump(exclude_unset=True)
    if changes.get("status") not in (None,"open","in_progress","blocked","completed","cancelled"): raise HTTPException(status_code=422,detail="Invalid task status")
    changes["updated_at"]=datetime.now(timezone.utc)
    if changes.get("status") == "completed": changes["completed_at"]=changes["updated_at"]
    elif "status" in changes: changes["completed_at"]=None
    db.application_tasks.update_one({"_id":oid},{"$set":changes})
    audit(db,user["_id"],"task.updated","task",oid,{"fields":list(payload.model_fields_set)})
    return {"message":"Task updated"}

@router.post("/{task_id}/complete")
def complete_task(task_id:str,payload:TaskComplete,user=Depends(current_user),db=Depends(db_dep)):
    try: oid=ObjectId(task_id)
    except Exception: raise HTTPException(status_code=404,detail="Task not found")
    d=db.application_tasks.find_one({"_id":oid})
    if not d or not can_manage_task(d,user): raise HTTPException(status_code=404,detail="Task not found")
    now=datetime.now(timezone.utc)
    db.application_tasks.update_one({"_id":oid},{"$set":{"status":"completed","completion_notes":payload.completion_notes,"completed_at":now,"updated_at":now}})
    audit(db,user["_id"],"task.completed","task",oid)
    return {"message":"Task completed"}
