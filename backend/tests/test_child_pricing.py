"""Tests for app.core.pricing (no DB / no network)."""
from decimal import Decimal

from app.core.pricing import (
    DEFAULT_CHILD_AGE_TIERS,
    child_discount_percent,
    child_price_multiplier,
    compute_room_subtotal,
)


def test_default_tier_under_six_is_free():
    assert child_discount_percent(0) == Decimal("100")
    assert child_discount_percent(5) == Decimal("100")
    assert child_price_multiplier(3) == Decimal("0")


def test_default_tier_six_to_twelve_half_off():
    assert child_discount_percent(6) == Decimal("50")
    assert child_discount_percent(12) == Decimal("50")
    assert child_price_multiplier(8) == Decimal("0.5")


def test_default_tier_thirteen_to_seventeen_quarter_off():
    assert child_discount_percent(13) == Decimal("25")
    assert child_discount_percent(17) == Decimal("25")
    assert child_price_multiplier(15) == Decimal("0.75")


def test_adult_age_pays_full_price():
    assert child_discount_percent(18) == Decimal("0")
    assert child_price_multiplier(18) == Decimal("1")


def test_base_room_price_unchanged_for_capacity_fit():
    # 2 adults in a max_guests=2 room → no extras → price_per_night × nights
    result = compute_room_subtotal(
        100, nights=2, quantity=1, adults=2, children_ages=[], max_guests=2
    )
    assert result == Decimal("200.00")


def test_legacy_call_without_max_guests_charges_room_rate():
    # When max_guests is omitted, capacity defaults to adults so the base rate
    # is preserved — keeps existing booking tests stable.
    result = compute_room_subtotal(
        200, nights=2, quantity=1, adults=2, children_ages=[]
    )
    assert result == Decimal("400.00")


def test_child_adds_tier_fraction_to_base():
    # 2 adults + age 3 (free) + age 8 (50% of one night) at $100 × 2 nights
    # base = $200; child surcharge = $0 + ($100 × 0.5 × 2) = $100 → $300
    result = compute_room_subtotal(
        100, nights=2, quantity=1, adults=2, children_ages=[3, 8], max_guests=2
    )
    assert result == Decimal("300.00")


def test_extra_adult_above_capacity_pays_full_surcharge():
    # max_guests=2 but adults=3 → 1 extra adult adds full per-night charge.
    result = compute_room_subtotal(
        100, nights=1, quantity=1, adults=3, children_ages=[], max_guests=2
    )
    assert result == Decimal("200.00")


def test_quantity_multiplies_base():
    result = compute_room_subtotal(
        100, nights=1, quantity=3, adults=2, children_ages=[], max_guests=2
    )
    assert result == Decimal("300.00")


def test_custom_tiers_override_default():
    custom = [{"min_age": 0, "max_age": 17, "discount_percent": 10}]
    # 2 adults + 1 child age 4 with custom tier (90% surcharge):
    # base = $100 (2 adults fit), child surcharge = $100 × 0.9 × 1 = $90
    result = compute_room_subtotal(
        100, nights=1, quantity=1, adults=2, children_ages=[4],
        tiers=custom, max_guests=2,
    )
    assert result == Decimal("190.00")


def test_default_tiers_exposed_for_consumers():
    assert DEFAULT_CHILD_AGE_TIERS[0]["max_age"] == 5
    assert DEFAULT_CHILD_AGE_TIERS[-1]["max_age"] == 17
