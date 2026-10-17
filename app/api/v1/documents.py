from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from bson import ObjectId
from app.api.dependencies import current_user, db_dep
from app.services.storage_service import StorageService
from app.services.audit_service import audit
from app.services.notification_service import notify
from app.core.config import settings
from app.core.permissions import has_permission
from app.schemas.document import (UploadUrlRequest, ConfirmUploadRequest, PhysicalDocumentReceiptRequest,
                                  DocumentReviewRequest, ReplacementRequest)

router=APIRouter()
storage=StorageService()

def app_access(app,user):
    role=user.get("role")
    return (role=="admin" or
            (role=="customer" and has_permission(user,"documents:manage:self") and str(app.get("customer_id"))==user["_id"]) or
            (role=="staff" and has_permission(user,"applications:read:assigned") and str(app.get("assigned_staff_id"))==user["_id"]) or
            (role=="owner" and has_permission(user,"documents:review")))

def has_checklist_item(app, checklist_item_id):
    return any((item if isinstance(item,str) else str(item.get("id") or item.get("item_id") or item.get("_id"))) == checklist_item_id
               for item in app.get("checklist_snapshot", []))

def can_review_documents(user):
    return (user.get("role")=="admin" or
            (user.get("role")=="owner" and has_permission(user,"documents:review")))

