import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ApplicableTo = Literal["all", "hotel", "tour", "flight"]
SyncStatus = Literal["not_synced", "synced", "failed", "disabled"]


class VoucherCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    discount_type: Literal["percentage", "fixed"] = "percentage"
    discount_value: float = Field(gt=0)
    maximum_discount_amount: float | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    min_order_value: float = Field(default=0, ge=0)
    budget: float | None = Field(default=None, gt=0)
    max_uses: int = Field(default=1, ge=1)
    valid_from: date
    valid_to: date
    status: Literal["active", "expired", "disabled"] = "active"
    guest_id: uuid.UUID | None = None
    description: str | None = None
    terms_and_conditions: str | None = None
    applicable_to: ApplicableTo = "all"


class VoucherUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    discount_type: Literal["percentage", "fixed"] | None = None
    discount_value: float | None = Field(None, gt=0)
    maximum_discount_amount: float | None = Field(None, gt=0)
    currency: str | None = Field(None, min_length=3, max_length=3)
    min_order_value: float | None = Field(None, ge=0)
    budget: float | None = Field(None, gt=0)
    max_uses: int | None = Field(None, ge=1)
    valid_from: date | None = None
    valid_to: date | None = None
    status: Literal["active", "expired", "disabled"] | None = None
    guest_id: uuid.UUID | None = None
    description: str | None = None
    terms_and_conditions: str | None = None
    applicable_to: ApplicableTo | None = None


class VoucherStatusUpdate(BaseModel):
    """Quick toggle endpoint mirroring LiteAPI PUT /vouchers/{id}/status."""

    status: Literal["active", "disabled"]


class VoucherResponse(BaseModel):
    id: uuid.UUID
    admin_id: uuid.UUID
    code: str
    name: str
    discount_type: str
    discount_value: float
    maximum_discount_amount: float | None = None
    currency: str
    min_order_value: float
    budget: float | None = None
    budget_used: float
    budget_remaining: float | None = None
    max_uses: int
    used_count: int
    valid_from: date
    valid_to: date
    status: str
    guest_id: uuid.UUID | None = None
    description: str | None = None
    terms_and_conditions: str | None = None
    applicable_to: str
    liteapi_voucher_id: str | None = None
    liteapi_sync_status: str
    liteapi_sync_error: str | None = None
    liteapi_synced_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="after")
    def _compute_budget_remaining(self):
        if self.budget is not None:
            self.budget_remaining = max(float(self.budget) - float(self.budget_used), 0.0)
        return self


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


class VoucherUsageDetail(BaseModel):
    """Enriched usage record for the admin usage-history dashboard."""

    id: uuid.UUID
    voucher_id: uuid.UUID
    voucher_code: str
    voucher_name: str
    user_id: uuid.UUID
    user_email: str
    user_full_name: str | None = None
    booking_id: uuid.UUID
    booking_status: str
    booking_total: float
    discount_amount: float
    used_at: datetime

    model_config = {"from_attributes": True}


class VoucherUsagesListMeta(BaseModel):
    total: int
    page: int
    per_page: int
    total_pages: int
    total_discount_amount: float


class VoucherUsagesListResponse(BaseModel):
    items: list[VoucherUsageDetail]
    meta: VoucherUsagesListMeta
