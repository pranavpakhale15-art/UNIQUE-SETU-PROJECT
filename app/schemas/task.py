from pydantic import BaseModel, Field
from datetime import datetime

class TaskCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    application_id: str | None = None
    assigned_staff_id: str
    priority: str = "normal"
    due_date: datetime | None = None

class TaskPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    priority: str | None = None
    due_date: datetime | None = None
    status: str | None = None

class TaskComplete(BaseModel):
    completion_notes: str | None = Field(default=None, max_length=2000)
