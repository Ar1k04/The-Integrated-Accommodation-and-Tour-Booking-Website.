import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=1024)
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    role: str = Field(default="user", pattern=r"^(user|partner|admin)$")


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=255)
    phone: str | None = None
    avatar_url: str | None = None
    role: str | None = Field(None, pattern=r"^(user|partner|admin)$")
    is_active: bool | None = None
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
    loyalty_points: int
    preferred_locale: str = "en"
    preferred_currency: str = "USD"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    items: list[UserResponse]
    meta: dict
