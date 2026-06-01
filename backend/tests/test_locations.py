"""Route tests cho /locations/autocomplete (cần DB test + extension pg_trgm/unaccent).

Chỉ kiểm tra các nhánh an toàn (không gọi Nominatim ngoài): query quá ngắn trả [],
query 2 ký tự không khớp (bảng cities rỗng) trả [] và set header cache.
Test IDs: UT-BE-LOC-01..NN.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_short_query_returns_empty(client: AsyncClient):
    # < 2 ký tự → trả [] trước khi chạy SQL (và không set Cache-Control).
    res = await client.get("/api/v1/locations/autocomplete", params={"q": "a"})
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_no_match_returns_empty_without_nominatim_fallback(client: AsyncClient):
    # 2 ký tự: chạy SQL trên bảng rỗng → []; < 3 ký tự nên KHÔNG fallback Nominatim.
    res = await client.get("/api/v1/locations/autocomplete", params={"q": "zz"})
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_sets_cache_control_header(client: AsyncClient):
    res = await client.get("/api/v1/locations/autocomplete", params={"q": "zz"})
    assert res.status_code == 200
    assert "public" in res.headers.get("Cache-Control", "")
