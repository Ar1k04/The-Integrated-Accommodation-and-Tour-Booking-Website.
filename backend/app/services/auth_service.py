import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.loyalty_tier import LoyaltyTier
from app.models.user import User
from app.schemas.user import UserCreate


async def register_user(db: AsyncSession, data: UserCreate) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise ValueError("Email already registered")

    # Lowest-threshold tier (typically Bronze, min_points=0); None if tiers unseeded.
    bronze = (
        await db.execute(
            select(LoyaltyTier).order_by(LoyaltyTier.min_points.asc()).limit(1)
        )
    ).scalar_one_or_none()

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        phone=data.phone,
        loyalty_tier_id=bronze.id if bronze else None,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise ValueError("Invalid email or password")
    if not user.is_active:
        raise ValueError("Account is deactivated")
    return user


def issue_tokens(user_id: uuid.UUID, role: str) -> tuple[str, str]:
    access = create_access_token(user_id, extra={"role": role})
    refresh = create_refresh_token(user_id)
    return access, refresh


async def blacklist_token(redis, jti: str, ttl_seconds: int | None = None) -> None:
    ttl = ttl_seconds or settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    await redis.setex(f"blacklist:{jti}", ttl, "1")


async def is_token_blacklisted(redis, jti: str) -> bool:
    return await redis.exists(f"blacklist:{jti}") > 0


async def validate_refresh_token(redis, token: str) -> dict:
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise ValueError("Invalid refresh token") from exc

    if payload.get("type") != "refresh":
        raise ValueError("Not a refresh token")

    jti = payload.get("jti")
    if not jti:
        raise ValueError("Malformed refresh token")

    if await is_token_blacklisted(redis, jti):
        raise ValueError("Token has been revoked")

    return payload


def create_password_reset_token(user_id: uuid.UUID) -> str:
    from jose import jwt as jose_jwt

    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {"sub": str(user_id), "exp": expire, "type": "password_reset"}
    return jose_jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_password_reset_token(token: str) -> str:
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise ValueError("Invalid or expired reset token") from exc

    if payload.get("type") != "password_reset":
        raise ValueError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Malformed token")
    return user_id


async def reset_user_password(db: AsyncSession, user_id: str, new_password: str) -> None:
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")
    user.hashed_password = hash_password(new_password)
    await db.flush()
