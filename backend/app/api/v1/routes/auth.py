from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, File, HTTPException, Request, Response, UploadFile, status
from app.core.rate_limit import limiter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    PartnerConfirmRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.user import SelfProfileUpdate, UserCreate, UserResponse
from app.models.user import UserRole
from app.services.email_service import send_partner_confirmation, send_password_reset
from app.services.auth_service import (
    approve_partner,
    authenticate_google,
    authenticate_user,
    blacklist_token,
    change_user_password,
    create_partner_confirm_token,
    create_password_reset_token,
    issue_tokens,
    register_user,
    reset_user_password,
    validate_refresh_token,
    verify_partner_confirm_token,
    verify_password_reset_token,
)

router = APIRouter(prefix="/auth", tags=["Auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=REFRESH_MAX_AGE,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path="/api/v1/auth")


def _queue_partner_confirmation(background_tasks: BackgroundTasks, user) -> None:
    """Email a pending partner a link to confirm their account."""
    token = create_partner_confirm_token(user.id)
    confirm_link = f"{settings.FRONTEND_URL}/partner/confirm?token={token}"
    background_tasks.add_task(_send_partner_confirm_email, user.email, confirm_link)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    response: Response,
    data: UserCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        user = await register_user(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    # Partners must confirm their email before the dashboard unlocks.
    if user.role == UserRole.partner.value:
        _queue_partner_confirmation(background_tasks, user)

    access, refresh = issue_tokens(user.id, user.role)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access)


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    data: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        user = await authenticate_user(db, data.email, data.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    access, refresh = issue_tokens(user.id, user.role)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access)


@router.post("/google", response_model=TokenResponse)
@limiter.limit("5/minute")
async def google_login(
    request: Request,
    response: Response,
    data: GoogleAuthRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        user, created = await authenticate_google(db, data.access_token, data.role)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    # A brand-new partner account still goes through email confirmation.
    if created and user.role == UserRole.partner.value:
        _queue_partner_confirmation(background_tasks, user)

    access, refresh = issue_tokens(user.id, user.role)
    _set_refresh_cookie(response, refresh)
    return TokenResponse(access_token=access)


@router.post("/partner/confirm", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def confirm_partner(
    request: Request,
    data: PartnerConfirmRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        user_id = verify_partner_confirm_token(data.token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        await approve_partner(db, user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return {"message": "Partner account confirmed. You can now sign in."}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None),
):
    if refresh_token:
        try:
            payload = await validate_refresh_token(request.app.state.redis, refresh_token)
            await blacklist_token(request.app.state.redis, payload["jti"])
        except ValueError:
            pass
    _clear_refresh_cookie(response)


@router.post("/token/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: str | None = Cookie(None),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    redis = request.app.state.redis
    try:
        payload = await validate_refresh_token(redis, refresh_token)
    except ValueError as exc:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    await blacklist_token(redis, payload["jti"])

    import uuid
    from sqlalchemy import select
    from app.models.user import User

    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access, new_refresh = issue_tokens(user.id, user.role)
    _set_refresh_cookie(response, new_refresh)
    return TokenResponse(access_token=access)


@router.post("/password/forgot", status_code=status.HTTP_200_OK)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user:
        token = create_password_reset_token(user.id)
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        background_tasks.add_task(_send_reset_email, user.email, reset_link)

    return {"message": "If the email exists, a reset link has been sent."}


@router.post("/password/reset", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        user_id = verify_password_reset_token(data.token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    try:
        await reset_user_password(db, user_id, data.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return {"message": "Password has been reset successfully."}


@router.post("/password/change", status_code=status.HTTP_200_OK)
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user=Depends(get_current_user),
):
    try:
        await change_user_password(
            db, current_user, data.current_password, data.new_password
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return {"message": "Password has been changed successfully."}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: SelfProfileUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user=Depends(get_current_user),
):
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    await db.flush()
    await db.refresh(current_user)
    return current_user


@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user=Depends(get_current_user),
    file: UploadFile = File(...),
):
    from app.services.cloudinary_service import upload_image

    url = await upload_image(file, folder="avatars")
    current_user.avatar_url = url
    await db.flush()
    await db.refresh(current_user)
    return current_user


async def _send_reset_email(email: str, reset_link: str) -> None:
    import logging
    sent = await send_password_reset(email, reset_link)
    if not sent:
        logging.getLogger(__name__).info("Reset email to %s: %s", email, reset_link)


async def _send_partner_confirm_email(email: str, confirm_link: str) -> None:
    import logging
    sent = await send_partner_confirmation(email, confirm_link)
    if not sent:
        logging.getLogger(__name__).info("Partner confirm email to %s: %s", email, confirm_link)
