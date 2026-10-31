from pydantic import BaseModel, ConfigDict, Field
from typing import Any
from datetime import datetime
from typing import Literal

LocalizedText = dict[str, str]

class ServiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_code: str = Field(min_length=2, max_length=40)
    name: dict[str, str]
    description: dict[str, str] = Field(default_factory=dict)
    category: str = Field(min_length=2, max_length=80)
    section_id: str | None = Field(default=None, min_length=24, max_length=24)
    customer_instructions: LocalizedText | str = Field(default_factory=dict)
    estimated_processing_time: LocalizedText | str | None = None
    pricing: int | float | str | dict[str, Any] | None = None
    display_order: int = Field(default=0, ge=0)
    is_featured: bool = False
    thumbnail_alt_text: LocalizedText | str = Field(default_factory=dict)
    document_requirements: list[dict[str, Any]] = Field(default_factory=list)
    form_requirements: list[dict[str, Any]] = Field(default_factory=list)

class ServicePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_code: str | None = Field(default=None, min_length=2, max_length=40)
    name: dict[str, str] | None = None
    description: dict[str, str] | None = None
    category: str | None = Field(default=None, min_length=2, max_length=80)
    section_id: str | None = Field(default=None, min_length=24, max_length=24)
    customer_instructions: LocalizedText | str | None = None
    estimated_processing_time: LocalizedText | str | None = None
    pricing: int | float | str | dict[str, Any] | None = None
    display_order: int | None = Field(default=None, ge=0)
    is_featured: bool | None = None
    thumbnail_alt_text: LocalizedText | str | None = None
    document_requirements: list[dict[str, Any]] | None = None
    form_requirements: list[dict[str, Any]] | None = None
    checklist_review_required: bool | None = None


class ServiceCategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: LocalizedText
    description: LocalizedText = Field(default_factory=dict)
    is_visible: bool = True
    display_order: int = Field(default=0, ge=0)


class ServiceCategoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str | None = Field(default=None, min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: LocalizedText | None = None
    description: LocalizedText | None = None
    is_visible: bool | None = None
    display_order: int | None = Field(default=None, ge=0)


class ServiceThumbnailMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_filename: str
    detected_content_type: Literal["image/jpeg", "image/png"]
    file_size: int = Field(gt=0)
    updated_at: datetime | None = None
    alt_text: LocalizedText | str = Field(default_factory=dict)
