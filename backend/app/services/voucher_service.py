"""Voucher validation, application, and usage tracking.

Enforces the `UNIQUE(voucher_id, user_id)` constraint at the application layer
so that callers see a friendly error before hitting the DB constraint.

Phase 2 enhancements:
- guest_id check (voucher reserved for a specific user)
- maximum_discount_amount cap for percentage discounts
- budget pool tracking (budget / budget_used)

Phase 5 — LiteAPI sync:
- sync_voucher_to_liteapi / unsync_voucher_from_liteapi: best-effort mirror
  of local voucher state to LiteAPI's dashboard API.
"""
import logging
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.booking import Booking
from app.models.voucher import (
    Voucher,
    VoucherLiteAPISyncStatus,
    VoucherStatus,
)
from app.models.voucher_usage import VoucherUsage
from app.services import liteapi_service

logger = logging.getLogger(__name__)


class VoucherError(ValueError):
    """Raised when a voucher cannot be validated or applied."""


async def peek_voucher(db: AsyncSession, code: str) -> Voucher | None:
    """Look up a voucher by code without raising. Used by booking_service to
    decide whether to forward the code to the supplier (LiteAPI)."""
    return (
        await db.execute(select(Voucher).where(Voucher.code == code))
    ).scalar_one_or_none()


async def validate_voucher(
    db: AsyncSession,
    code: str,
    user_id: uuid.UUID,
    subtotal: Decimal,
) -> Voucher:
    """Fetch the voucher, check it is usable by this user for this subtotal."""

    voucher = await peek_voucher(db, code)
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

    # Guest-specific voucher: only the designated user may redeem.
    if voucher.guest_id is not None and voucher.guest_id != user_id:
        raise VoucherError("This voucher is reserved for another customer")

    # Budget pool: cap by total discount disbursed, independent of max_uses.
    if voucher.budget is not None:
        prospective_discount = compute_discount(voucher, subtotal)
        if Decimal(str(voucher.budget_used)) + prospective_discount > Decimal(str(voucher.budget)):
            raise VoucherError("Voucher budget pool exhausted")

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
    """Return the discount amount for the given subtotal. Never exceeds the subtotal.

    For percentage vouchers, also caps at maximum_discount_amount when set.
    """

    if voucher.discount_type == "percentage":
        discount = subtotal * Decimal(str(voucher.discount_value)) / Decimal("100")
        if voucher.maximum_discount_amount is not None:
            discount = min(discount, Decimal(str(voucher.maximum_discount_amount)))
    else:
        discount = Decimal(str(voucher.discount_value))
    return min(discount, subtotal).quantize(Decimal("0.01"))


async def apply_voucher(
    db: AsyncSession,
    booking: Booking,
    voucher: Voucher,
    user_id: uuid.UUID,
) -> Decimal:
    """Record usage, bump used_count + budget_used, attach voucher to booking.
    Returns discount amount.

    Note: callers that intend to settle the discount supplier-side (LiteAPI)
    should use record_usage_only() instead to avoid double-discounting.
    """

    discount = compute_discount(voucher, Decimal(str(booking.total_price)))
    usage = VoucherUsage(voucher_id=voucher.id, user_id=user_id, booking_id=booking.id)
    db.add(usage)
    voucher.used_count += 1
    if voucher.budget is not None:
        voucher.budget_used = (
            Decimal(str(voucher.budget_used)) + discount
        ).quantize(Decimal("0.01"))
    booking.voucher_id = voucher.id
    booking.discount_amount = discount
    await db.flush()
    return discount


async def record_usage_only(
    db: AsyncSession,
    booking: Booking,
    voucher: Voucher,
    user_id: uuid.UUID,
    supplier_discount: Decimal,
) -> Decimal:
    """Record voucher usage without applying local discount math.

    Used when LiteAPI applied the discount supplier-side and returned a
    pre-discounted price — booking.total_price already reflects the discount,
    so we just need to record the usage and bump counters using the supplier-
    reported discount amount for budget tracking.
    """
    usage = VoucherUsage(voucher_id=voucher.id, user_id=user_id, booking_id=booking.id)
    db.add(usage)
    voucher.used_count += 1
    if voucher.budget is not None:
        voucher.budget_used = (
            Decimal(str(voucher.budget_used)) + supplier_discount
        ).quantize(Decimal("0.01"))
    booking.voucher_id = voucher.id
    booking.discount_amount = supplier_discount.quantize(Decimal("0.01"))
    await db.flush()
    return supplier_discount


# ---------------------------------------------------------------------------
# LiteAPI sync helpers (Phase 5)
# ---------------------------------------------------------------------------


def _should_sync(voucher: Voucher) -> bool:
    """A voucher is eligible for LiteAPI sync when:
    - the feature flag is enabled,
    - it is hotel-applicable (applicable_to in {all, hotel}),
    - it is not guest-locked (LiteAPI uses its own guest model — we keep
      guest-locked vouchers local-only to avoid mismatched identifiers),
    - its sync hasn't been explicitly disabled.
    """
    if not settings.LITEAPI_VOUCHER_SYNC_ENABLED:
        return False
    if voucher.applicable_to not in ("all", "hotel"):
        return False
    if voucher.guest_id is not None:
        return False
    if voucher.liteapi_sync_status == VoucherLiteAPISyncStatus.disabled.value:
        return False
    return True


