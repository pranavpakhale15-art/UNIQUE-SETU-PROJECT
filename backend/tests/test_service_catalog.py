import asyncio
import copy
from io import BytesIO
from types import SimpleNamespace

from bson import ObjectId
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
import pytest

from app.api.dependencies import current_user, db_dep, optional_user
from app.api.v1 import services
from app.core.config import settings
from app.main import app
from app.schemas.service import ServiceCreate, ServicePatch
from app.services.storage_service import StorageService


JPEG_CONTENT = bytes.fromhex("ffd8ffe000104a46494600010100000100010000ffd9")


class Cursor:
    def __init__(self, docs):
        self.docs = list(docs)

    def sort(self, key, direction=1):
        keys = key if isinstance(key, list) else [(key, direction)]
        for field, order in reversed(keys):
            self.docs.sort(key=lambda doc: value_at(doc, field) or "", reverse=order < 0)
        return self

    def skip(self, count):
        self.docs = self.docs[count:]
        return self

    def limit(self, count):
        self.docs = self.docs[:count]
        return self

    def __iter__(self):
        return iter(copy.deepcopy(self.docs))


def value_at(document, key):
    value = document
    for part in key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


class FakeCollection:
    def __init__(self, docs=()):
        self.docs = [copy.deepcopy(doc) for doc in docs]

    def matches(self, doc, query):
        for key, expected in query.items():
            if key == "$and":
                if not all(self.matches(doc, clause) for clause in expected):
                    return False
                continue
            if key == "$or":
                if not any(self.matches(doc, clause) for clause in expected):
                    return False
                continue
            actual = value_at(doc, key)
            if isinstance(expected, dict) and "$exists" in expected:
                if (actual is not None) != expected["$exists"]:
                    return False
            elif isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    def find_one(self, query):
        return copy.deepcopy(next((doc for doc in self.docs if self.matches(doc, query)), None))

    def find(self, query=None):
        query = query or {}
        return Cursor([doc for doc in self.docs if self.matches(doc, query)])

    def count_documents(self, query):
        return sum(self.matches(doc, query) for doc in self.docs)

    def insert_one(self, document):
        stored = copy.deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.docs.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    def update_one(self, query, update):
        for doc in self.docs:
            if not self.matches(doc, query):
                continue
            for key, value in update.get("$set", {}).items():
                target = doc
                parts = key.split(".")
                for part in parts[:-1]:
                    target = target.setdefault(part, {})
                target[parts[-1]] = copy.deepcopy(value)
            return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    def delete_one(self, query):
        for index, doc in enumerate(self.docs):
            if self.matches(doc, query):
                del self.docs[index]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    def delete_many(self, query):
        before = len(self.docs)
        self.docs = [doc for doc in self.docs if not self.matches(doc, query)]
        return SimpleNamespace(deleted_count=before - len(self.docs))


class FakeDatabase:
    def __init__(self, service_records=(), categories=()):
        self.services = FakeCollection(service_records)
        self.service_categories = FakeCollection(categories)
        self.service_versions = FakeCollection()
        self.applications = FakeCollection()
        self.audit_logs = FakeCollection()


def request(method, path, **kwargs):
    async def send():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, **kwargs)
    return asyncio.run(send())


def setup_api(monkeypatch, database, user, tmp_path):
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "local_storage_dir", str(tmp_path))
    monkeypatch.setattr(services, "storage", StorageService())
    app.dependency_overrides[db_dep] = lambda: database
    app.dependency_overrides[current_user] = lambda: user
    app.dependency_overrides[optional_user] = lambda: user


def teardown_api():
    app.dependency_overrides.clear()


def test_service_schemas_add_optional_catalog_fields_and_keep_legacy_patch():
    fields = ServiceCreate(
        service_code="TEST", name={"en": "Test"}, category="Legacy",
        customer_instructions={"en": "Bring originals"}, estimated_processing_time={"en": "10 days"},
        pricing={"amount": 100, "currency": "INR"}, display_order=5, is_featured=True,
    ).model_dump()
    assert fields["category"] == "Legacy"
    assert fields["display_order"] == 5
    assert fields["is_featured"] is True
    assert ServicePatch(category="Tax").model_dump(exclude_unset=True) == {"category": "Tax"}
    with pytest.raises(ValidationError):
        ServicePatch(display_order=-1)


