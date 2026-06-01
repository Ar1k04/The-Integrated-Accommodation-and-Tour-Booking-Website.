"""Unit tests cho app/core/pricing.py (pure logic — KHÔNG cần DB).

Pricing là nghiệp vụ cốt lõi: tính giá phòng theo sức chứa/phụ thu, giá tour
theo độ tuổi (child tiers) và theo age-band của partner. Toàn bộ hàm ở đây là
thuần (deterministic) nên test rất nhanh và đáng tin.

These cover the local (DB) pricing helpers; supplier-quoted prices (LiteAPI /
Viator) are trusted as-is and not recomputed here.

Test IDs: UT-BE-PRICING-01..NN (xem docs/unit_test_design.md).
"""
from decimal import Decimal

import pytest

from app.core import pricing
from app.core.pricing import (
    AgeBandError,
    adult_band_price,
    child_discount_percent,
    child_price_multiplier,
    compute_room_subtotal,
    compute_tour_subtotal,
    compute_tour_subtotal_from_bands,
    match_age_band,
)

# Mọi test trong file này là pure-unit, không chạm DB.
pytestmark = pytest.mark.nodb


# ── child_discount_percent ───────────────────────────────────────────────────
class TestChildDiscountPercent:
    @pytest.mark.parametrize(
        "age,expected",
        [
            (0, "100"),   # infant — free
            (3, "100"),
            (5, "100"),   # boundary cuối tier 0–5
            (6, "50"),    # boundary đầu tier 6–12
            (8, "50"),
            (12, "50"),   # boundary cuối tier 6–12
            (13, "25"),   # boundary đầu tier 13–17
            (17, "25"),   # boundary cuối tier trẻ em
        ],
    )
    def test_default_tiers(self, age, expected):
        assert child_discount_percent(age) == Decimal(expected)

    @pytest.mark.parametrize("age", [18, 20, 65])
    def test_age_above_child_range_is_not_discounted(self, age):
        # >17 không còn là trẻ em → 0% (trả như người lớn).
        assert child_discount_percent(age) == Decimal("0")

    def test_negative_age_returns_zero(self):
        assert child_discount_percent(-1) == Decimal("0")

    def test_custom_tiers_override_default(self):
        tiers = [{"min_age": 0, "max_age": 10, "discount_percent": 80}]
        assert child_discount_percent(7, tiers) == Decimal("80")
        # Tuổi 11 vẫn trong child range (<=17) nhưng không khớp custom tier nào → 0.
        assert child_discount_percent(11, tiers) == Decimal("0")


# ── child_price_multiplier ───────────────────────────────────────────────────
class TestChildPriceMultiplier:
    def test_free_child_costs_zero_fraction(self):
        assert child_price_multiplier(3) == Decimal("0")  # 100% off → 0.0

    def test_half_price_child(self):
        assert child_price_multiplier(8) == Decimal("0.5")

    def test_quarter_off_child(self):
        assert child_price_multiplier(15) == Decimal("0.75")  # 25% off

    def test_out_of_range_pays_full(self):
        assert child_price_multiplier(30) == Decimal("1")  # 0% off → full


# ── compute_room_subtotal ────────────────────────────────────────────────────
class TestComputeRoomSubtotal:
    def test_base_within_capacity_no_children(self):
        # price 100 × 2 đêm × 1 phòng, đúng sức chứa → 200.00
        assert compute_room_subtotal(100, 2, 1, 2, [], max_guests=2) == Decimal("200.00")

    def test_extra_adult_beyond_capacity_adds_full_surcharge(self):
        # capacity=2, 3 adults → 1 extra: surcharge = 100 × 1 × 2 đêm = 200 → 400.00
        assert compute_room_subtotal(100, 2, 1, 3, [], max_guests=2) == Decimal("400.00")

    def test_child_adds_tier_fraction(self):
        # base 100 (1 đêm) + child 8 tuổi (50%) = 100 + 50 = 150.00
        assert compute_room_subtotal(100, 1, 1, 2, [8], max_guests=2) == Decimal("150.00")

    def test_quantity_scales_capacity_linearly(self):
        # 2 phòng × max_guests 2 = capacity 4; 4 adults vừa khít → không phụ thu.
        assert compute_room_subtotal(100, 1, 2, 4, [], max_guests=2) == Decimal("200.00")

    def test_nights_floored_to_one(self):
        # nights=0 được nâng lên 1 (không cho subtotal = 0).
        assert compute_room_subtotal(100, 0, 1, 1, [], max_guests=1) == Decimal("100.00")

    def test_free_infant_adds_nothing(self):
        assert compute_room_subtotal(100, 1, 1, 2, [3], max_guests=2) == Decimal("100.00")

    def test_result_is_quantized_to_cents(self):
        out = compute_room_subtotal(33.333, 1, 1, 1, [], max_guests=1)
        assert out == Decimal("33.33")
        assert out.as_tuple().exponent == -2  # đúng 2 chữ số thập phân


