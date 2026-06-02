import math
import uuid
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import AdminUser, CurrentUser, StaffUser
from app.db.session import get_db
from app.models.booking import Booking
from app.models.user import User
from app.models.voucher import Voucher, VoucherLiteAPISyncStatus
from app.models.voucher_usage import VoucherUsage
from app.schemas.voucher import (
    PublicVoucherResponse,
    VoucherCreate,
    VoucherResponse,
    VoucherStatusUpdate,
    VoucherUpdate,
    VoucherUsageDetail,
    VoucherUsagesListMeta,
    VoucherUsagesListResponse,
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


@router.get("/available", response_model=list[PublicVoucherResponse])
async def list_available_vouchers(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: CurrentUser,
):
    """Vouchers the current customer can still redeem (UC_VIEW_VOUCHER)."""
    vouchers = await voucher_service.list_available_for_user(db, current_user.id)
    return [PublicVoucherResponse.model_validate(v) for v in vouchers]


def _enforce_sync_disabled_for_non_hotel(payload: dict) -> dict:
    """Tour/flight vouchers cannot be synced to LiteAPI."""
    if payload.get("applicable_to") in ("tour", "flight"):
        payload["liteapi_sync_status"] = VoucherLiteAPISyncStatus.disabled.value
    return payload


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

    if data.valid_to < data.valid_from:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="valid_to must be on or after valid_from",
        )

    payload = data.model_dump()
    payload = _enforce_sync_disabled_for_non_hotel(payload)
    voucher = Voucher(admin_id=current_user.id, **payload)
    db.add(voucher)
    await db.flush()
    # Best-effort sync; never blocks creation.
    await voucher_service.sync_voucher_to_liteapi(db, voucher)
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


# --- Aggregated usage history (admin only) ------------------------------------
# Defined BEFORE /{voucher_id} so FastAPI does not interpret "usages" as a UUID.

def _build_usage_query(
    *,
    voucher_id: uuid.UUID | None,
    date_from: date_type | None,
    date_to: date_type | None,
    user_email: str | None,
    voucher_code: str | None,
):
    """Shared query builder for usage history endpoints."""
    query = (
        select(
            VoucherUsage.id,
            VoucherUsage.voucher_id,
            Voucher.code.label("voucher_code"),
            Voucher.name.label("voucher_name"),
            VoucherUsage.user_id,
            User.email.label("user_email"),
            User.full_name.label("user_full_name"),
            VoucherUsage.booking_id,
            Booking.status.label("booking_status"),
            Booking.total_price.label("booking_total"),
            Booking.discount_amount.label("discount_amount"),
            VoucherUsage.used_at,
        )
        .join(Voucher, Voucher.id == VoucherUsage.voucher_id)
        .join(User, User.id == VoucherUsage.user_id)
        .join(Booking, Booking.id == VoucherUsage.booking_id)
    )
    if voucher_id is not None:
        query = query.where(VoucherUsage.voucher_id == voucher_id)
    if date_from is not None:
        query = query.where(VoucherUsage.used_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        query = query.where(VoucherUsage.used_at <= datetime.combine(date_to, datetime.max.time()))
    if user_email:
        query = query.where(User.email.ilike(f"%{user_email}%"))
    if voucher_code:
        query = query.where(Voucher.code.ilike(f"%{voucher_code}%"))
    return query


@router.get("/usages", response_model=VoucherUsagesListResponse)
async def list_all_usages(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    date_from: date_type | None = Query(None),
    date_to: date_type | None = Query(None),
    user_email: str | None = Query(None, max_length=255),
    voucher_code: str | None = Query(None, max_length=50),
):
    """Aggregated voucher usage history for admin dashboard."""
    base = _build_usage_query(
        voucher_id=None,
        date_from=date_from,
        date_to=date_to,
        user_email=user_email,
        voucher_code=voucher_code,
    )

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    sum_q = select(func.coalesce(func.sum(Booking.discount_amount), 0)).select_from(
        base.subquery()
    )
    total_discount = float((await db.execute(sum_q)).scalar() or 0)

    rows = (
        await db.execute(
            base.order_by(VoucherUsage.used_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()

    items = [
        VoucherUsageDetail(
            id=r.id,
            voucher_id=r.voucher_id,
            voucher_code=r.voucher_code,
            voucher_name=r.voucher_name,
            user_id=r.user_id,
            user_email=r.user_email,
            user_full_name=r.user_full_name,
            booking_id=r.booking_id,
            booking_status=r.booking_status,
            booking_total=float(r.booking_total or 0),
            discount_amount=float(r.discount_amount or 0),
            used_at=r.used_at,
        )
        for r in rows
    ]

    return VoucherUsagesListResponse(
        items=items,
        meta=VoucherUsagesListMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total / per_page) if total else 0,
            total_discount_amount=total_discount,
        ),
    )


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


@router.get("/{voucher_id}/usages", response_model=VoucherUsagesListResponse)
async def list_voucher_usages(
    voucher_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    date_from: date_type | None = Query(None),
    date_to: date_type | None = Query(None),
    user_email: str | None = Query(None, max_length=255),
):
    """Per-voucher usage history. Owner (staff) or any admin may view."""
    voucher = (
        await db.execute(select(Voucher).where(Voucher.id == voucher_id))
    ).scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found")
    if current_user.role != "admin" and voucher.admin_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your voucher")

    base = _build_usage_query(
        voucher_id=voucher_id,
        date_from=date_from,
        date_to=date_to,
        user_email=user_email,
        voucher_code=None,
    )

    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    sum_q = select(func.coalesce(func.sum(Booking.discount_amount), 0)).select_from(
        base.subquery()
    )
    total_discount = float((await db.execute(sum_q)).scalar() or 0)

    rows = (
        await db.execute(
            base.order_by(VoucherUsage.used_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).all()

    items = [
        VoucherUsageDetail(
            id=r.id,
            voucher_id=r.voucher_id,
            voucher_code=r.voucher_code,
            voucher_name=r.voucher_name,
            user_id=r.user_id,
            user_email=r.user_email,
            user_full_name=r.user_full_name,
            booking_id=r.booking_id,
            booking_status=r.booking_status,
            booking_total=float(r.booking_total or 0),
            discount_amount=float(r.discount_amount or 0),
            used_at=r.used_at,
        )
        for r in rows
    ]

    return VoucherUsagesListResponse(
        items=items,
        meta=VoucherUsagesListMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total / per_page) if total else 0,
            total_discount_amount=total_discount,
        ),
    )


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

    payload = data.model_dump(exclude_unset=True)

    # Integrity rules:
    # - guest_id cannot change after the voucher has been used (would orphan VoucherUsage records).
    # - discount_value/type/applicable_to cannot change once synced (would diverge from supplier).
    if "guest_id" in payload and voucher.used_count > 0 and payload["guest_id"] != voucher.guest_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot change guest_id after voucher has been used",
        )
    if voucher.liteapi_sync_status == VoucherLiteAPISyncStatus.synced.value:
        for locked in ("discount_value", "discount_type", "applicable_to", "currency"):
            if locked in payload and payload[locked] != getattr(voucher, locked):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot change {locked} on a synced voucher; unsync from LiteAPI first",
                )

    for field, value in payload.items():
        setattr(voucher, field, value)
    await db.flush()
    # Re-sync if this voucher is mirrored to LiteAPI.
    if voucher.liteapi_sync_status in (
        VoucherLiteAPISyncStatus.synced.value,
        VoucherLiteAPISyncStatus.failed.value,
    ):
        await voucher_service.sync_voucher_to_liteapi(db, voucher)
    await db.refresh(voucher)
    return voucher


