from pydantic import BaseModel, Field
from typing import Literal


class UploadUrlRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str
    file_size: int = Field(gt=0)
    checklist_item_id: str = Field(min_length=1, max_length=120)
    replace_document_id: str | None = None


class ConfirmUploadRequest(BaseModel):
    upload_id: str


class PhysicalDocumentReceiptRequest(BaseModel):
    checklist_item_id: str = Field(min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=1000)


class DocumentReviewRequest(BaseModel):
    verification_status: Literal["verified", "rejected", "correction_requested"]
    reviewer_comment: str | None = Field(default=None, max_length=2000)


class ReplacementRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
