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
from app.models.user import User, UserRole
from app.schemas.user import UserCreate


async def _provision_new_user(
    db: AsyncSession,
    *,
    email: str,
    full_name: str,
    role: str,
    hashed_password: str | None = None,
    phone: str | None = None,
    google_id: str | None = None,
    avatar_url: str | None = None,
) -> User:
    """Create a User row with loyalty tier + Stripe customer.

    Shared by password registration and Google sign-up. The caller is
    responsible for the email-uniqueness check.
    """
    # Lowest-threshold tier (typically Bronze, min_points=0); None if tiers unseeded.
    bronze = (
        await db.execute(
            select(LoyaltyTier).order_by(LoyaltyTier.min_points.asc()).limit(1)
        )
    ).scalar_one_or_none()

    user = User(
        email=email,
        hashed_password=hashed_password,
        google_id=google_id,
        full_name=full_name,
        phone=phone,
        avatar_url=avatar_url,
        role=role,
        # Partners must be approved before using the dashboard. For password
        # signups this is unlocked via the email-confirmation link; admins can
        # still override via the admin API.
        partner_status="pending" if role == UserRole.partner.value else None,
        loyalty_tier_id=bronze.id if bronze else None,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Best-effort Stripe Customer creation. Outage must not block signup —
    # the customer will be created lazily on first PaymentIntent.
    from app.services.payment_service import get_or_create_stripe_customer
    await get_or_create_stripe_customer(user)
    await db.flush()
    return user


async def register_user(db: AsyncSession, data: UserCreate) -> User:
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise ValueError("Email already registered")

    return await _provision_new_user(
        db,
        email=data.email,
        full_name=data.full_name,
        role=data.role,
        hashed_password=hash_password(data.password),
        phone=data.phone,
    )


async def _verify_google_access_token(access_token: str) -> dict:
    """Verify a Google OAuth access token and return its profile claims.

    Two-step check: ``tokeninfo`` confirms the token was minted for THIS app
    (``aud == GOOGLE_CLIENT_ID`` — prevents token-substitution), then
    ``userinfo`` returns the profile (sub/email/name/picture). Raises
    ValueError if either step fails.
    """
    import httpx

    async with httpx.AsyncClient(timeout=10) as http:
        ti = await http.get(
            "https://oauth2.googleapis.com/tokeninfo", params={"access_token": access_token}
        )
        if ti.status_code != 200:
            raise ValueError("Invalid Google token")
        if ti.json().get("aud") != settings.GOOGLE_CLIENT_ID:
            raise ValueError("Google token has wrong audience")

        ui = await http.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if ui.status_code != 200:
            raise ValueError("Could not fetch Google profile")
        return ui.json()


async def authenticate_google(
    db: AsyncSession, access_token: str, requested_role: str = "user"
) -> tuple[User, bool]:
    """Verify a Google access token and return (user, created_new).

    Resolution order: existing google_id → existing email (auto-link) → create.
    ``created_new`` lets the caller trigger partner email-confirmation only for
    brand-new partner accounts. Raises ValueError on an invalid token.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise ValueError("Google login is not configured")

    try:
        claims = await _verify_google_access_token(access_token)
    except ValueError:
        raise
    except Exception as exc:  # network/parse — keep message opaque
        raise ValueError("Invalid Google token") from exc

    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise ValueError("Google token missing required claims")
    if not claims.get("email_verified", False):
        raise ValueError("Google account email is not verified")

    # 1) Returning Google user.
    user = (
        await db.execute(select(User).where(User.google_id == sub))
    ).scalar_one_or_none()
    if user:
        if not user.is_active:
            raise ValueError("Account is deactivated")
        return user, False

    # 2) Existing email → auto-link Google to it.
    user = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user:
        if not user.is_active:
            raise ValueError("Account is deactivated")
        user.google_id = sub
        if not user.avatar_url and claims.get("picture"):
            user.avatar_url = claims.get("picture")
        await db.flush()
        return user, False

    # 3) Brand-new account.
    role = requested_role if requested_role in ("user", "partner") else "user"
    user = await _provision_new_user(
        db,
        email=email,
        full_name=claims.get("name") or email.split("@")[0],
        role=role,
        google_id=sub,
        avatar_url=claims.get("picture"),
    )
    return user, True


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user and user.hashed_password is None:
        # Google-only account — no local password to verify against.
        raise ValueError("This account uses Google sign-in")
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


def _password_fingerprint(hashed_password: str | None) -> str:
    """Short, stable fingerprint of a user's password hash.

    Embedded in the reset token so the token becomes single-use: once the
    password is reset the hash (and thus this fingerprint) changes, and the
    original token no longer matches. Empty for OAuth users with no local hash.
    """
    import hashlib

    return hashlib.sha256((hashed_password or "").encode("utf-8")).hexdigest()[:16]


def create_password_reset_token(user: User) -> str:
    from jose import jwt as jose_jwt

    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {
        "sub": str(user.id),
        "exp": expire,
        "type": "password_reset",
        "pf": _password_fingerprint(user.hashed_password),
    }
    return jose_jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def verify_password_reset_token(db: AsyncSession, token: str) -> User:
    """Validate a single-use reset token and return the row-locked User.

    The user row is loaded with ``SELECT ... FOR UPDATE`` so two concurrent
    reset requests serialize: the first commits a new hash, the second re-reads
    the locked row and sees a changed fingerprint, so it is rejected. The caller
    must reset the password on the returned object within the same transaction.
    """
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise ValueError("Invalid or expired reset token") from exc

    if payload.get("type") != "password_reset":
        raise ValueError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Malformed token")

    fingerprint = payload.get("pf")
    if not fingerprint:
        # Legacy tokens minted before single-use enforcement carry no
        # fingerprint and must be rejected so they cannot bypass the check.
        raise ValueError("Invalid or expired reset token")

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(user_id)).with_for_update()
    )
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User not found")

    if fingerprint != _password_fingerprint(user.hashed_password):
        raise ValueError("Invalid or expired reset token")

    return user


async def reset_user_password(db: AsyncSession, user: User, new_password: str) -> None:
    user.hashed_password = hash_password(new_password)
    await db.flush()


async def change_user_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> None:
    """Change the password of an already-authenticated user.

    Requires the correct current password. Users created via Google OAuth may
    have no local password set yet, in which case they should use the
    forgot-password flow instead.
    """
    if not user.hashed_password:
        raise ValueError(
            "No password is set for this account. Use the reset-password flow."
        )
    if not verify_password(current_password, user.hashed_password):
        raise ValueError("Current password is incorrect")
    if verify_password(new_password, user.hashed_password):
        raise ValueError("New password must be different from the current password")
    user.hashed_password = hash_password(new_password)
    await db.flush()


def create_partner_confirm_token(user_id: uuid.UUID) -> str:
    from jose import jwt as jose_jwt

    expire = datetime.now(timezone.utc) + timedelta(days=7)
    payload = {"sub": str(user_id), "exp": expire, "type": "partner_confirm"}
    return jose_jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_partner_confirm_token(token: str) -> str:
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise ValueError("Invalid or expired confirmation link") from exc

    if payload.get("type") != "partner_confirm":
        raise ValueError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Malformed token")
    return user_id


async def approve_partner(db: AsyncSession, user_id: str) -> User:
    """Mark a pending partner as approved (idempotent for already-approved).

    Raises ValueError if the user does not exist or is not a partner.
    """
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or user.role != UserRole.partner.value:
        raise ValueError("Partner account not found")
    if user.partner_status != "approved":
        user.partner_status = "approved"
        await db.flush()
    return user
