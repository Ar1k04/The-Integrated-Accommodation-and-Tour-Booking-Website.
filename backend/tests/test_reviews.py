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
async def test_create_liteapi_review_without_completed_stay_forbidden(
    client: AsyncClient, user_token
):
    # Chưa hoàn tất booking khách sạn LiteAPI này → 403.
    res = await client.post(
        "/api/v1/reviews",
        json={"rating": 5, "liteapi_hotel_id": "lp_test_123", "comment": "Nice"},
        headers=auth_header(user_token),
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_create_and_list_liteapi_review(
    client: AsyncClient, db_session, test_user, user_token, monkeypatch
):
    from app.models.booking import Booking
    from app.models.booking_item import BookingItem
    from app.services import liteapi_service

    lite_id = "lp_test_review"

    booking = Booking(user_id=test_user.id, total_price=200, status="completed")
    db_session.add(booking)
    await db_session.flush()
    db_session.add(
        BookingItem(
            booking_id=booking.id,
            item_type="room",
            liteapi_prebook_id="prebook_1",
            liteapi_hotel_id=lite_id,
            status="completed",
            unit_price=200,
            subtotal=200,
        )
    )
    await db_session.flush()

    # Hoàn tất lưu trú → tạo review thành công.
    created = await client.post(
        "/api/v1/reviews",
        json={"rating": 5, "liteapi_hotel_id": lite_id, "comment": "Great stay"},
        headers=auth_header(user_token),
    )
    assert created.status_code == 201

    # Review thứ hai cho cùng hotel → 409.
    dup = await client.post(
        "/api/v1/reviews",
        json={"rating": 4, "liteapi_hotel_id": lite_id},
        headers=auth_header(user_token),
    )
    assert dup.status_code == 409

    # Listing gộp review user (DB) lên đầu feed LiteAPI (mock rỗng để khỏi gọi mạng).
    async def _no_liteapi_reviews(hotel_id, limit=50):
        return []

    monkeypatch.setattr(liteapi_service, "get_hotel_reviews", _no_liteapi_reviews)
    listed = await client.get(f"/api/v1/hotels/liteapi/{lite_id}/reviews")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert any(i["comment"] == "Great stay" and i["rating"] == 5 for i in items)


@pytest.mark.asyncio
async def test_hotel_review_allowed_after_checkout_via_lazy_complete(
    client: AsyncClient, db_session, test_user, user_token, test_hotel, test_room
):
    """A confirmed room booking whose check-out has passed is auto-completed by
    the lazy sweep inside POST /reviews, so the guest can review immediately."""
    from datetime import date, timedelta

    from app.models.booking import Booking
    from app.models.booking_item import BookingItem

    booking = Booking(user_id=test_user.id, total_price=200, status="confirmed")
    db_session.add(booking)
    await db_session.flush()
    db_session.add(
        BookingItem(
            booking_id=booking.id, item_type="room", room_id=test_room.id,
            check_in=date.today() - timedelta(days=3),
            check_out=date.today() - timedelta(days=1),
            status="confirmed", unit_price=200, subtotal=200,
        )
    )
    await db_session.flush()

    res = await client.post(
        "/api/v1/reviews",
        json={"rating": 5, "hotel_id": str(test_hotel.id), "comment": "Great stay"},
        headers=auth_header(user_token),
    )
    assert res.status_code == 201

    # The lazy sweep should also have rolled the single-item booking up.
    await db_session.refresh(booking)
    assert booking.status == "completed"


@pytest.mark.asyncio
async def test_hotel_reviewable_even_when_sibling_flight_pending(
    client: AsyncClient, db_session, test_user, user_token, test_hotel, test_room
):
    """Item-level eligibility: a finished hotel stay is reviewable even though a
    sibling flight in the same booking hasn't departed (booking still confirmed)."""
    from datetime import date, datetime, timedelta, timezone

    from app.models.booking import Booking
    from app.models.booking_item import BookingItem
    from app.models.flight_booking import FlightBooking

    booking = Booking(user_id=test_user.id, total_price=300, status="confirmed")
    db_session.add(booking)
    await db_session.flush()
    flight = FlightBooking(
        airline_name="Duffel Airways", flight_number="ZZ200",
        departure_airport="HAN", arrival_airport="SGN",
        departure_at=datetime.now(timezone.utc) + timedelta(days=30),
        arrival_at=datetime.now(timezone.utc) + timedelta(days=30, hours=2),
        passenger_name="Test User", passenger_email="t@example.com",
        base_amount=100, total_amount=100, status="confirmed",
    )
    db_session.add(flight)
    await db_session.flush()
    db_session.add_all([
        BookingItem(
            booking_id=booking.id, item_type="room", room_id=test_room.id,
            check_in=date.today() - timedelta(days=3),
            check_out=date.today() - timedelta(days=1),
            status="confirmed", unit_price=200, subtotal=200,
        ),
        BookingItem(
            booking_id=booking.id, item_type="flight", flight_booking_id=flight.id,
            status="confirmed", unit_price=100, subtotal=100,
        ),
    ])
    await db_session.flush()

    res = await client.post(
        "/api/v1/reviews",
        json={"rating": 4, "hotel_id": str(test_hotel.id)},
        headers=auth_header(user_token),
    )
    assert res.status_code == 201

    # Booking is NOT completed (flight still pending), but the review went through.
    await db_session.refresh(booking)
    assert booking.status == "confirmed"


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
