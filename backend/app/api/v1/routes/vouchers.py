import math
import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import StaffUser, CurrentUser
from app.db.session import get_db
from app.models.voucher import Voucher
from app.schemas.voucher import (
    VoucherCreate,
    VoucherResponse,
    VoucherUpdate,
    VoucherValidateRequest,
    VoucherValidateResponse,
)
from app.services import voucher_service
from app.services.voucher_service import VoucherError

router = APIRouter(prefix="/vouchers", tags=["Vouchers"])


@router.post("/validate", response_model=VoucherValidateResponse)
async def validate_voucher(
    data: VoucherValidateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    try:
        voucher = await voucher_service.validate_voucher(
            db, data.code, current_user.id, Decimal(str(data.subtotal))
        )
    except VoucherError as exc:
        return VoucherValidateResponse(valid=False, message=str(exc))

    discount = voucher_service.compute_discount(voucher, Decimal(str(data.subtotal)))
    return VoucherValidateResponse(
        valid=True,
        code=voucher.code,
        discount_type=voucher.discount_type,
        discount_value=float(voucher.discount_value),
        discount_amount=float(discount),
        message=f"Voucher applied ({voucher.discount_value} {voucher.discount_type})",
    )


@router.post("", response_model=VoucherResponse, status_code=status.HTTP_201_CREATED)
async def create_voucher(
    data: VoucherCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    existing = (
        await db.execute(select(Voucher).where(Voucher.code == data.code))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Voucher code already exists")

    voucher = Voucher(admin_id=current_user.id, **data.model_dump())
    db.add(voucher)
    await db.flush()
    await db.refresh(voucher)
    return voucher


@router.get("")
async def list_vouchers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    query = select(Voucher)
    if current_user.role != "admin":
        query = query.where(Voucher.admin_id == current_user.id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    query = query.order_by(Voucher.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    items = (await db.execute(query)).scalars().all()

    return {
        "items": [VoucherResponse.model_validate(v).model_dump(mode="json") for v in items],
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total / per_page) if total else 0,
        },
    }


@router.get("/{voucher_id}", response_model=VoucherResponse)
async def get_voucher(
    voucher_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    voucher = (
        await db.execute(select(Voucher).where(Voucher.id == voucher_id))
    ).scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found")
    if current_user.role != "admin" and voucher.admin_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your voucher")
    return voucher


@router.patch("/{voucher_id}", response_model=VoucherResponse)
async def update_voucher(
    voucher_id: uuid.UUID,
    data: VoucherUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    voucher = (
        await db.execute(select(Voucher).where(Voucher.id == voucher_id))
    ).scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found")
    if current_user.role != "admin" and voucher.admin_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your voucher")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(voucher, field, value)
    await db.flush()
    await db.refresh(voucher)
    return voucher


@router.delete("/{voucher_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_voucher(
    voucher_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    voucher = (
        await db.execute(select(Voucher).where(Voucher.id == voucher_id))
    ).scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found")
    if current_user.role != "admin" and voucher.admin_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your voucher")
    await db.delete(voucher)
    await db.flush()
