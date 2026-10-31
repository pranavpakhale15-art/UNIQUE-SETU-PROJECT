from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from datetime import datetime, timezone
from app.api.dependencies import current_user, db_dep

router=APIRouter()
def serial(d):
    d["_id"]=str(d["_id"])
    for k,v in list(d.items()):
        if isinstance(v,ObjectId): d[k]=str(v)
        elif isinstance(v,datetime): d[k]=v.isoformat()
    d.pop("dedupe_key",None)
    return d

@router.get("")
def list_notifications(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),user=Depends(current_user),db=Depends(db_dep)):
    query={"recipient_id":ObjectId(user["_id"])}
    total=db.notifications.count_documents(query)
    return {"items":[serial(d) for d in db.notifications.find(query).sort("created_at",-1).skip((page-1)*page_size).limit(page_size)],
            "page":page,"page_size":page_size,"total":total,"pages":(total+page_size-1)//page_size}

@router.get("/unread-count")
def unread_count(user=Depends(current_user),db=Depends(db_dep)):
    return {"unread_count":db.notifications.count_documents({"recipient_id":ObjectId(user["_id"]),"is_read":False})}

@router.get("/unread-documents")
def unread_document_notifications(user=Depends(current_user),db=Depends(db_dep)):
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Customer access required")
    query = {
        "recipient_id": ObjectId(user["_id"]),
        "is_read": False,
        "event_type": {"$in": [
            "document.issued_available", "document.reviewed", "document.replacement_requested", "application.comment",
        ]},
    }
    items = []
    for record in db.notifications.find(query).sort("created_at", -1).limit(100):
        related_document_id = record.get("related_document_id")
        if not related_document_id and record.get("event_type") == "document.issued_available" and record.get("related_application_id"):
            legacy_document = db.application_documents.find_one({
                "application_id": record["related_application_id"],
                "customer_id": ObjectId(user["_id"]),
                "document_kind": "issued",
                "shared_at": {"$exists": True, "$ne": None},
            }, sort=[("shared_at", -1)])
            related_document_id = legacy_document.get("_id") if legacy_document else None
            if related_document_id:
                record["related_document_id"] = related_document_id
        if related_document_id:
            document = db.application_documents.find_one({
                "_id": related_document_id,
                "customer_id": ObjectId(user["_id"]),
                "application_id": record.get("related_application_id"),
            })
            if not document or (record.get("event_type") == "document.issued_available" and (
                document.get("document_kind") != "issued" or not document.get("shared_at")
            )):
                continue
        elif record.get("event_type") == "document.issued_available":
            continue
        if not record.get("related_application_id") or not db.applications.find_one({
            "_id": record["related_application_id"],
            "customer_id": ObjectId(user["_id"]),
        }):
            continue
        items.append(serial(record))
    return {"items": items, "total": len(items)}

@router.post("/{notification_id}/read")
def mark_read(notification_id:str,application_id:str|None=None,user=Depends(current_user),db=Depends(db_dep)):
    try: oid=ObjectId(notification_id)
    except Exception: raise HTTPException(status_code=404,detail="Notification not found")
    query={"_id":oid,"recipient_id":ObjectId(user["_id"])}
    if application_id:
        try: related_id=ObjectId(application_id)
        except Exception: raise HTTPException(status_code=404,detail="Notification not found")
        query["related_application_id"]=related_id
    result=db.notifications.update_one(query,{"$set":{"is_read":True,"updated_at":datetime.now(timezone.utc)}})
    if not result.matched_count: raise HTTPException(status_code=404,detail="Notification not found")
    return {"message":"Notification marked as read"}

@router.post("/read-all")
def read_all(user=Depends(current_user),db=Depends(db_dep)):
    result=db.notifications.update_many({"recipient_id":ObjectId(user["_id"]),"is_read":False},{"$set":{"is_read":True,"updated_at":datetime.now(timezone.utc)}})
    return {"updated_count":result.modified_count}
