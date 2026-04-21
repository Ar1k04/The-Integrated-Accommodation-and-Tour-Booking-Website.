import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class VoucherCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    discount_type: Literal["percentage", "fixed"] = "percentage"
    discount_value: float = Field(gt=0)
    min_order_value: float = Field(default=0, ge=0)
    max_uses: int = Field(default=1, ge=1)
    valid_from: date
    valid_to: date
    status: Literal["active", "expired", "disabled"] = "active"


class VoucherUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    discount_type: Literal["percentage", "fixed"] | None = None
    discount_value: float | None = Field(None, gt=0)
    min_order_value: float | None = Field(None, ge=0)
    max_uses: int | None = Field(None, ge=1)
    valid_from: date | None = None
    valid_to: date | None = None
    status: Literal["active", "expired", "disabled"] | None = None


class VoucherResponse(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID
    code: str
    name: str
    discount_type: str
    discount_value: float
    min_order_value: float
    max_uses: int
    used_count: int
    valid_from: date
    valid_to: date
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VoucherValidateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    subtotal: float = Field(ge=0)


class VoucherValidateResponse(BaseModel):
    valid: bool
    code: str | None = None
    discount_type: str | None = None
    discount_value: float = 0
    discount_amount: float = 0
    message: str = ""


class VoucherUsageResponse(BaseModel):
    id: uuid.UUID
    voucher_id: uuid.UUID
    user_id: uuid.UUID
    booking_id: uuid.UUID
    used_at: datetime

    model_config = {"from_attributes": True}
