import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PaymentCreate(BaseModel):
    booking_id: uuid.UUID
    currency: str = "usd"


class PaymentResponse(BaseModel):
    id: uuid.UUID
    booking_id: uuid.UUID | None = None
    provider: str = "stripe"
    stripe_payment_intent_id: str | None = None
    stripe_refund_id: str | None = None
    amount: float
    refunded_amount: float = 0
    currency: str
    status: str
    failure_code: str | None = None
    decline_code: str | None = None
    failure_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
