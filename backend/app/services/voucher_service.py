"""Voucher validation, application, and usage tracking.

Enforces the `UNIQUE(voucher_id, user_id)` constraint at the application layer
so that callers see a friendly error before hitting the DB constraint.
"""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.booking import Booking
from app.models.voucher import Voucher, VoucherStatus
from app.models.voucher_usage import VoucherUsage


class VoucherError(ValueError):
    """Raised when a voucher cannot be validated or applied."""


async def validate_voucher(
    db: AsyncSession,
    code: str,
    user_id: uuid.UUID,
    subtotal: Decimal,
) -> Voucher:
    """Fetch the voucher, check it is usable by this user for this subtotal."""

    voucher = (
        await db.execute(select(Voucher).where(Voucher.code == code))
    ).scalar_one_or_none()
    if not voucher:
        raise VoucherError("Voucher not found")
    if voucher.status != VoucherStatus.active.value:
        raise VoucherError("Voucher is not active")

    today = date.today()
    if voucher.valid_from and voucher.valid_from > today:
        raise VoucherError("Voucher is not yet valid")
    if voucher.valid_to and voucher.valid_to < today:
        raise VoucherError("Voucher has expired")
    if voucher.used_count >= voucher.max_uses:
        raise VoucherError("Voucher usage limit reached")
    if subtotal < Decimal(str(voucher.min_order_value)):
        raise VoucherError(
            f"Order total must be at least {voucher.min_order_value}"
        )

    existing_usage = (
        await db.execute(
            select(VoucherUsage).where(
                and_(VoucherUsage.voucher_id == voucher.id, VoucherUsage.user_id == user_id)
            )
        )
    ).scalar_one_or_none()
    if existing_usage:
        raise VoucherError("You have already used this voucher")

    return voucher


def compute_discount(voucher: Voucher, subtotal: Decimal) -> Decimal:
    """Return the discount amount for the given subtotal. Never exceeds the subtotal."""

    if voucher.discount_type == "percentage":
        discount = subtotal * Decimal(str(voucher.discount_value)) / Decimal("100")
    else:
        discount = Decimal(str(voucher.discount_value))
    return min(discount, subtotal).quantize(Decimal("0.01"))


async def apply_voucher(
    db: AsyncSession,
    booking: Booking,
    voucher: Voucher,
    user_id: uuid.UUID,
) -> Decimal:
    """Record usage, bump used_count, attach voucher to booking. Returns discount amount."""

    discount = compute_discount(voucher, Decimal(str(booking.total_price)))
    usage = VoucherUsage(voucher_id=voucher.id, user_id=user_id, booking_id=booking.id)
    db.add(usage)
    voucher.used_count += 1
    booking.voucher_id = voucher.id
    booking.discount_amount = discount
    await db.flush()
    return discount
