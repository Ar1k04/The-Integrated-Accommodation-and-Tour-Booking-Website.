"""Route tests cho /wishlists (cần DB test).

Bao phủ: yêu cầu đăng nhập, thêm/list, ràng buộc XOR hotel|tour, chống trùng,
xoá. Test IDs: UT-BE-WISH-01..NN.
"""
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_list_requires_auth(client: AsyncClient):
    res = await client.get("/api/v1/wishlists")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_add_then_list(client: AsyncClient, user_token, test_hotel):
    res = await client.post(
        "/api/v1/wishlists",
        json={"hotel_id": str(test_hotel.id)},
        headers=auth_header(user_token),
    )
    assert res.status_code == 201
    assert res.json()["hotel_id"] == str(test_hotel.id)

    listing = await client.get("/api/v1/wishlists", headers=auth_header(user_token))
    assert listing.status_code == 200
    assert any(i["hotel_id"] == str(test_hotel.id) for i in listing.json()["items"])


@pytest.mark.asyncio
async def test_add_requires_exactly_one_target(client: AsyncClient, user_token, test_hotel):
    # Không có target nào → 400
    none_res = await client.post("/api/v1/wishlists", json={}, headers=auth_header(user_token))
    assert none_res.status_code == 400
    # Cả hai target → 400
    both_res = await client.post(
        "/api/v1/wishlists",
        json={"hotel_id": str(test_hotel.id), "tour_id": str(uuid.uuid4())},
        headers=auth_header(user_token),
    )
    assert both_res.status_code == 400


@pytest.mark.asyncio
async def test_duplicate_returns_409(client: AsyncClient, user_token, test_hotel):
    payload = {"hotel_id": str(test_hotel.id)}
    await client.post("/api/v1/wishlists", json=payload, headers=auth_header(user_token))
    dup = await client.post("/api/v1/wishlists", json=payload, headers=auth_header(user_token))
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_delete_owned_item(client: AsyncClient, user_token, test_hotel):
    add = await client.post(
        "/api/v1/wishlists", json={"hotel_id": str(test_hotel.id)}, headers=auth_header(user_token)
    )
    wid = add.json()["id"]
    deleted = await client.delete(f"/api/v1/wishlists/{wid}", headers=auth_header(user_token))
    assert deleted.status_code == 204


@pytest.mark.asyncio
async def test_delete_missing_returns_404(client: AsyncClient, user_token):
    res = await client.delete(f"/api/v1/wishlists/{uuid.uuid4()}", headers=auth_header(user_token))
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_add_liteapi_hotel_with_snapshot(client: AsyncClient, user_token):
    res = await client.post(
        "/api/v1/wishlists",
        json={
            "liteapi_hotel_id": "lp1a2b3c",
            "item_name": "Sandbox Beach Resort",
            "item_city": "Da Nang",
            "item_country": "Vietnam",
            "item_image": "https://example.com/a.jpg",
        },
        headers=auth_header(user_token),
    )
    assert res.status_code == 201
    body = res.json()
    assert body["liteapi_hotel_id"] == "lp1a2b3c"
    assert body["item_name"] == "Sandbox Beach Resort"
    assert body["hotel_id"] is None and body["tour_id"] is None

    listing = await client.get("/api/v1/wishlists", headers=auth_header(user_token))
    assert any(i["liteapi_hotel_id"] == "lp1a2b3c" for i in listing.json()["items"])


@pytest.mark.asyncio
async def test_add_viator_tour(client: AsyncClient, user_token):
    res = await client.post(
        "/api/v1/wishlists",
        json={"viator_product_code": "5010SYDNEY", "item_name": "Opera House Tour"},
        headers=auth_header(user_token),
    )
    assert res.status_code == 201
    assert res.json()["viator_product_code"] == "5010SYDNEY"


@pytest.mark.asyncio
async def test_external_duplicate_returns_409(client: AsyncClient, user_token):
    payload = {"viator_product_code": "DUP123", "item_name": "Dup tour"}
    await client.post("/api/v1/wishlists", json=payload, headers=auth_header(user_token))
    dup = await client.post("/api/v1/wishlists", json=payload, headers=auth_header(user_token))
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_two_external_targets_returns_400(client: AsyncClient, user_token):
    res = await client.post(
        "/api/v1/wishlists",
        json={"liteapi_hotel_id": "x", "viator_product_code": "y"},
        headers=auth_header(user_token),
    )
    assert res.status_code == 400
