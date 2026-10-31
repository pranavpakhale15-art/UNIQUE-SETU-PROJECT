import asyncio
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import current_user, db_dep
from app.api.v1.documents import can_review_documents
from app.api.v1.tasks import can_manage_task
from app.core.security import create_token
from app.main import app


class FakeCollection:
    def __init__(self, documents=()):
        self.documents = list(documents)

    def find_one(self, query):
        for document in self.documents:
            matches = True
            for key, expected in query.items():
                actual = document.get(key)
                if isinstance(expected, dict) and "$gt" in expected:
                    if actual is None or actual <= expected["$gt"]:
                        matches = False
                        break
                elif actual != expected:
                    matches = False
                    break
            if matches:
                return document.copy()
        return None


class FakeDatabase:
    def __init__(self, applications=(), users=(), sessions=(), services=()):
        self.applications = FakeCollection(applications)
        self.users = FakeCollection(users)
        self.sessions = FakeCollection(sessions)
        self.services = FakeCollection(services)


def request(app_client, method, path, **kwargs):
    async def send():
        async with AsyncClient(transport=ASGITransport(app=app_client), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(send())


def test_customer_cannot_read_another_customers_application():
    application_id = ObjectId()
    owner_id = ObjectId()
    database = FakeDatabase(applications=[{"_id": application_id, "customer_id": owner_id,
        "service_id": ObjectId(), "service_version": 1, "checklist_snapshot": [], "status": "Draft",
        "application_number": "USK-TEST", "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc), "internal_notes": "private"}])
    app.dependency_overrides[db_dep] = lambda: database
    app.dependency_overrides[current_user] = lambda: {"_id": str(ObjectId()), "role": "customer"}
    try:
        response = request(app, "GET", f"/api/v1/applications/{application_id}")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


def test_staff_cannot_update_owner_application_fields():
    app.dependency_overrides[current_user] = lambda: {"_id": str(ObjectId()), "role": "staff"}
    try:
        response = request(app, "PATCH", f"/api/v1/applications/{ObjectId()}/owner-fields",
                           json={"priority": "urgent"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 403


def test_staff_permissions_are_read_only_even_with_custom_permissions():
    staff_user = {
        "_id": str(ObjectId()),
        "role": "staff",
        "permissions_customized": True,
        "permissions": [
            "applications:update:assigned",
            "documents:review:assigned",
            "tasks:manage:assigned",
        ],
    }

    assert not can_review_documents(staff_user)
    assert not can_manage_task({"assigned_staff_id": ObjectId(staff_user["_id"])}, staff_user)


def test_suspended_user_is_blocked_by_current_user_dependency():
    user_id = ObjectId()
    session_id = ObjectId()
    now = datetime.now(timezone.utc)
    database = FakeDatabase(
        users=[{"_id": user_id, "account_status": "suspended", "role": "customer"}],
        sessions=[{"_id": session_id, "user_id": user_id, "revoked": False,
                   "expires_at": now + timedelta(hours=1)}],
    )
    app.dependency_overrides[db_dep] = lambda: database
    token = create_token(str(user_id), "access", timedelta(minutes=2), session_id=str(session_id))
    try:
        response = request(app, "GET", "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401