def test_public_categories_admin_visibility_and_in_use_delete_protection(monkeypatch, tmp_path):
    admin_id = ObjectId()
    category_id = ObjectId()
    db = FakeDatabase(service_records=[{"_id": ObjectId(), "section_id": category_id}], categories=[{
        "_id": category_id, "slug": "tax", "name": {"en": "Tax"}, "description": {},
        "is_visible": True, "display_order": 2,
    }])
    setup_api(monkeypatch, db, {"_id": str(admin_id), "role": "admin"}, tmp_path)
    try:
        response = request("PATCH", f"/api/v1/services/categories/{category_id}", json={"is_visible": False, "display_order": 1})
        assert response.status_code == 200
        hidden = request("GET", "/api/v1/services/categories")
        admin_list = request("GET", "/api/v1/services/categories?include_hidden=true")
        delete = request("DELETE", f"/api/v1/services/categories/{category_id}")
    finally:
        teardown_api()

    assert hidden.status_code == 200 and hidden.json() == []
    assert admin_list.status_code == 200 and admin_list.json()[0]["display_order"] == 1
    assert delete.status_code == 409


def test_admin_can_create_category_and_reference_it_from_service(monkeypatch, tmp_path):
    admin_id = ObjectId()
    db = FakeDatabase()
    setup_api(monkeypatch, db, {"_id": str(admin_id), "role": "admin"}, tmp_path)
    try:
        category_response = request("POST", "/api/v1/services/categories", json={
            "slug": "business", "name": {"en": "Business"}, "description": {},
            "is_visible": True, "display_order": 3,
        })
        category_id = category_response.json()["id"]
        service_response = request("POST", "/api/v1/services", json={
            "service_code": "BIZ-1", "name": {"en": "Business service"}, "category": "Legacy category",
            "section_id": category_id, "document_requirements": [{"id": "identity"}],
        })
    finally:
        teardown_api()

    assert category_response.status_code == 201
    assert service_response.status_code == 201
    assert db.services.docs[0]["category"] == "Legacy category"
    assert db.services.docs[0]["section_id"] == ObjectId(category_id)


def test_service_list_orders_by_display_order_and_keeps_legacy_category_filter(monkeypatch, tmp_path):
    db = FakeDatabase(service_records=[
        {"_id": ObjectId(), "service_code": "LATE", "name": {"mr": "ब"}, "category": "Legacy", "display_order": 9, "is_published": True},
        {"_id": ObjectId(), "service_code": "EARLY", "name": {"mr": "अ"}, "category": "Legacy", "display_order": 2, "is_published": True},
        {"_id": ObjectId(), "service_code": "OTHER", "name": {"mr": "क"}, "category": "Other", "display_order": 0, "is_published": True},
    ])
    setup_api(monkeypatch, db, None, tmp_path)
    try:
        response = request("GET", "/api/v1/services?category=Legacy")
    finally:
        teardown_api()

    assert response.status_code == 200
    assert [item["service_code"] for item in response.json()["items"]] == ["EARLY", "LATE"]


def test_public_service_list_and_detail_hide_services_in_hidden_sections(monkeypatch, tmp_path):
    visible_id = ObjectId()
    hidden_id = ObjectId()
    visible_service = {"_id": ObjectId(), "service_code": "VISIBLE", "name": {"mr": "सेवा"}, "category": "Legacy", "section_id": visible_id, "is_published": True}
    hidden_service = {"_id": ObjectId(), "service_code": "HIDDEN", "name": {"mr": "लपलेली"}, "category": "Legacy", "section_id": hidden_id, "is_published": True}
    db = FakeDatabase(service_records=[visible_service, hidden_service], categories=[
        {"_id": visible_id, "slug": "visible", "name": {"en": "Visible"}, "is_visible": True, "display_order": 0},
        {"_id": hidden_id, "slug": "hidden", "name": {"en": "Hidden"}, "is_visible": False, "display_order": 1},
    ])
    setup_api(monkeypatch, db, None, tmp_path)
    try:
        listed = request("GET", "/api/v1/services")
        detail = request("GET", f"/api/v1/services/{hidden_service['_id']}")
    finally:
        teardown_api()

    assert listed.status_code == 200
    assert [item["service_code"] for item in listed.json()["items"]] == ["VISIBLE"]
    assert detail.status_code == 404