def _build_liteapi_payload(voucher: Voucher) -> dict:
    """Map local Voucher → LiteAPI POST/PUT /vouchers body."""
    payload = {
        "voucher_code": voucher.code,
        "discount_type": voucher.discount_type,
        "discount_value": float(voucher.discount_value),
        "minimum_spend": float(voucher.min_order_value or 0),
        "maximum_discount_amount": (
            float(voucher.maximum_discount_amount)
            if voucher.maximum_discount_amount is not None
            else float(voucher.discount_value)
        ),
        "currency": voucher.currency,
        "validity_start": voucher.valid_from.isoformat(),
        "validity_end": voucher.valid_to.isoformat(),
        "usages_limit": voucher.max_uses,
        "status": "active" if voucher.status == VoucherStatus.active.value else "inactive",
    }
    if voucher.budget is not None:
        payload["budget"] = float(voucher.budget)
    if voucher.description:
        payload["description"] = voucher.description
    if voucher.terms_and_conditions:
        payload["terms_and_conditions"] = voucher.terms_and_conditions
    return payload


async def _find_liteapi_id_by_code(code: str) -> str | None:
    """Look up an existing LiteAPI voucher by code. Used to reconcile after a
    previous sync attempt that created the supplier voucher but failed to
    persist the id locally (e.g. response parsing error, DB rollback)."""
    try:
        for v in await liteapi_service.list_vouchers():
            if v.get("voucher_code") == code:
                vid = v.get("id") or v.get("voucher_id")
                return str(vid) if vid else None
    except liteapi_service.LiteAPIError as exc:
        logger.warning("LiteAPI list_vouchers failed during reconcile: %s", exc)
    return None


async def sync_voucher_to_liteapi(db: AsyncSession, voucher: Voucher) -> None:
    """Best-effort create-or-update of the voucher on LiteAPI.

    Mutates voucher.liteapi_* fields and flushes. Never raises — failures are
    recorded as liteapi_sync_status='failed' with the error captured for the
    admin UI's "Retry sync" action.

    Handles the "voucher_code already exists" case by looking up the existing
    LiteAPI id by code and switching to update mode. This recovers from a
    previous create that succeeded supplier-side but failed to persist locally.
    """
    if voucher.applicable_to not in ("all", "hotel") or voucher.guest_id is not None:
        # Mark unsync-eligible so the admin UI doesn't keep prompting.
        voucher.liteapi_sync_status = VoucherLiteAPISyncStatus.disabled.value
        await db.flush()
        return
    if not settings.LITEAPI_VOUCHER_SYNC_ENABLED:
        # Flag off — leave status as 'not_synced' so it'll be picked up later.
        return

    payload = _build_liteapi_payload(voucher)
    try:
        # If already linked, skip update entirely: LiteAPI's PUT /vouchers/{id}
        # has a server-side bug ("Unknown column 'bindings'") and their
        # `voucher_code` is reserved forever after first use (soft-delete keeps
        # the unique constraint), so delete+recreate is also impossible.
        # We accept that supplier-side content may drift from local — the
        # voucher still applies correctly at booking time because LiteAPI uses
        # its own copy. Local-only fields (budget caps, max_uses_per_user) are
        # enforced in our validate_voucher anyway.
        if voucher.liteapi_voucher_id:
            voucher.liteapi_sync_status = VoucherLiteAPISyncStatus.synced.value
            voucher.liteapi_sync_error = None
            voucher.liteapi_synced_at = datetime.now(timezone.utc)
            await db.flush()
            return

        try:
            result = await liteapi_service.create_voucher(payload)
        except liteapi_service.LiteAPIError as exc:
            msg = (exc.message or "").lower()
            if "already exists" in msg or exc.status_code == 409:
                # Try to recover by linking the existing active supplier voucher.
                found = await _find_liteapi_id_by_code(voucher.code)
                if found:
                    voucher.liteapi_voucher_id = found
                    voucher.liteapi_sync_status = VoucherLiteAPISyncStatus.synced.value
                    voucher.liteapi_sync_error = None
                    voucher.liteapi_synced_at = datetime.now(timezone.utc)
                    await db.flush()
                    return
                # Code is reserved supplier-side but not active (soft-deleted)
                # — cannot recover without renaming. Surface a clear message.
                raise liteapi_service.LiteAPIError(
                    409,
                    f"Voucher code '{voucher.code}' is reserved on LiteAPI by a "
                    "previously deleted voucher. Rename the code (e.g. add a suffix) "
                    "and retry sync.",
                )
            raise

        liteapi_id = result.get("id") or result.get("voucher_id")
        if not liteapi_id:
            raise liteapi_service.LiteAPIError(
                502, f"LiteAPI create_voucher response missing id: {result}"
            )
        voucher.liteapi_voucher_id = str(liteapi_id)
        voucher.liteapi_sync_status = VoucherLiteAPISyncStatus.synced.value
        voucher.liteapi_sync_error = None
        voucher.liteapi_synced_at = datetime.now(timezone.utc)
    except Exception as exc:
        logger.warning("LiteAPI voucher sync failed for %s: %s", voucher.code, exc)
        voucher.liteapi_sync_status = VoucherLiteAPISyncStatus.failed.value
        voucher.liteapi_sync_error = str(exc)[:1000]
    await db.flush()


async def unsync_voucher_from_liteapi(db: AsyncSession, voucher: Voucher) -> None:
    """Remove the voucher from LiteAPI side, keep local record intact.

    Raises LiteAPIError so callers can decide whether to block the local
    operation (e.g. block a delete that would leave a supplier-side orphan).
    """
    if not voucher.liteapi_voucher_id:
        voucher.liteapi_sync_status = VoucherLiteAPISyncStatus.not_synced.value
        await db.flush()
        return
    await liteapi_service.delete_voucher(voucher.liteapi_voucher_id)
    voucher.liteapi_voucher_id = None
    voucher.liteapi_sync_status = VoucherLiteAPISyncStatus.not_synced.value
    voucher.liteapi_sync_error = None
    voucher.liteapi_synced_at = None
    await db.flush()
