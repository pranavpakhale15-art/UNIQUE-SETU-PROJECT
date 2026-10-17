from typing import Literal

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from app.utils.identifiers import normalize_indian_mobile

class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    mobile_number: str = Field(min_length=10, max_length=16)
    password: str = Field(min_length=10, max_length=128)
    email: str | None = Field(default=None, max_length=254)
    preferred_language: str = "mr"

    @field_validator("mobile_number")
    @classmethod
    def valid_mobile(cls, v):
        return normalize_indian_mobile(v)

    @field_validator("password")
    @classmethod
    def strong_password(cls, v):
        if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one letter and one number")
        return v

class LoginRequest(BaseModel):
    mobile_number: str
    password: str
    account_type: Literal["customer", "staff", "owner", "admin"] | None = None

class RefreshRequest(BaseModel):
    refresh_token: str | None = None

class ForgotPasswordRequest(BaseModel):
    mobile_number: str

class ResetPasswordRequest(BaseModel):
    reset_token: str
    new_password: str = Field(min_length=10, max_length=128)


class ProfilePhotoResponse(BaseModel):
    original_filename: str
    detected_content_type: Literal["image/jpeg", "image/png"]
    file_size: int
    updated_at: datetime
