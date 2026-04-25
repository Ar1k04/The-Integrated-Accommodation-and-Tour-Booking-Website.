import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    booking_id: uuid.UUID
    currency: str = "usd"


class VnpayCreateRequest(BaseModel):
    booking_id: uuid.UUID
    return_url: str


class PaymentResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID | None = None
    provider: str = "stripe"
    stripe_payment_intent_id: str | None = None
    vnpay_transaction_id: str | None = None
    amount: float
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
