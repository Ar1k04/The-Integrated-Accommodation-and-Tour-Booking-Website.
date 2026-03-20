import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PromoCodeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    discount_percent: float = Field(gt=0, le=100)
    max_uses: int = Field(default=100, ge=1)
    min_booking_amount: float = Field(default=0, ge=0)
    expires_at: datetime | None = None


class PromoCodeUpdate(BaseModel):
    discount_percent: float | None = Field(None, gt=0, le=100)
    max_uses: int | None = Field(None, ge=1)
    min_booking_amount: float | None = Field(None, ge=0)
    is_active: bool | None = None
    expires_at: datetime | None = None


class PromoCodeResponse(BaseModel):
    id: uuid.UUID
    code: str
    discount_percent: float
    max_uses: int
    current_uses: int
    min_booking_amount: float
    is_active: bool
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PromoCodeValidateResponse(BaseModel):
    valid: bool
    discount_percent: float = 0
    message: str = ""