@router.patch("/{voucher_id}/status", response_model=VoucherResponse)
async def toggle_voucher_status(
    voucher_id: uuid.UUID,
    data: VoucherStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    """Quick activate/disable toggle, mirrors LiteAPI PUT /vouchers/{id}/status."""
    voucher = (
        await db.execute(select(Voucher).where(Voucher.id == voucher_id))
    ).scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found")
    if current_user.role != "admin" and voucher.admin_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your voucher")
    voucher.status = data.status
    await db.flush()
    # Mirror the toggle to LiteAPI if synced (uses the lightweight status endpoint).
    if (
        voucher.liteapi_sync_status == VoucherLiteAPISyncStatus.synced.value
        and voucher.liteapi_voucher_id
    ):
        try:
            await voucher_service.liteapi_service.set_voucher_status(
                voucher.liteapi_voucher_id,
                "active" if data.status == "active" else "inactive",
            )
        except voucher_service.liteapi_service.LiteAPIError as exc:
            voucher.liteapi_sync_status = VoucherLiteAPISyncStatus.failed.value
            voucher.liteapi_sync_error = str(exc)[:1000]
            await db.flush()
    await db.refresh(voucher)
    return voucher


@router.post("/{voucher_id}/sync-liteapi", response_model=VoucherResponse)
async def sync_voucher_liteapi(
    voucher_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: StaffUser,
):
    """Manually retry / force sync the voucher to LiteAPI."""
    voucher = (
        await db.execute(select(Voucher).where(Voucher.id == voucher_id))
    ).scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found")
    if current_user.role != "admin" and voucher.admin_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your voucher")
    await voucher_service.sync_voucher_to_liteapi(db, voucher)
    # Commit the sync result (success OR recorded failure) BEFORE potentially
    # raising — otherwise get_db's exception handler rolls back the failure
    # state and the UI never sees 'failed' or the captured error.
    await db.commit()
    await db.refresh(voucher)
    if voucher.liteapi_sync_status == VoucherLiteAPISyncStatus.failed.value:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=voucher.liteapi_sync_error or "LiteAPI sync failed",
        )
    return voucher


@router.delete("/{voucher_id}/sync-liteapi", response_model=VoucherResponse)
async def unsync_voucher_liteapi(
    voucher_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: AdminUser,
):
    """Remove the voucher from LiteAPI but keep the local record. Admin only."""
    voucher = (
        await db.execute(select(Voucher).where(Voucher.id == voucher_id))
    ).scalar_one_or_none()
    if not voucher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Voucher not found")
    try:
        await voucher_service.unsync_voucher_from_liteapi(db, voucher)
    except voucher_service.liteapi_service.LiteAPIError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))
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
    # If synced, drop the supplier copy first to avoid orphans.
    if voucher.liteapi_voucher_id:
        try:
            await voucher_service.unsync_voucher_from_liteapi(db, voucher)
        except voucher_service.liteapi_service.LiteAPIError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Cannot delete: LiteAPI unsync failed — {exc}",
            )
    await db.delete(voucher)
    await db.flush()