def test_thumbnail_upload_is_private_image_only_and_public_read_requires_publish(monkeypatch, tmp_path):
    admin_id = ObjectId()
    service_id = ObjectId()
    db = FakeDatabase(service_records=[{
        "_id": service_id, "service_code": "TEST", "name": {"en": "Test"}, "category": "Legacy",
        "document_requirements": [{"id": "identity"}], "version": 1, "is_published": False,
    }])
    setup_api(monkeypatch, db, {"_id": str(admin_id), "role": "admin"}, tmp_path)
    try:
        invalid = request("PUT", f"/api/v1/services/{service_id}/thumbnail", files={
            "file": ("thumbnail.pdf", JPEG_CONTENT, "application/pdf"),
        })
        uploaded = request("PUT", f"/api/v1/services/{service_id}/thumbnail", files={
            "file": ("thumbnail.jpg", JPEG_CONTENT, "image/jpeg"),
        })
        admin_preview = request("GET", f"/api/v1/services/{service_id}/thumbnail")
        service_response = request("GET", f"/api/v1/services/{service_id}")
        db.services.update_one({"_id": service_id}, {"$set": {"is_published": True}})
        app.dependency_overrides[current_user] = lambda: None
        app.dependency_overrides[optional_user] = lambda: None
        public_preview = request("GET", f"/api/v1/services/{service_id}/thumbnail")
        db.services.update_one({"_id": service_id}, {"$set": {"is_published": False}})
        private_preview = request("GET", f"/api/v1/services/{service_id}/thumbnail")
    finally:
        teardown_api()

    assert invalid.status_code == 422
    assert uploaded.status_code == 200
    assert "storage_key" not in uploaded.text and "storage_provider" not in uploaded.text
    assert admin_preview.status_code == 200 and admin_preview.content == JPEG_CONTENT
    assert service_response.status_code == 200
    assert "storage_key" not in service_response.text and "storage_provider" not in service_response.text
    assert public_preview.status_code == 200 and public_preview.content == JPEG_CONTENT
    assert private_preview.status_code == 404
    assert db.services.find_one({"_id": service_id})["thumbnail"]["storage_key"].startswith("service-thumbnails/")


def test_thumbnail_upload_requires_admin(monkeypatch, tmp_path):
    service_id = ObjectId()
    db = FakeDatabase(service_records=[{"_id": service_id, "is_published": False}])
    setup_api(monkeypatch, db, {"_id": str(ObjectId()), "role": "customer"}, tmp_path)
    try:
        response = request("PUT", f"/api/v1/services/{service_id}/thumbnail", files={
            "file": ("thumbnail.jpg", JPEG_CONTENT, "image/jpeg"),
        })
    finally:
        teardown_api()
    assert response.status_code == 403


def test_s3_thumbnail_storage_uses_private_namespaced_objects(monkeypatch):
    class FakeS3:
        def __init__(self):
            self.put_request = None

        def put_object(self, **kwargs):
            self.put_request = kwargs

        def get_object(self, **kwargs):
            return {"Body": BytesIO(JPEG_CONTENT)}

    monkeypatch.setattr(settings, "storage_provider", "s3")
    monkeypatch.setattr(settings, "storage_bucket", "private-test-bucket")
    client = FakeS3()
    storage = StorageService(s3_client=client)

    key, size = storage.save_bytes(
        JPEG_CONTENT, "thumbnail.jpg", "image/jpeg", resource_type="image", folder="service-thumbnails"
    )

    assert key.startswith("service-thumbnails/")
    assert size == len(JPEG_CONTENT)
    assert client.put_request["Bucket"] == "private-test-bucket"
    assert client.put_request["ContentType"] == "image/jpeg"
    assert "ACL" not in client.put_request
    assert storage.read_bytes(key, provider="s3") == JPEG_CONTENT


def test_cloudinary_thumbnail_storage_and_retrieval_are_authenticated(monkeypatch):
    class FakeCloudinary:
        def __init__(self):
            self.upload_request = None

        def upload(self, content, **kwargs):
            self.upload_request = (content.read(), kwargs)
            return {"public_id": kwargs["public_id"]}

    class FakeSigner:
        def __init__(self):
            self.sign_request = None

        def private_download_url(self, public_id, file_format, **kwargs):
            self.sign_request = (public_id, file_format, kwargs)
            return "https://cloudinary.example/temporary-signed-url"

    monkeypatch.setattr(settings, "storage_provider", "cloudinary")
    monkeypatch.setattr(settings, "cloudinary_cloud_name", "test-cloud")
    monkeypatch.setattr(settings, "cloudinary_api_key", "test-key")
    monkeypatch.setattr(settings, "cloudinary_api_secret", "test-secret")
    api = FakeCloudinary()
    signer = FakeSigner()
    storage = StorageService(cloudinary_api=api, cloudinary_signer=signer)

    key, _ = storage.save_bytes(
        JPEG_CONTENT, "thumbnail.jpg", "image/jpeg", resource_type="image", folder="service-thumbnails"
    )
    signed_url = storage.generate_download_url(
        key, provider="cloudinary", resource_type="image", file_format="jpg", attachment=False,
        expires_in_seconds=300,
    )

    assert key.startswith("service-thumbnails/")
    assert api.upload_request[1]["type"] == "authenticated"
    assert api.upload_request[1]["resource_type"] == "image"
    assert "test-secret" not in signed_url
    assert signer.sign_request[1] == "jpg"
    assert signer.sign_request[2]["type"] == "authenticated"
    assert signer.sign_request[2]["attachment"] is False
