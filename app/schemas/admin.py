from typing import Literal

from pydantic import BaseModel, Field


class AdminUserStatusChange(BaseModel):
    account_status: Literal["active", "suspended", "disabled"]


class AdminRoleChange(BaseModel):
    role: Literal["customer", "staff", "owner", "admin"]


class AdminPermissionsChange(BaseModel):
    permissions: list[str] = Field(max_length=100)


class TranslationUpdate(BaseModel):
    translations: dict[Literal["mr", "en", "hi"], str]


class SystemSettingsUpdate(BaseModel):
    business_name: str | None = Field(default=None, min_length=2, max_length=160)
    business_address: str | None = Field(default=None, max_length=500)
    support_phone: str | None = Field(default=None, max_length=24)
    default_language: Literal["mr", "en", "hi"] | None = None
    maintenance_mode: bool | None = None


class StaffCreateRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    mobile_number: str = Field(min_length=10, max_length=16)
    password: str = Field(min_length=10, max_length=128)