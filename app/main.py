import asyncio
from contextlib import asynccontextmanager
import logging, time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.logging import configure_logging
from app.database.mongodb import connect, close, get_db
from app.database.indexes import create_indexes
from app.api.v1.router import router
from app.services.retention_service import cleanup_expired_completed_work

configure_logging()
logger=logging.getLogger(__name__)

async def completed_work_retention_worker():
    while True:
        try:
            result = await asyncio.to_thread(cleanup_expired_completed_work, get_db())
            logger.info("Completed-work retention run finished: %s", result)
        except Exception:
            logger.exception("Completed-work retention run failed")
        await asyncio.sleep(60 * 60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        db=connect()
        create_indexes(db)
        logger.info("MongoDB connected and indexes ensured")
    except Exception:
        logger.exception("Database startup failed")
        close()
        raise
    retention_worker = asyncio.create_task(completed_work_retention_worker())
    try:
        yield
    finally:
        retention_worker.cancel()
        try:
            await retention_worker
        except asyncio.CancelledError:
            pass
        close()

app=FastAPI(title=settings.app_name,version="1.0.0",description="Independent API for Unique Solutions and Setu Kendra",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins,allow_credentials=True,
                   allow_methods=["GET","POST","PATCH","PUT","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type","X-Request-ID","X-CSRF-Token"])
@app.middleware("http")
async def security_and_request_id(request:Request,call_next):
    start=time.time()
    request_id=request.headers.get("X-Request-ID") or __import__("uuid").uuid4().hex
    try:
        response=await call_next(request)
    except Exception:
        logger.exception("Unhandled exception request_id=%s path=%s",request_id,request.url.path)
        response=JSONResponse(status_code=500,content={"detail":"Internal server error","request_id":request_id})
    response.headers["X-Request-ID"]=request_id
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    if settings.app_env.lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"]="no-store"
    logger.info("request_id=%s method=%s path=%s status=%s duration_ms=%s",request_id,request.method,request.url.path,response.status_code,round((time.time()-start)*1000))
    return response
app.include_router(router,prefix=settings.api_v1_prefix)

@app.get("/")
def root():
    return {"name":settings.app_name,"version":"1.0.0","docs":"/docs","health":f"{settings.api_v1_prefix}/health/live"}
