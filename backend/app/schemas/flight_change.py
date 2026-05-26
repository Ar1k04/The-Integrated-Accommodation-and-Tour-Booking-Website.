"""Pydantic schemas for the Duffel order-change 3-step flow."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NewSlice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: str = Field(min_length=3, max_length=3)
    destination: str = Field(min_length=3, max_length=3)
    departure_date: date
    cabin_class: Literal["economy", "premium_economy", "business", "first"] | None = None

    @field_validator("origin", "destination")
    @classmethod
    def _iata_upper(cls, v: str) -> str:
        return v.upper()


class OrderChangeRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slices_remove: list[str] = Field(min_length=1)
    slices_add: list[NewSlice] = Field(min_length=1)
    private_fares: dict | None = None


class OrderChangeConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Required only when change_total_amount > 0 — backend enforces.
    payment_intent_id: str | None = Field(default=None, max_length=255)


class ChangeOfferOut(BaseModel):
    id: str
    order_change_request_id: str | None = None
    change_total_amount: float | None = None
    change_total_currency: str | None = None
    new_total_amount: float | None = None
    new_total_currency: str | None = None
    penalty_total_amount: float | None = None
    penalty_total_currency: str | None = None
    refund_to: str | None = None
    expires_at: str | None = None
    slices_add: list[dict] = []
    slices_remove: list[dict] = []
    conditions: dict = {}


class OrderChangeOut(BaseModel):
    id: str
    status: str | None = None
    change_total_amount: float | None = None
    change_total_currency: str | None = None
    new_total_amount: float | None = None
    refund_to: str | None = None
    confirmed_at: str | None = None
