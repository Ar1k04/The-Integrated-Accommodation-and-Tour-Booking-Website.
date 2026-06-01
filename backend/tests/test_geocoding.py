"""Unit tests cho app/services/geocoding_service.py.

Service gọi Nominatim qua httpx.AsyncClient (tạo inline). Ta thay AsyncClient
bằng một async context-manager giả để không chạm mạng và không cần DB.

Test IDs: UT-BE-GEO-01..NN.
"""
import pytest

from app.services import geocoding_service
from app.services.geocoding_service import geocode_address, search_cities_nominatim

pytestmark = pytest.mark.nodb


class _Resp:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


class _FakeClient:
    """Đóng vai httpx.AsyncClient: trả lần lượt các response đã set sẵn."""

    def __init__(self, responses=None, raise_exc=None):
        self._responses = list(responses or [])
        self._raise = raise_exc
        self.requests = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        self.requests.append({"url": url, "params": params})
        if self._raise:
            raise self._raise
        return self._responses.pop(0)


def _patch_client(monkeypatch, fake):
    monkeypatch.setattr(geocoding_service.httpx, "AsyncClient", lambda *a, **k: fake)


class TestGeocodeAddress:
    async def test_returns_none_without_any_input_and_skips_http(self, monkeypatch):
        def _boom(*a, **k):
            raise AssertionError("không được gọi HTTP khi không có input")

        monkeypatch.setattr(geocoding_service.httpx, "AsyncClient", _boom)
        assert await geocode_address(None, None, None) is None

    async def test_returns_coords_on_first_hit(self, monkeypatch):
        fake = _FakeClient([_Resp(200, [{"lat": "10.5", "lon": "106.6"}])])
        _patch_client(monkeypatch, fake)
        assert await geocode_address("1 Street", "Ho Chi Minh", "Vietnam") == (10.5, 106.6)

    async def test_falls_back_to_city_country_query(self, monkeypatch):
        # Query đầy đủ địa chỉ rỗng → thử lại với (city, country).
        fake = _FakeClient([_Resp(200, []), _Resp(200, [{"lat": "21.0", "lon": "105.8"}])])
        _patch_client(monkeypatch, fake)
        assert await geocode_address("Nowhere", "Hanoi", "Vietnam") == (21.0, 105.8)
        assert len(fake.requests) == 2

    async def test_returns_none_when_all_queries_fail(self, monkeypatch):
        _patch_client(monkeypatch, _FakeClient([_Resp(500, None), _Resp(404, None)]))
        assert await geocode_address("X", "Y", "Z") is None

    async def test_swallows_network_exceptions(self, monkeypatch):
        _patch_client(monkeypatch, _FakeClient(raise_exc=RuntimeError("boom")))
        assert await geocode_address(None, "Paris", "France") is None


class TestSearchCitiesNominatim:
    async def test_short_query_returns_empty_without_http(self, monkeypatch):
        def _boom(*a, **k):
            raise AssertionError("không được gọi HTTP cho query < 2 ký tự")

        monkeypatch.setattr(geocoding_service.httpx, "AsyncClient", _boom)
        assert await search_cities_nominatim("a") == []

    async def test_parses_and_dedupes_results(self, monkeypatch):
        data = [
            {"address": {"city": "Hanoi", "country": "Vietnam", "country_code": "vn"}},
            {"address": {"city": "Hanoi", "country": "Vietnam"}},  # trùng (city,country) → loại
            {"address": {"town": "Da Lat", "country": "Vietnam", "country_code": "vn"}},
        ]
        _patch_client(monkeypatch, _FakeClient([_Resp(200, data)]))
        out = await search_cities_nominatim("ha")
        assert [c["city"] for c in out] == ["Hanoi", "Da Lat"]
        assert out[0]["countryCode"] == "VN"  # country_code được viết hoa

    async def test_non_200_returns_empty(self, monkeypatch):
        _patch_client(monkeypatch, _FakeClient([_Resp(500, None)]))
        assert await search_cities_nominatim("hanoi") == []

    async def test_exception_returns_empty(self, monkeypatch):
        _patch_client(monkeypatch, _FakeClient(raise_exc=RuntimeError("x")))
        assert await search_cities_nominatim("hanoi") == []
