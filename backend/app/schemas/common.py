from pydantic import BaseModel, Field, ConfigDict
from typing import Any

class MessageResponse(BaseModel):
    message: str

class PageResponse(BaseModel):
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int
    pages: int
