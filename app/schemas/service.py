from pydantic import BaseModel, ConfigDict, Field
from typing import Any

class ServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_code: str = Field(min_length=2, max_length=40)
    name: dict[str, str]
    description: dict[str, str] = Field(default_factory=dict)
    category: str = Field(min_length=2, max_length=80)
    document_requirements: list[dict[str, Any]] = Field(default_factory=list)
    form_requirements: list[dict[str, Any]] = Field(default_factory=list)

class ServicePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_code: str | None = Field(default=None, min_length=2, max_length=40)
    name: dict[str, str] | None = None
    description: dict[str, str] | None = None
    category: str | None = Field(default=None, min_length=2, max_length=80)
    document_requirements: list[dict[str, Any]] | None = None
    form_requirements: list[dict[str, Any]] | None = None
    checklist_review_required: bool | None = None
