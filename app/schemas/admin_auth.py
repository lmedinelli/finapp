from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=6, max_length=120)


class AdminLoginResponse(BaseModel):
    token: str
    username: str
    email: str | None = None
    role: Literal["admin", "user"] = "user"
    subscription_ends_at: datetime | None = None
    subscription_active: bool = False
    alerts_enabled: bool = False
    mobile_phone: str | None = None
    expires_at: datetime


class AdminLogoutResponse(BaseModel):
    status: str


class AdminUserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=120)
    email: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=6, max_length=120)
    role: Literal["admin", "user"] = "user"
    subscription_ends_at: datetime | None = None
    alerts_enabled: bool = False
    mobile_phone: str | None = Field(default=None, max_length=32)
    is_active: bool = True


class AdminUserUpdateRequest(BaseModel):
    email: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=6, max_length=120)
    role: Literal["admin", "user"] | None = None
    subscription_ends_at: datetime | None = None
    alerts_enabled: bool | None = None
    mobile_phone: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None


class AdminUserRead(BaseModel):
    id: int
    username: str
    email: str | None = None
    role: Literal["admin", "user"] = "user"
    subscription_ends_at: datetime | None = None
    alerts_enabled: bool = False
    mobile_phone: str | None = None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None = None
