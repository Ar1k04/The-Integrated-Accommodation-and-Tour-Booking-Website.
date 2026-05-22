"""Pricing helpers for child/adult occupancy rates.

LiteAPI returns the already child-adjusted price from the supplier, so this
module only governs local (DB) room pricing. The default tier matches what
the user agreed on during planning; an admin can override per-room via the
``rooms.child_age_tiers`` JSONB column.

Pricing model
-------------
``price_per_night`` is the full-room rate covering up to ``max_guests``
occupants (industry convention). Extra adults beyond capacity add a full
per-night surcharge; children always add the age-tier fraction of one
adult night — so a 3-year-old in a default-tier room costs nothing extra
while an 8-year-old adds half the per-night rate.

When ``quantity > 1`` (multiple rooms booked together), capacity scales
linearly with ``quantity`` so callers don't have to split guests between
rooms manually.
"""
from __future__ import annotations

from decimal import Decimal


DEFAULT_CHILD_AGE_TIERS: list[dict] = [
    {"min_age": 0, "max_age": 5, "discount_percent": 100},
    {"min_age": 6, "max_age": 12, "discount_percent": 50},
    {"min_age": 13, "max_age": 17, "discount_percent": 25},
]

CHILD_MAX_AGE = 17


def child_discount_percent(age: int, tiers: list[dict] | None = None) -> Decimal:
    """Return the discount percentage (0–100) for a given child age."""
    if age < 0 or age > CHILD_MAX_AGE:
        return Decimal("0")
    use_tiers = tiers if tiers else DEFAULT_CHILD_AGE_TIERS
    for tier in use_tiers:
        if int(tier["min_age"]) <= age <= int(tier["max_age"]):
            return Decimal(str(tier["discount_percent"]))
    return Decimal("0")


def child_price_multiplier(age: int, tiers: list[dict] | None = None) -> Decimal:
    """Fraction of an adult night a child of `age` costs (0.0–1.0)."""
    return (Decimal("100") - child_discount_percent(age, tiers)) / Decimal("100")


def compute_room_subtotal(
    price_per_night,
    nights: int,
    quantity: int,
    adults: int,
    children_ages: list[int] | None,
    tiers: list[dict] | None = None,
    max_guests: int | None = None,
) -> Decimal:
    """Compute booking subtotal for a local room.

    Base = ``price_per_night × nights × quantity`` (covers up to
    ``max_guests × quantity`` adults). Adults above that cap add a full
    per-night surcharge each; every child adds the tier fraction
    regardless of capacity. Backward-compatible with the previous formula
    when ``adults == capacity`` and no children are present.
    """
    price = Decimal(str(price_per_night))
    nights = max(1, int(nights))
    quantity = max(1, int(quantity))
    adults = max(1, int(adults))
    capacity = (max_guests or adults) * quantity

    base = price * Decimal(nights) * Decimal(quantity)

    extra_adults = max(0, adults - capacity)
    adult_surcharge = price * Decimal(extra_adults) * Decimal(nights)

    child_surcharge = Decimal("0")
    for age in children_ages or []:
        child_surcharge += price * child_price_multiplier(age, tiers) * Decimal(nights)

    return (base + adult_surcharge + child_surcharge).quantize(Decimal("0.01"))


def compute_tour_subtotal(
    price_per_person,
    adults: int,
    children_ages: list[int] | None,
    tiers: list[dict] | None = None,
) -> Decimal:
    """Compute booking subtotal for a local (partner) tour.

    Adults pay full ``price_per_person``; each child pays the tier fraction
    (default: 0–5 free, 6–12 50% off, 13–17 25% off). Used by
    ``_reserve_tour_item`` so partner tours mirror the hotel child-pricing
    behaviour. External suppliers (Viator) trust the supplier-quoted price.
    """
    price = Decimal(str(price_per_person))
    adults = max(1, int(adults))
    adult_total = price * Decimal(adults)
    child_total = Decimal("0")
    for age in children_ages or []:
        child_total += price * child_price_multiplier(age, tiers)
    return (adult_total + child_total).quantize(Decimal("0.01"))
