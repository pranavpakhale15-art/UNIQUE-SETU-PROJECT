from fastapi import APIRouter, HTTPException
from app.database.mongodb import ping
router = APIRouter()

@router.get("/health/live")
def live():
    return {"status": "alive"}

@router.get("/health/ready")
def ready():
    healthy = ping()
    if not healthy:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "database": "unavailable"})
    return {"status": "ready" if healthy else "not_ready", "database": "connected" if healthy else "unavailable"}
