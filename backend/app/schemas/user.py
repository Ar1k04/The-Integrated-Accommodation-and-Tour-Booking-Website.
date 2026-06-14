import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=1024)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    role: Literal["user", "partner"] = "user"


class UserUpdate(BaseModel):
    """Admin-only update — may change role/is_active. NEVER bind to /auth/me."""

    full_name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = None
    avatar_url: str | None = None
    role: str | None = Field(None, pattern=r"^(user|partner|admin)$")
    is_active: bool | None = None
    preferred_locale: str | None = Field(None, pattern=r"^(en|vi)$")
    preferred_currency: str | None = Field(None, pattern=r"^(USD|VND)$")


class SelfProfileUpdate(BaseModel):
    """Fields a user may change on their own account via PATCH /auth/me.

    Deliberately excludes ``role`` and ``is_active`` — binding ``UserUpdate``
    here would let any user escalate themselves to admin (AUTHZ-01).
    """

    model_config = {"extra": "forbid"}

    full_name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = None
    avatar_url: str | None = None
    preferred_locale: str | None = Field(None, pattern=r"^(en|vi)$")
    preferred_currency: str | None = Field(None, pattern=r"^(USD|VND)$")


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None = None
    avatar_url: str | None = None
    role: str
    is_active: bool
    partner_status: str | None = None
    loyalty_points: int
    preferred_locale: str = "en"
    preferred_currency: str = "USD"
    # False for Google-only accounts; lets the client hide the change-password form.
    has_password: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    meta: dict


class PartnerStatusUpdate(BaseModel):
    partner_status: Literal["approved", "rejected", "pending"]