# ── compute_tour_subtotal (partner tour fallback, không có age band) ──────────
class TestComputeTourSubtotal:
    def test_adults_only(self):
        assert compute_tour_subtotal(50, 2, []) == Decimal("100.00")

    def test_adults_plus_half_price_child(self):
        # 2 adults × 50 + child 8 (50%) × 50 = 100 + 25 = 125.00
        assert compute_tour_subtotal(50, 2, [8]) == Decimal("125.00")

    def test_free_child_band(self):
        assert compute_tour_subtotal(50, 1, [2]) == Decimal("50.00")

    def test_at_least_one_adult(self):
        # adults được nâng tối thiểu 1.
        assert compute_tour_subtotal(50, 0, []) == Decimal("50.00")


# ── adult_band_price ─────────────────────────────────────────────────────────
class TestAdultBandPrice:
    def test_returns_adult_band_price(self):
        bands = [
            {"age_band": "ADULT", "start_age": 12, "end_age": 99, "price": 80},
            {"age_band": "CHILD", "start_age": 2, "end_age": 11, "price": 40},
        ]
        assert adult_band_price(bands, fallback=999) == Decimal("80")

    def test_falls_back_when_no_adult_band(self):
        bands = [{"age_band": "CHILD", "start_age": 2, "end_age": 11, "price": 40}]
        assert adult_band_price(bands, fallback=70) == Decimal("70")

    def test_none_bands_uses_fallback(self):
        assert adult_band_price(None, fallback=55) == Decimal("55")

    def test_camelcase_keys_supported(self):
        # Viator-shaped band dùng "ageBand"; band không có price → dùng fallback.
        bands = [{"ageBand": "ADULT", "startAge": 18, "endAge": 99}]
        assert adult_band_price(bands, fallback=120) == Decimal("120")


# ── match_age_band ───────────────────────────────────────────────────────────
class TestMatchAgeBand:
    BANDS = [
        {"age_band": "ADULT", "start_age": 12, "end_age": 99, "price": 80},
        {"age_band": "CHILD", "start_age": 2, "end_age": 11, "price": 40},
        {"age_band": "INFANT", "start_age": 0, "end_age": 1, "price": 0},
    ]

    def test_matches_child_band(self):
        assert match_age_band(5, self.BANDS)["age_band"] == "CHILD"

    def test_matches_infant_band(self):
        assert match_age_band(1, self.BANDS)["age_band"] == "INFANT"

    def test_adult_band_excluded_from_child_match(self):
        # Tuổi 50 chỉ khớp ADULT, nhưng ADULT bị loại → None.
        assert match_age_band(50, self.BANDS) is None

    def test_age_outside_all_child_bands_returns_none(self):
        assert match_age_band(11, self.BANDS)["age_band"] == "CHILD"
        assert match_age_band(12, self.BANDS) is None  # rơi vào ADULT → loại

    def test_lowest_start_age_wins_on_overlap(self):
        overlapping = [
            {"age_band": "A", "start_age": 0, "end_age": 10, "price": 10},
            {"age_band": "B", "start_age": 5, "end_age": 10, "price": 20},
        ]
        assert match_age_band(7, overlapping)["age_band"] == "A"


# ── compute_tour_subtotal_from_bands ─────────────────────────────────────────
class TestComputeTourSubtotalFromBands:
    BANDS = [
        {"age_band": "ADULT", "start_age": 12, "end_age": 99, "price": 80},
        {"age_band": "CHILD", "start_age": 2, "end_age": 11, "price": 40},
        {"age_band": "INFANT", "start_age": 0, "end_age": 1, "price": 0},
    ]

    def test_adults_and_children_priced_by_band(self):
        # 2 adults × 80 + child(5)=40 + infant(1)=0 = 200.00
        out = compute_tour_subtotal_from_bands(self.BANDS, adults=2, children_ages=[5, 1], fallback_price=999)
        assert out == Decimal("200.00")

    def test_age_outside_every_band_raises(self):
        # Tour chỉ nhận tới 11 tuổi cho trẻ; child 13 không có band → reject.
        with pytest.raises(AgeBandError):
            compute_tour_subtotal_from_bands(self.BANDS, adults=1, children_ages=[13], fallback_price=80)

    def test_adult_only_uses_adult_band(self):
        out = compute_tour_subtotal_from_bands(self.BANDS, adults=3, children_ages=[], fallback_price=999)
        assert out == Decimal("240.00")

    def test_missing_adult_band_uses_fallback_price(self):
        bands = [{"age_band": "CHILD", "start_age": 2, "end_age": 11, "price": 40}]
        out = compute_tour_subtotal_from_bands(bands, adults=2, children_ages=[5], fallback_price=100)
        # 2 × fallback(100) + child(40) = 240.00
        assert out == Decimal("240.00")

    def test_age_band_error_is_value_error_subclass(self):
        # Cho phép caller bắt bằng ValueError (mirrors Viator enforcement).
        assert issubclass(AgeBandError, ValueError)
