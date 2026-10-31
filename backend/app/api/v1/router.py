from fastapi import APIRouter
from app.api.v1 import auth, services, applications, documents, tasks, notifications, owner, admin, health

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["authentication"])
router.include_router(services.router, prefix="/services", tags=["services"])
router.include_router(applications.router, prefix="/applications", tags=["applications"])
router.include_router(documents.router, tags=["documents"])
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
router.include_router(owner.router, prefix="/owner", tags=["owner"])
router.include_router(admin.router, prefix="/admin", tags=["admin"])
