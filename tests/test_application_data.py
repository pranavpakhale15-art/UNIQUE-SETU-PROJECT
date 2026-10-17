from datetime import datetime, timezone

import pytest
from bson import ObjectId
from fastapi import HTTPException

from app.api.v1.applications import change_status, patch_application
from app.schemas.application import ApplicationPatch, StatusChange


class FakeApplications:
    def __init__(self, application):
        self.application = application
        self.update = None

    def find_one(self, query):
        return self.application

    def update_one(self, query, update):
        self.update = update


class FakeDatabase:
    def __init__(self, application):
        self.applications = FakeApplications(application)


def customer_app():
    customer_id = ObjectId()
    application_id = ObjectId()
    return {
        "_id": application_id,
        "customer_id": customer_id,
        "status": "Draft",
        "form_requirements_snapshot": [{"id": "phone", "required": True}],
        "application_data": {},
    }, {"_id": str(customer_id), "role": "customer"}


def test_customer_can_save_only_declared_application_fields():
    application, user = customer_app()
    database = FakeDatabase(application)

    patch_application(
        str(application["_id"]),
        ApplicationPatch(application_data={"phone": "8149921445"}),
        user,
        database,
    )

    assert database.applications.update["$set"]["application_data"] == {"phone": "8149921445"}

    with pytest.raises(HTTPException) as error:
        patch_application(
            str(application["_id"]),
            ApplicationPatch(application_data={"unknown": "value"}),
            user,
            database,
        )
    assert error.value.status_code == 422


def test_customer_cannot_submit_without_required_application_details():
    application, user = customer_app()

    with pytest.raises(HTTPException) as error:
        change_status(
            str(application["_id"]),
            StatusChange(status="Submitted by Customer"),
            user,
            FakeDatabase(application),
        )

    assert error.value.status_code == 409
    assert error.value.detail["missing_form_field_ids"] == ["phone"]
