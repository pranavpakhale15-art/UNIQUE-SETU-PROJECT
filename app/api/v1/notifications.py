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

@router.post("/{notification_id}/read")
def mark_read(notification_id:str,user=Depends(current_user),db=Depends(db_dep)):
    try: oid=ObjectId(notification_id)
    except Exception: raise HTTPException(status_code=404,detail="Notification not found")
    result=db.notifications.update_one({"_id":oid,"recipient_id":ObjectId(user["_id"])},{"$set":{"is_read":True,"updated_at":datetime.now(timezone.utc)}})
    if not result.matched_count: raise HTTPException(status_code=404,detail="Notification not found")
    return {"message":"Notification marked as read"}

@router.post("/read-all")
def read_all(user=Depends(current_user),db=Depends(db_dep)):
    result=db.notifications.update_many({"recipient_id":ObjectId(user["_id"]),"is_read":False},{"$set":{"is_read":True,"updated_at":datetime.now(timezone.utc)}})
    return {"updated_count":result.modified_count}
