"""Unit tests cho app/services/facility_mapping.py (pure data — KHÔNG cần DB).

Các dict này ánh xạ slug nội bộ ↔ ID canonical của LiteAPI. Sai ID → filter
amenities/hotel-type khi gọi LiteAPI lệch hoàn toàn, nên cần test chốt giá trị.

Test IDs: UT-BE-MAP-01..NN.
"""
import pytest

from app.services.facility_mapping import HOTEL_TYPE_SLUG_TO_ID, SLUG_TO_LITEAPI_ID

pytestmark = pytest.mark.nodb


class TestFacilitySlugMapping:
    @pytest.mark.parametrize(
        "slug,expected_id",
        [("wifi", 107), ("pool", 301), ("gym", 11), ("spa", 54), ("parking", 2)],
    )
    def test_known_amenity_ids(self, slug, expected_id):
        assert SLUG_TO_LITEAPI_ID[slug] == expected_id

    def test_all_ids_are_positive_ints(self):
        assert all(isinstance(v, int) and v > 0 for v in SLUG_TO_LITEAPI_ID.values())

    def test_ids_are_unique(self):
        ids = list(SLUG_TO_LITEAPI_ID.values())
        assert len(ids) == len(set(ids))  # không trùng ID


class TestHotelTypeSlugMapping:
    @pytest.mark.parametrize(
        "slug,expected_id",
        [("hotels", 204), ("hostels", 203), ("resorts", 206), ("palace", 278)],
    )
    def test_known_hotel_type_ids(self, slug, expected_id):
        assert HOTEL_TYPE_SLUG_TO_ID[slug] == expected_id

    def test_all_ids_are_positive_ints(self):
        assert all(isinstance(v, int) and v > 0 for v in HOTEL_TYPE_SLUG_TO_ID.values())

    def test_ids_are_unique(self):
        ids = list(HOTEL_TYPE_SLUG_TO_ID.values())
        assert len(ids) == len(set(ids))
