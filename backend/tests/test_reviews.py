"""Route tests cho reviews (cần DB test).

Bao phủ: 404 khi hotel/tour không tồn tại, ràng buộc "đúng 1 target", chốt chặn
"chỉ review khi đã hoàn tất booking" (403), quyền sửa/xoá (owner/admin).
Test IDs: UT-BE-REVIEW-01..NN.
"""
import uuid

import pytest
from httpx import AsyncClient

from tests.conftest import auth_header


@pytest.mark.asyncio
async def test_list_hotel_reviews_404_when_hotel_missing(client: AsyncClient):
    res = await client.get(f"/api/v1/hotels/{uuid.uuid4()}/reviews")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_hotel_reviews_empty(client: AsyncClient, test_hotel):
    res = await client.get(f"/api/v1/hotels/{test_hotel.id}/reviews")
    assert res.status_code == 200
    assert res.json()["items"] == []


@pytest.mark.asyncio
async def test_create_review_requires_exactly_one_target(client: AsyncClient, user_token, test_hotel):
    # Không target nào
    r0 = await client.post("/api/v1/reviews", json={"rating": 5}, headers=auth_header(user_token))
    assert r0.status_code == 400
    # Hai target
    r2 = await client.post(
        "/api/v1/reviews",
        json={"rating": 5, "hotel_id": str(test_hotel.id), "tour_id": str(uuid.uuid4())},
        headers=auth_header(user_token),
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_create_hotel_review_without_completed_stay_forbidden(
    client: AsyncClient, user_token, test_hotel
):
    # Chưa từng hoàn tất booking khách sạn này → 403.
    res = await client.post(
        "/api/v1/reviews",
        json={"rating": 5, "hotel_id": str(test_hotel.id), "comment": "Lovely"},
        headers=auth_header(user_token),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_owner_can_update_but_admin_cannot(
    client: AsyncClient, db_session, test_user, user_token, admin_user, admin_token, test_hotel
):
    from app.models.review import Review

    review = Review(user_id=test_user.id, hotel_id=test_hotel.id, rating=4, comment="ok")
    db_session.add(review)
    await db_session.flush()
    rid = str(review.id)

    upd = await client.patch(
        f"/api/v1/reviews/{rid}", json={"rating": 5}, headers=auth_header(user_token)
    )
    assert upd.status_code == 200
    assert upd.json()["rating"] == 5

    # PATCH chỉ dành cho chủ sở hữu — admin không phải chủ → 403.
    upd_admin = await client.patch(
        f"/api/v1/reviews/{rid}", json={"rating": 3}, headers=auth_header(admin_token)
    )
    assert upd_admin.status_code == 403


@pytest.mark.asyncio
async def test_update_missing_review_404(client: AsyncClient, user_token):
    res = await client.patch(
        f"/api/v1/reviews/{uuid.uuid4()}", json={"rating": 5}, headers=auth_header(user_token)
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_non_owner_forbidden_owner_allowed(
    client: AsyncClient, db_session, test_user, user_token, partner_user, partner_token, test_hotel
):
    from app.models.review import Review

    review = Review(user_id=test_user.id, hotel_id=test_hotel.id, rating=4)
    db_session.add(review)
    await db_session.flush()
    rid = str(review.id)

    # Partner (không phải chủ, không phải admin) → 403.
    bad = await client.delete(f"/api/v1/reviews/{rid}", headers=auth_header(partner_token))
    assert bad.status_code == 403
    # Chủ sở hữu → 204.
    ok = await client.delete(f"/api/v1/reviews/{rid}", headers=auth_header(user_token))
    assert ok.status_code == 204


@pytest.mark.asyncio
async def test_admin_can_delete_any_review(
    client: AsyncClient, db_session, test_user, admin_user, admin_token, test_hotel
):
    from app.models.review import Review

    review = Review(user_id=test_user.id, hotel_id=test_hotel.id, rating=4)
    db_session.add(review)
    await db_session.flush()
    rid = str(review.id)

    res = await client.delete(f"/api/v1/reviews/{rid}", headers=auth_header(admin_token))
    assert res.status_code == 204
