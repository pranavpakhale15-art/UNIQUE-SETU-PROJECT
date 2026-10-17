from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from app.api.dependencies import current_user, db_dep
from app.core.permissions import has_permission
from app.schemas.task import TaskCreate, TaskPatch, TaskComplete
from app.services.audit_service import audit
from app.services.notification_service import notify

router=APIRouter()

def can_manage_task(task, user):
    return has_permission(user,"tasks:manage") and user.get("role") in ("owner", "admin")

def serialize(d):
    d["_id"]=str(d["_id"])
    for k,v in list(d.items()):
        if isinstance(v,ObjectId): d[k]=str(v)
        elif isinstance(v,datetime): d[k]=v.isoformat()
    return d

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
    if not has_permission(user,"tasks:manage") or user.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403,detail="Forbidden")
    if assignee_id:
        if user.get("role") not in ("owner","admin"): raise HTTPException(status_code=403,detail="Only owners and administrators may filter by assignee")
        try: query["assigned_staff_id"]=ObjectId(assignee_id)
        except Exception: raise HTTPException(status_code=422,detail="Invalid assignee id")
    conditions=[]
    if status: conditions.append({"status":status})
    if overdue: conditions.append({"due_date":{"$lt":datetime.now(timezone.utc)},"status":{"$nin":["completed","cancelled"]}})
    if conditions: query["$and"]=conditions
    total=db.application_tasks.count_documents(query)
    items=[]
    for task in db.application_tasks.find(query).sort("created_at",-1).skip((page-1)*page_size).limit(page_size):
        overdue_value=is_overdue(task)
        item=serialize(task)
        item["overdue"]=overdue_value
        items.append(item)
    return {"items":items,"page":page,"page_size":page_size,"total":total,"pages":(total+page_size-1)//page_size}

@router.get("/{task_id}")
def get_task(task_id:str,user=Depends(current_user),db=Depends(db_dep)):
    try: oid=ObjectId(task_id)
    except Exception: raise HTTPException(status_code=404,detail="Task not found")
    d=db.application_tasks.find_one({"_id":oid})
    if not d or not can_manage_task(d,user): raise HTTPException(status_code=404,detail="Task not found")
    item=serialize(d)
    item["overdue"]=is_overdue(d)
    return item

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