@router.post("/applications/{application_id}/documents/upload-url")
def upload_url(application_id: str, payload: UploadUrlRequest, user=Depends(current_user), db=Depends(db_dep)):
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers may upload application documents")
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    app=db.applications.find_one({"_id":oid})
    if not app or not app_access(app,user): raise HTTPException(status_code=404,detail="Application not found")
    if user.get("role")=="customer" and app.get("status") not in ("Draft","Documents Incomplete","Correction Requested"):
        raise HTTPException(status_code=409,detail="Documents cannot be uploaded in the current application status")
    if not has_checklist_item(app, payload.checklist_item_id):
        raise HTTPException(status_code=422,detail="Checklist item is not part of this application snapshot")
    try:
        storage.validate_declared_upload(payload.filename,payload.content_type,payload.file_size)
    except OverflowError as exc:
        raise HTTPException(status_code=413,detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    replacement=None
    if payload.replace_document_id:
        try: replacement_id=ObjectId(payload.replace_document_id)
        except Exception: raise HTTPException(status_code=404,detail="Document not found")
        replacement=db.application_documents.find_one({"_id":replacement_id,"application_id":oid,
            "checklist_item_id":payload.checklist_item_id})
        if not replacement: raise HTTPException(status_code=404,detail="Document not found")
        if user.get("role")=="customer" and str(replacement["customer_id"])!=user["_id"]:
            raise HTTPException(status_code=404,detail="Document not found")
        if replacement.get("verification_status") not in ("correction_requested","rejected"):
            raise HTTPException(status_code=409,detail="Document is not awaiting replacement")
    now=datetime.now(timezone.utc)
    intent_id=ObjectId()
    provider=settings.storage_provider.lower()
    intent={"_id":intent_id,"application_id":oid,"user_id":ObjectId(user["_id"]),
            "checklist_item_id":payload.checklist_item_id,"filename":Path(payload.filename.replace("\\", "/")).name,
            "content_type":payload.content_type,"expected_size":payload.file_size,
            "replace_document_id":replacement["_id"] if replacement else None,
            "storage_provider":provider,"state":"pending","created_at":now,"expires_at":now+timedelta(minutes=5)}
    if provider=="s3":
        try: upload_url_value,fields,key=storage.generate_upload_url(intent["filename"],payload.content_type,payload.file_size)
        except Exception as exc: raise HTTPException(status_code=503,detail="Private storage is unavailable") from exc
        intent["storage_key"]=key
        db.document_upload_intents.insert_one(intent)
        return {"upload_id":str(intent_id),"upload_mode":"signed_post","url":upload_url_value,
                "fields":fields,"expires_in_seconds":300}
    db.document_upload_intents.insert_one(intent)
    return {"upload_id":str(intent_id),"upload_mode":"multipart",
            "upload_endpoint":f"/api/v1/applications/{application_id}/documents/confirm",
            "required_fields":{"upload_id":str(intent_id),"file":"multipart file"},"expires_in_seconds":300}

@router.post("/applications/{application_id}/documents/confirm", status_code=201)
async def upload_document(application_id: str, request: Request, user=Depends(current_user), db=Depends(db_dep)):
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Only customers may upload application documents")
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    app=db.applications.find_one({"_id":oid})
    if not app or not app_access(app,user): raise HTTPException(status_code=404,detail="Application not found")
    if str(app["customer_id"])!=user["_id"]: raise HTTPException(status_code=403,detail="Forbidden")
    upload_file=None
    if request.headers.get("content-type","").startswith("application/json"):
        try: payload=ConfirmUploadRequest.model_validate(await request.json())
        except Exception as exc: raise HTTPException(status_code=422,detail="Invalid upload confirmation") from exc
        upload_id=payload.upload_id
    else:
        form=await request.form()
        upload_id=str(form.get("upload_id") or "")
        upload_file=form.get("file")
    try: intent_id=ObjectId(upload_id)
    except Exception: raise HTTPException(status_code=404,detail="Upload intent not found")
    now=datetime.now(timezone.utc)
    intent=db.document_upload_intents.find_one({"_id":intent_id,"application_id":oid,"user_id":ObjectId(user["_id"]),
        "state":"pending","expires_at":{"$gt":now}})
    if not intent: raise HTTPException(status_code=404,detail="Upload intent not found or expired")
    if not has_checklist_item(app,intent["checklist_item_id"]):
        raise HTTPException(status_code=422,detail="Checklist item is not part of this application snapshot")
    claim=db.document_upload_intents.update_one({"_id":intent_id,"state":"pending"},{"$set":{"state":"processing"}})
    if not claim.modified_count: raise HTTPException(status_code=409,detail="Upload confirmation is already being processed")
    provider=intent.get("storage_provider") or ("s3" if intent.get("storage_key") else "local")
    try:
        if upload_file is not None:
            if provider not in ("local", "cloudinary") or not hasattr(upload_file,"read"):
                raise ValueError("Multipart confirmation is available only with local or Cloudinary storage")
            content=await upload_file.read(settings.max_upload_size_mb*1024*1024+1)
            if len(content)>settings.max_upload_size_mb*1024*1024:
                raise OverflowError("File exceeds configured maximum size")
            if len(content)!=intent["expected_size"]:
                raise ValueError("Uploaded file size does not match the upload request")
            key,size=storage.save_bytes(content,intent["filename"],intent["content_type"],provider=provider)
            detected_type=storage.detect_content_type(content)
        elif provider=="s3":
            key=intent["storage_key"]
            size,detected_type=storage.verify_uploaded_object(key,intent["filename"],intent["expected_size"],provider=provider)
            key=storage.finalize_upload(key,str(oid),provider=provider)
        else:
            raise ValueError("Local and Cloudinary storage require a multipart file")
    except OverflowError as exc:
        db.document_upload_intents.update_one({"_id":intent_id},{"$set":{"state":"failed"}})
        raise HTTPException(status_code=413,detail=str(exc)) from exc
    except ValueError as exc:
        db.document_upload_intents.update_one({"_id":intent_id},{"$set":{"state":"failed"}})
        if provider=="s3" and intent.get("storage_key"):
            storage.delete(intent["storage_key"],provider=provider)
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    except Exception as exc:
        db.document_upload_intents.update_one({"_id":intent_id},{"$set":{"state":"failed"}})
        raise HTTPException(status_code=503,detail="Private storage is unavailable") from exc
    now=datetime.now(timezone.utc)
    replace_id=intent.get("replace_document_id")
    if replace_id:
        current=db.application_documents.find_one({"_id":replace_id,"application_id":oid})
        if not current:
            db.document_upload_intents.update_one({"_id":intent_id},{"$set":{"state":"failed"}})
            storage.delete(key,provider=provider)
            raise HTTPException(status_code=404,detail="Document to replace not found")
        previous={field:current.get(field) for field in ("storage_key","storage_provider","storage_resource_type",
            "original_filename","detected_content_type","file_size","uploaded_by","created_at")}
        previous["replaced_at"]=now
        previous["replaced_by"]=ObjectId(user["_id"])
        db.application_documents.update_one({"_id":replace_id},{"$push":{"replacement_history":previous},"$set":{
            "storage_key":key,"storage_provider":provider,"storage_resource_type":"raw",
            "original_filename":intent["filename"],"detected_content_type":detected_type,
            "file_size":size,"uploaded_by":ObjectId(user["_id"]),"verification_status":"pending",
            "reviewer_comment":None,"updated_at":now}})
        document_id=replace_id
        audit(db,user["_id"],"document.replaced","document",replace_id,{"application_id":str(oid)})
    else:
        doc={"application_id":oid,"customer_id":app["customer_id"],"checklist_item_id":intent["checklist_item_id"],
             "submission_method":"online","storage_key":key,"storage_provider":provider,"storage_resource_type":"raw",
             "original_filename":intent["filename"],"detected_content_type":detected_type,
             "file_size":size,"uploaded_by":ObjectId(user["_id"]),"received_by_staff_id":None,"physical_document_status":None,
             "verification_status":"pending","reviewer_comment":None,"created_at":now,"updated_at":now,"replacement_history":[]}
        document_id=db.application_documents.insert_one(doc).inserted_id
        audit(db,user["_id"],"document.uploaded","document",document_id,{"application_id":str(oid)})
    db.document_upload_intents.update_one({"_id":intent_id,"state":"processing"},{"$set":{"state":"used","used_at":now}})
    return {"id":str(document_id),"verification_status":"pending"}

@router.post("/applications/{application_id}/documents/physical-receipt", status_code=201)
def physical_receipt(application_id: str, payload: PhysicalDocumentReceiptRequest,
                     user=Depends(current_user), db=Depends(db_dep)):
    if not can_review_documents(user): raise HTTPException(status_code=403,detail="Document review permission required")
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    app=db.applications.find_one({"_id":oid})
    if not app or not app_access(app,user): raise HTTPException(status_code=404,detail="Application not found")
    if not has_checklist_item(app,payload.checklist_item_id): raise HTTPException(status_code=422,detail="Checklist item is not part of this application snapshot")
    now=datetime.now(timezone.utc)
    doc={"application_id":oid,"customer_id":app["customer_id"],"checklist_item_id":payload.checklist_item_id,
         "submission_method":"in_shop","storage_key":None,"storage_provider":None,"storage_resource_type":None,
         "original_filename":None,"detected_content_type":None,"file_size":0,
         "uploaded_by":ObjectId(user["_id"]),"received_by_staff_id":ObjectId(user["_id"]),"physical_document_status":"received",
         "verification_status":"pending","reviewer_comment":payload.notes,"created_at":now,"updated_at":now,"replacement_history":[]}
    result=db.application_documents.insert_one(doc)
    audit(db,user["_id"],"document.physical_received","document",result.inserted_id,{"application_id":application_id})
    return {"id":str(result.inserted_id),"physical_document_status":"received"}

@router.get("/applications/{application_id}/documents")
def list_documents(application_id: str, user=Depends(current_user), db=Depends(db_dep)):
    try: oid=ObjectId(application_id)
    except Exception: raise HTTPException(status_code=404,detail="Application not found")
    app=db.applications.find_one({"_id":oid})
    if not app or not app_access(app,user): raise HTTPException(status_code=404,detail="Application not found")
    docs=[]
    for d in db.application_documents.find({"application_id":oid}):
        d["_id"]=str(d["_id"]); d["application_id"]=str(d["application_id"]); d["customer_id"]=str(d["customer_id"]); d["uploaded_by"]=str(d["uploaded_by"])
        d.pop("storage_key",None)
        d.pop("storage_provider",None)
        d.pop("storage_resource_type",None)
        for history_entry in d.get("replacement_history",[]):
            history_entry.pop("storage_key",None)
            history_entry.pop("storage_provider",None)
            history_entry.pop("storage_resource_type",None)
            for field in ("uploaded_by", "replaced_by"):
                if isinstance(history_entry.get(field), ObjectId): history_entry[field]=str(history_entry[field])
            for field in ("created_at", "replaced_at"):
                if isinstance(history_entry.get(field), datetime): history_entry[field]=history_entry[field].isoformat()
        if d.get("received_by_staff_id"): d["received_by_staff_id"]=str(d["received_by_staff_id"])
        for k in ("created_at","updated_at"):
            if d.get(k): d[k]=d[k].isoformat()
        docs.append(d)
    return docs

@router.get("/documents/{document_id}/download-url")
def download_url(document_id: str, user=Depends(current_user), db=Depends(db_dep)):
    try: oid=ObjectId(document_id)
    except Exception: raise HTTPException(status_code=404,detail="Document not found")
    d=db.application_documents.find_one({"_id":oid})
    app=db.applications.find_one({"_id":d["application_id"]}) if d else None
    if not d or not app or not app_access(app,user): raise HTTPException(status_code=404,detail="Document not found")
    if not d.get("storage_key"): raise HTTPException(status_code=409,detail="This is a physical document record; no file exists")
    provider=storage.provider_for_record(d)
    if provider in ("s3","cloudinary"):
        try: return {"url":storage.generate_download_url(d["storage_key"],provider=provider,
                    resource_type=d.get("storage_resource_type") or "raw"),"expires_in_seconds":300}
        except Exception as exc: raise HTTPException(status_code=503,detail="Private storage is unavailable") from exc
    return {"download_endpoint":f"/api/v1/documents/{document_id}/download","expires_in_seconds":0}

@router.get("/documents/{document_id}/download")
def download_document(document_id: str, user=Depends(current_user), db=Depends(db_dep)):
    try: oid=ObjectId(document_id)
    except Exception: raise HTTPException(status_code=404,detail="Document not found")
    d=db.application_documents.find_one({"_id":oid})
    app=db.applications.find_one({"_id":d["application_id"]}) if d else None
    if not d or not app or not app_access(app,user) or not d.get("storage_key"): raise HTTPException(status_code=404,detail="Document not found")
    provider=storage.provider_for_record(d)
    if provider=="cloudinary":
        try:
            signed_url=storage.generate_download_url(
                d["storage_key"],provider=provider,resource_type=d.get("storage_resource_type") or "raw"
            )
        except Exception as exc:
            raise HTTPException(status_code=503,detail="Private storage is unavailable") from exc
        audit(db,user["_id"],"document.downloaded","document",oid)
        return RedirectResponse(signed_url,status_code=307)
    try: data=storage.read_bytes(d["storage_key"],provider=provider)
    except FileNotFoundError: raise HTTPException(status_code=404,detail="Stored file not found")
    audit(db,user["_id"],"document.downloaded","document",oid)
    return Response(content=data,media_type=d.get("detected_content_type") or "application/octet-stream",
                    headers={"Content-Disposition":f"attachment; filename*=UTF-8''{quote(Path(d.get('original_filename','document')).name)}","X-Content-Type-Options":"nosniff"})

@router.post("/documents/{document_id}/review")
def review_document(document_id: str, payload: DocumentReviewRequest, user=Depends(current_user), db=Depends(db_dep)):
    if not can_review_documents(user): raise HTTPException(status_code=403,detail="Document review permission required")
    try: oid=ObjectId(document_id)
    except Exception: raise HTTPException(status_code=404,detail="Document not found")
    d=db.application_documents.find_one({"_id":oid})
    app=db.applications.find_one({"_id":d["application_id"]}) if d else None
    if not d or not app or not app_access(app,user): raise HTTPException(status_code=404,detail="Document not found")
    now=datetime.now(timezone.utc)
    db.application_documents.update_one({"_id":oid},{"$set":{"verification_status":payload.verification_status,"reviewer_comment":payload.reviewer_comment,"updated_at":now}})
    audit(db,user["_id"],"document.reviewed","document",oid,{"status":payload.verification_status})
    notify(db,str(d["customer_id"]),"document.reviewed","Document reviewed",f"Document review status: {payload.verification_status}",str(app["_id"]),f"{oid}:{payload.verification_status}:{now.timestamp()}")
    return {"message":"Document review updated"}

@router.post("/documents/{document_id}/replacement-request")
def replacement_request(document_id: str, payload: ReplacementRequest, user=Depends(current_user), db=Depends(db_dep)):
    if not can_review_documents(user): raise HTTPException(status_code=403,detail="Document review permission required")
    try: oid=ObjectId(document_id)
    except Exception: raise HTTPException(status_code=404,detail="Document not found")
    d=db.application_documents.find_one({"_id":oid})
    app=db.applications.find_one({"_id":d["application_id"]}) if d else None
    if not d or not app or not app_access(app,user): raise HTTPException(status_code=404,detail="Document not found")
    now=datetime.now(timezone.utc)
    db.application_documents.update_one({"_id":oid},{"$set":{"verification_status":"correction_requested","reviewer_comment":payload.reason,"updated_at":now}})
    notify(db,str(d["customer_id"]),"document.replacement_requested","Document correction requested",payload.reason,str(app["_id"]),f"{oid}:replacement:{now.timestamp()}")
    audit(db,user["_id"],"document.replacement_requested","document",oid)
    return {"message":"Replacement requested"}
