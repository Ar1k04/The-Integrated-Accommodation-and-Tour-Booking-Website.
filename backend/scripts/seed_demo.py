"""Demo seed script for graduation defense.

Usage (with Docker):
    docker exec travel_backend python -m scripts.seed_demo

Idempotent: skips seeding if admin@demo.com already exists.
Creates:
  - 1 superadmin (admin@demo.com / Demo1234!)
  - 2 partner-admin users (partner1@demo.com, partner2@demo.com / Demo1234!)
  - 3 regular users (user1..3@demo.com / Demo1234!)
  - 4 hotels with 2-3 rooms each
  - 4 tours with 30 days of schedules
  - 2 vouchers
  - 3 completed bookings (room + tour) with reviews
"""
import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.models.booking import Booking
from app.models.booking_item import BookingItem, BookingItemType
from app.models.hotel import Hotel
from app.models.loyalty_tier import LoyaltyTier
from app.models.review import Review
from app.models.room import Room
from app.models.tour import Tour
from app.models.tour_schedule import TourSchedule
from app.models.user import User
from app.models.voucher import Voucher

DEFAULT_PASS = "Demo1234!"

HOTELS = [
    {"name": "Hanoi Pearl Hotel", "city": "Hanoi", "country": "Vietnam", "star_rating": 4,
     "description": "Elegant 4-star hotel in the heart of Hoan Kiem district.", "base_price": 80},
    {"name": "Da Nang Beach Resort", "city": "Da Nang", "country": "Vietnam", "star_rating": 5,
     "description": "Luxury beachfront resort on My Khe beach.", "base_price": 150},
    {"name": "Hoi An Riverside Inn", "city": "Hoi An", "country": "Vietnam", "star_rating": 3,
     "description": "Charming boutique inn steps from the ancient town.", "base_price": 55},
    {"name": "Saigon Central Hotel", "city": "Ho Chi Minh City", "country": "Vietnam", "star_rating": 4,
     "description": "Modern business hotel in District 1.", "base_price": 95},
]

ROOM_TYPES = [
    {"name": "Standard Double", "room_type": "double", "price_per_night": 60, "max_guests": 2},
    {"name": "Deluxe King", "room_type": "king", "price_per_night": 90, "max_guests": 2},
    {"name": "Suite", "room_type": "suite", "price_per_night": 140, "max_guests": 4},
]

TOURS = [
    {"name": "Hanoi Old Quarter Walking Tour", "city": "Hanoi", "country": "Vietnam",
     "duration_days": 1, "max_participants": 20, "price_per_person": 25,
     "description": "Explore the 36 streets of Hanoi's historic Old Quarter on foot."},
    {"name": "Ha Long Bay Cruise", "city": "Hanoi", "country": "Vietnam",
     "duration_days": 2, "max_participants": 30, "price_per_person": 180,
     "description": "2-day cruise through the UNESCO World Heritage limestone karsts."},
    {"name": "Hoi An Lantern Making Class", "city": "Hoi An", "country": "Vietnam",
     "duration_days": 1, "max_participants": 15, "price_per_person": 35,
     "description": "Learn to craft traditional silk lanterns with local artisans."},
    {"name": "Cu Chi Tunnels Day Trip", "city": "Ho Chi Minh City", "country": "Vietnam",
     "duration_days": 1, "max_participants": 25, "price_per_person": 30,
     "description": "Visit the historic Cu Chi tunnel network used during the Vietnam War."},
]


def _slug(name: str) -> str:
    return name.lower().replace(" ", "-").replace("'", "").replace(",", "")


