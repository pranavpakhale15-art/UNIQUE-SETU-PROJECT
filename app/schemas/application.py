from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from typing import Any

class ApplicationCreate(BaseModel):
    service_id: str
    customer_notes: str | None = Field(default=None, max_length=3000)

class ApplicationPatch(BaseModel):
    customer_notes: str | None = Field(default=None, max_length=3000)
    application_data: dict[str, str] | None = None

class StatusChange(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=1000)

class AssignRequest(BaseModel):
    staff_id: str

class CommentCreate(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    visibility: str = "customer"

class CustomerApplicationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(alias="_id")
    application_number: str
    service_id: str
    service_version: int
    checklist_snapshot: list[dict[str, Any]]
    form_requirements_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    application_data: dict[str, str] = Field(default_factory=dict)
    status: str
    customer_notes: str | None = None
    created_at: str
    updated_at: str
    completed_at: str | None = None
    service: dict[str, Any] | None = None

class OwnerApplicationFields(BaseModel):
    priority: Literal["low", "normal", "high", "urgent"] | None = None
    internal_due_date: datetime | None = None
    internal_notes: str | None = Field(default=None, max_length=5000)
