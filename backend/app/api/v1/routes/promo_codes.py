"""Legacy /promo-codes alias — forwards to the voucher system.

@deprecated — Sprint 2 removes this surface once the frontend switches to
`/api/v1/vouchers/*`. Validation is served by voucher_service; admin CRUD still
writes to the old `promo_codes` table so admins managing legacy rows don't
lose data, but any newly validated/used code comes from `vouchers`.
"""
import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser, CurrentUser
from app.db.session import get_db
from app.models.promo_code import PromoCode
from app.models.voucher import Voucher
from app.schemas.promo_code import (
    PromoCodeCreate,
    PromoCodeResponse,
    PromoCodeUpdate,
    PromoCodeValidateResponse,
)
from app.services import voucher_service
from app.services.voucher_service import VoucherError

router = APIRouter(prefix="/promo-codes", tags=["Promo Codes (legacy)"])


@router.post("/validate", response_model=PromoCodeValidateResponse)
async def validate_promo_code(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
    code: str = Query(...),
    booking_amount: float = Query(..., gt=0),
):
    """Validate against both vouchers and the legacy promo_codes table."""

    try:
        voucher = await voucher_service.validate_voucher(
            db, code, current_user.id, Decimal(str(booking_amount))
        )
        pct = float(voucher.discount_value) if voucher.discount_type == "percentage" else 0.0
        return PromoCodeValidateResponse(
            valid=True,
            discount_percent=pct,
            message=f"Voucher applied ({voucher.discount_value} {voucher.discount_type})",
        )
    except VoucherError:
        pass

    promo = (
        await db.execute(select(PromoCode).where(PromoCode.code == code))
    ).scalar_one_or_none()
    if not promo or not promo.is_active:
        return PromoCodeValidateResponse(valid=False, message="Invalid promo code")
    if promo.expires_at and promo.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        return PromoCodeValidateResponse(valid=False, message="Promo code has expired")
    if promo.current_uses >= promo.max_uses:
        return PromoCodeValidateResponse(valid=False, message="Promo code usage limit reached")
    if booking_amount < float(promo.min_booking_amount):
        return PromoCodeValidateResponse(
            valid=False, message=f"Minimum booking amount is ${promo.min_booking_amount}"
        )

    return PromoCodeValidateResponse(
        valid=True,
        discount_percent=float(promo.discount_percent),
        message=f"{promo.discount_percent}% discount applied",
    )


@router.post("", response_model=PromoCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_promo_code(
    data: PromoCodeCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    existing = await db.execute(select(PromoCode).where(PromoCode.code == data.code))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Code already exists")

    promo = PromoCode(**data.model_dump())
    db.add(promo)
    await db.flush()
    await db.refresh(promo)
    return promo


@router.get("")
async def list_promo_codes(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = select(PromoCode)
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(PromoCode.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    items = (await db.execute(query)).scalars().all()

    return {
        "items": [PromoCodeResponse.model_validate(p).model_dump(mode="json") for p in items],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    }


@router.patch("/{promo_id}", response_model=PromoCodeResponse)
async def update_promo_code(
    promo_id: uuid.UUID,
    data: PromoCodeUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(PromoCode).where(PromoCode.id == promo_id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promo code not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(promo, field, value)
    await db.flush()
    await db.refresh(promo)
    return promo


@router.delete("/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promo_code(
    promo_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    result = await db.execute(select(PromoCode).where(PromoCode.id == promo_id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promo code not found")
    await db.delete(promo)
    await db.flush()