async def seed(db: AsyncSession) -> None:
    # Idempotency check
    existing = (await db.execute(select(User).where(User.email == "admin@demo.com"))).scalar_one_or_none()
    if existing:
        print("Demo data already seeded — skipping.")
        return

    # Fetch Bronze tier for new users
    bronze_tier = (await db.execute(select(LoyaltyTier).where(LoyaltyTier.name == "Bronze"))).scalar_one_or_none()

    # ── Users ───────────────────────────────────────────────────────────────────
    superadmin = User(id=uuid.uuid4(), email="admin@demo.com", full_name="Demo Admin",
                      hashed_password=hash_password(DEFAULT_PASS), role="admin",
                      loyalty_tier_id=bronze_tier.id if bronze_tier else None)
    partner1 = User(id=uuid.uuid4(), email="partner1@demo.com", full_name="Partner One",
                    hashed_password=hash_password(DEFAULT_PASS), role="partner",
                    loyalty_tier_id=bronze_tier.id if bronze_tier else None)
    partner2 = User(id=uuid.uuid4(), email="partner2@demo.com", full_name="Partner Two",
                    hashed_password=hash_password(DEFAULT_PASS), role="partner",
                    loyalty_tier_id=bronze_tier.id if bronze_tier else None)
    users = [
        User(id=uuid.uuid4(), email=f"user{i}@demo.com", full_name=f"Demo User {i}",
             hashed_password=hash_password(DEFAULT_PASS), role="user",
             loyalty_tier_id=bronze_tier.id if bronze_tier else None)
        for i in range(1, 4)
    ]
    db.add_all([superadmin, partner1, partner2, *users])
    await db.flush()

    # ── Hotels + Rooms ──────────────────────────────────────────────────────────
    hotels = []
    all_rooms = []
    partners = [partner1, partner2, partner1, partner2]
    for i, h_data in enumerate(HOTELS):
        hotel = Hotel(
            id=uuid.uuid4(),
            owner_id=partners[i].id,
            name=h_data["name"],
            slug=_slug(h_data["name"]),
            description=h_data["description"],
            city=h_data["city"],
            country=h_data["country"],
            star_rating=h_data["star_rating"],
            base_price=Decimal(str(h_data["base_price"])),
            images=["https://placehold.co/800x500?text=Hotel"],
        )
        db.add(hotel)
        hotels.append(hotel)

        room_count = 3 if i < 2 else 2
        for rt in ROOM_TYPES[:room_count]:
            room = Room(
                id=uuid.uuid4(),
                hotel_id=hotel.id,
                name=rt["name"],
                room_type=rt["room_type"],
                price_per_night=Decimal(str(rt["price_per_night"])),
                max_guests=rt["max_guests"],
                images=["https://placehold.co/600x400?text=Room"],
            )
            db.add(room)
            all_rooms.append((hotel, room))

    await db.flush()

    # ── Tours + Schedules ───────────────────────────────────────────────────────
    tours = []
    t_partners = [partner1, partner2, partner1, partner2]
    today = date.today()
    for i, t_data in enumerate(TOURS):
        tour = Tour(
            id=uuid.uuid4(),
            owner_id=t_partners[i].id,
            name=t_data["name"],
            slug=_slug(t_data["name"]),
            description=t_data["description"],
            city=t_data["city"],
            country=t_data["country"],
            duration_days=t_data["duration_days"],
            max_participants=t_data["max_participants"],
            price_per_person=Decimal(str(t_data["price_per_person"])),
            images=["https://placehold.co/800x500?text=Tour"],
        )
        db.add(tour)
        tours.append(tour)
        for offset in range(30):
            sched = TourSchedule(
                id=uuid.uuid4(),
                tour_id=tour.id,
                available_date=today + timedelta(days=offset + 1),
                total_slots=t_data["max_participants"],
                booked_slots=0,
            )
            db.add(sched)

    await db.flush()

    # ── Vouchers ────────────────────────────────────────────────────────────────
    db.add(Voucher(
        id=uuid.uuid4(), admin_id=superadmin.id,
        code="DEMO10", name="10% Off Demo", discount_type="percentage",
        discount_value=10, min_order_value=0, max_uses=100,
        valid_from=today, valid_to=today + timedelta(days=365), status="active",
    ))
    db.add(Voucher(
        id=uuid.uuid4(), admin_id=superadmin.id,
        code="FLAT20", name="$20 Flat Discount", discount_type="fixed",
        discount_value=20, min_order_value=50, max_uses=50,
        valid_from=today, valid_to=today + timedelta(days=365), status="active",
    ))
    await db.flush()

    # ── Completed Bookings + Reviews ────────────────────────────────────────────
    demo_user = users[0]
    past_checkin = today - timedelta(days=30)
    past_checkout = today - timedelta(days=27)

    # Booking 1: hotel room — completed
    hotel_room = all_rooms[0][1]
    room_subtotal = Decimal(str(hotel_room.price_per_night)) * 3
    booking1 = Booking(
        id=uuid.uuid4(), user_id=demo_user.id,
        total_price=room_subtotal, status="completed",
        points_earned=int(float(room_subtotal)),
    )
    db.add(booking1)
    await db.flush()

    room_item = BookingItem(
        id=uuid.uuid4(), booking_id=booking1.id,
        item_type=BookingItemType.room.value,
        room_id=hotel_room.id,
        check_in=past_checkin, check_out=past_checkout,
        unit_price=Decimal(str(hotel_room.price_per_night)),
        quantity=1,
        subtotal=room_subtotal,
        status="completed",
    )
    db.add(room_item)

    db.add(Review(
        id=uuid.uuid4(), user_id=demo_user.id,
        hotel_id=all_rooms[0][0].id,
        rating=5, comment="Fantastic stay! Clean rooms and excellent service.",
    ))

    # Booking 2: tour — completed
    tour_date = today - timedelta(days=15)
    demo_tour = tours[0]
    schedule = TourSchedule(
        id=uuid.uuid4(), tour_id=demo_tour.id,
        available_date=tour_date, total_slots=20, booked_slots=2,
    )
    db.add(schedule)
    await db.flush()

    tour_subtotal = Decimal(str(demo_tour.price_per_person)) * 2
    booking2 = Booking(
        id=uuid.uuid4(), user_id=demo_user.id,
        total_price=tour_subtotal, status="completed",
        points_earned=int(float(tour_subtotal)),
    )
    db.add(booking2)
    await db.flush()

    tour_item = BookingItem(
        id=uuid.uuid4(), booking_id=booking2.id,
        item_type=BookingItemType.tour.value,
        tour_schedule_id=schedule.id,
        check_in=tour_date,
        unit_price=Decimal(str(demo_tour.price_per_person)),
        quantity=2,
        subtotal=tour_subtotal,
        status="completed",
    )
    db.add(tour_item)

    db.add(Review(
        id=uuid.uuid4(), user_id=demo_user.id,
        tour_id=demo_tour.id,
        rating=5, comment="Amazing experience! The guide was knowledgeable and fun.",
    ))

    # Booking 3: pending (upcoming) hotel room for user2
    demo_user2 = users[1]
    future_checkin = today + timedelta(days=10)
    future_checkout = today + timedelta(days=13)
    hotel_room2 = all_rooms[3][1]
    room2_subtotal = Decimal(str(hotel_room2.price_per_night)) * 3
    booking3 = Booking(
        id=uuid.uuid4(), user_id=demo_user2.id,
        total_price=room2_subtotal, status="pending",
    )
    db.add(booking3)
    await db.flush()

    db.add(BookingItem(
        id=uuid.uuid4(), booking_id=booking3.id,
        item_type=BookingItemType.room.value,
        room_id=hotel_room2.id,
        check_in=future_checkin, check_out=future_checkout,
        unit_price=Decimal(str(hotel_room2.price_per_night)),
        quantity=1,
        subtotal=room2_subtotal,
        status="pending",
    ))

    await db.flush()
    await db.commit()
    print("✓ Demo data seeded successfully!")
    print(f"  Admin:      admin@demo.com / {DEFAULT_PASS}")
    print(f"  Partners:   partner1@demo.com, partner2@demo.com / {DEFAULT_PASS}")
    print(f"  Users:      user1@demo.com .. user3@demo.com / {DEFAULT_PASS}")
    print(f"  Hotels: {len(hotels)}, Rooms: {len(all_rooms)}, Tours: {len(tours)}")
    print("  Vouchers: DEMO10 (10% off), FLAT20 ($20 flat)")


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as db:
        await seed(db)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
