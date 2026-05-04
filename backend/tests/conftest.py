"""
Pytest fixtures for async testing with SQLAlchemy + httpx.

Uses a dedicated PostgreSQL test database (travel_test_db) so JSONB and other
Postgres-specific types work correctly. The full schema is created before each
test and dropped after, giving full isolation without requiring a separate schema.
"""
import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://travel_user:travel_password@postgres:5432/travel_test_db",
)

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db():
        yield db_session

    mock_redis = AsyncMock()
    mock_redis.exists.return_value = 0
    mock_redis.setex.return_value = True
    # Soft-lock: NX acquire always succeeds; GET returns None (no existing lock);
    # Lua release returns 1 (released); helpers succeed.
    mock_redis.set.return_value = True
    mock_redis.get.return_value = None
    mock_redis.eval.return_value = 1
    mock_redis.expire.return_value = True
    mock_redis.delete.return_value = 1

    app.dependency_overrides[get_db] = _override_get_db
    app.state.redis = mock_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    from app.models.user import User
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        hashed_password=hash_password("TestPassword1!"),
        full_name="Test User",
        role="user",
        is_active=True,
        loyalty_points=0,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession):
    """Full platform admin (formerly superadmin). Can access user management."""
    from app.models.user import User
    user = User(
        id=uuid.uuid4(),
        email="admin@example.com",
        hashed_password=hash_password("AdminPassword1!"),
        full_name="Admin User",
        role="admin",
        is_active=True,
        loyalty_points=0,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def partner_user(db_session: AsyncSession):
    """Partner user (hotel/tour owner). Can manage own listings."""
    from app.models.user import User
    user = User(
        id=uuid.uuid4(),
        email="partner@example.com",
        hashed_password=hash_password("PartnerPassword1!"),
        full_name="Partner User",
        role="partner",
        is_active=True,
        loyalty_points=0,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def user_token(test_user):
    return create_access_token(test_user.id, extra={"role": test_user.role})


@pytest_asyncio.fixture
async def admin_token(admin_user):
    return create_access_token(admin_user.id, extra={"role": admin_user.role})


@pytest_asyncio.fixture
async def partner_token(partner_user):
    return create_access_token(partner_user.id, extra={"role": partner_user.role})


@pytest_asyncio.fixture
async def test_hotel(db_session: AsyncSession):
    from app.models.hotel import Hotel
    hotel = Hotel(
        id=uuid.uuid4(),
        name="Test Hotel",
        slug="test-hotel",
        city="Paris",
        country="France",
        base_price=150.00,
        star_rating=4,
    )
    db_session.add(hotel)
    await db_session.flush()
    await db_session.refresh(hotel)
    return hotel


@pytest_asyncio.fixture
async def test_room(db_session: AsyncSession, test_hotel):
    from app.models.room import Room
    room = Room(
        id=uuid.uuid4(),
        hotel_id=test_hotel.id,
        name="Deluxe Double",
        room_type="double",
        price_per_night=200.00,
        total_quantity=2,
        max_guests=3,
    )
    db_session.add(room)
    await db_session.flush()
    await db_session.refresh(room)
    return room


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
