"""Unit tests cho Pydantic schema validation (pure — KHÔNG cần DB).

Schema là lớp chặn dữ liệu xấu trước khi vào nghiệp vụ: bắt buộc field, ràng
buộc miền giá trị (giá > 0, sao 1–5, slug hợp lệ, rating 1–5...).
Test IDs: UT-BE-SCHEMA-01..NN.
"""
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.hotel import HotelCreate
from app.schemas.review import ReviewCreate
from app.schemas.room import ChildAgeTier, RoomCreate
from app.schemas.voucher import VoucherCreate

pytestmark = pytest.mark.nodb


class TestHotelCreate:
    def test_valid_defaults(self):
        h = HotelCreate(name="H", city="Paris", country="France")
        assert h.star_rating == 3  # default

    def test_missing_required_fields(self):
        with pytest.raises(ValidationError):
            HotelCreate(name="H")  # thiếu city/country

    def test_star_rating_out_of_range(self):
        with pytest.raises(ValidationError):
            HotelCreate(name="H", city="P", country="F", star_rating=6)

    def test_base_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            HotelCreate(name="H", city="P", country="F", base_price=0)

    def test_invalid_property_type_rejected(self):
        with pytest.raises(ValidationError):
            HotelCreate(name="H", city="P", country="F", property_type="castle")

    def test_valid_property_type_accepted(self):
        assert HotelCreate(name="H", city="P", country="F", property_type="hotels").property_type == "hotels"

    def test_invalid_amenity_slug_rejected(self):
        with pytest.raises(ValidationError):
            HotelCreate(name="H", city="P", country="F", amenities=["wifi", "teleporter"])


class TestVoucherCreate:
    def _base(self, **kw):
        data = dict(
            code="SAVE10",
            name="Save 10",
            discount_value=10,
            valid_from=date(2026, 1, 1),
            valid_to=date(2026, 12, 31),
        )
        data.update(kw)
        return data

    def test_valid_defaults(self):
        v = VoucherCreate(**self._base())
        assert v.discount_type == "percentage"
        assert v.applicable_to == "all"

    def test_discount_value_must_be_positive(self):
        with pytest.raises(ValidationError):
            VoucherCreate(**self._base(discount_value=0))

    def test_currency_must_be_three_chars(self):
        with pytest.raises(ValidationError):
            VoucherCreate(**self._base(currency="US"))

    def test_invalid_discount_type(self):
        with pytest.raises(ValidationError):
            VoucherCreate(**self._base(discount_type="bogus"))

    def test_max_uses_minimum(self):
        with pytest.raises(ValidationError):
            VoucherCreate(**self._base(max_uses=0))


class TestRoomCreate:
    def test_valid_defaults(self):
        r = RoomCreate(name="R", room_type="double", price_per_night=100)
        assert r.total_quantity == 1
        assert r.max_guests == 2

    def test_price_must_be_positive(self):
        with pytest.raises(ValidationError):
            RoomCreate(name="R", room_type="double", price_per_night=0)

    def test_child_tier_min_must_be_le_max(self):
        with pytest.raises(ValidationError):
            RoomCreate(
                name="R",
                room_type="double",
                price_per_night=100,
                child_age_tiers=[{"min_age": 10, "max_age": 5, "discount_percent": 50}],
            )

    def test_valid_child_tier_parsed(self):
        r = RoomCreate(
            name="R",
            room_type="double",
            price_per_night=100,
            child_age_tiers=[{"min_age": 0, "max_age": 5, "discount_percent": 100}],
        )
        assert r.child_age_tiers[0]["discount_percent"] == 100


class TestChildAgeTier:
    def test_age_upper_bound(self):
        with pytest.raises(ValidationError):
            ChildAgeTier(min_age=0, max_age=20, discount_percent=50)  # max_age > 17

    def test_discount_percent_bounds(self):
        with pytest.raises(ValidationError):
            ChildAgeTier(min_age=0, max_age=5, discount_percent=150)


class TestReviewCreate:
    @pytest.mark.parametrize("bad_rating", [0, 6, -1])
    def test_rating_out_of_range(self, bad_rating):
        with pytest.raises(ValidationError):
            ReviewCreate(rating=bad_rating)

    def test_valid_rating(self):
        assert ReviewCreate(rating=5, comment="great").rating == 5
