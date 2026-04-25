"""Tests for email service — verifies send logic and graceful degradation."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal

from app.services import email_service
from app.core.config import settings


def _make_booking(discount_amount=0.0):
    """Build a minimal booking-like object with items."""
    booking = MagicMock()
    booking.id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    booking.total_price = Decimal("100.00")
    booking.discount_amount = Decimal(str(discount_amount))
    booking.items = []
    return booking


@pytest.mark.asyncio
async def test_send_email_skips_guest_placeholder():
    """Sending to guest@example.com should return False without calling aiosmtplib."""
    with patch("app.services.email_service.aiosmtplib") as mock_smtp:
        result = await email_service.send_email(
            to="guest@example.com",
            subject="Test",
            html_body="<p>Test</p>",
        )
    assert result is False
    mock_smtp.send.assert_not_called()


@pytest.mark.asyncio
async def test_send_email_skips_when_smtp_user_empty(monkeypatch):
    """If SMTP_USER is not configured, email should be silently skipped."""
    monkeypatch.setattr(settings, "SMTP_USER", "")
    with patch("app.services.email_service.aiosmtplib") as mock_smtp:
        result = await email_service.send_email(
            to="user@example.com",
            subject="Test",
            html_body="<p>Test</p>",
        )
    assert result is False
    mock_smtp.send.assert_not_called()


@pytest.mark.asyncio
async def test_send_email_returns_true_on_success(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "test@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "testpassword")

    with patch("app.services.email_service.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock(return_value=None)
        result = await email_service.send_email(
            to="user@example.com",
            subject="Booking Confirmed",
            html_body="<p>Confirmed</p>",
        )

    assert result is True
    mock_smtp.send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_returns_false_on_smtp_error(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "test@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "testpassword")

    with patch("app.services.email_service.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock(side_effect=Exception("SMTP connection refused"))
        result = await email_service.send_email(
            to="user@example.com",
            subject="Booking Confirmed",
            html_body="<p>Confirmed</p>",
        )

    assert result is False  # should NOT raise


@pytest.mark.asyncio
async def test_send_booking_confirmation_builds_message(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "test@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "testpassword")

    booking = _make_booking(discount_amount=10.0)

    with patch("app.services.email_service.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock(return_value=None)
        result = await email_service.send_booking_confirmation(booking, "customer@example.com")

    assert result is True
    call_args = mock_smtp.send.call_args
    msg = call_args.args[0] if call_args.args else call_args.kwargs.get("message")
    assert msg is not None
    assert "Booking Confirmed" in msg["Subject"]


@pytest.mark.asyncio
async def test_send_booking_cancellation_builds_message(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_USER", "test@gmail.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "testpassword")

    booking = _make_booking()

    with patch("app.services.email_service.aiosmtplib") as mock_smtp:
        mock_smtp.send = AsyncMock(return_value=None)
        result = await email_service.send_booking_cancellation(booking, "customer@example.com")

    assert result is True
    call_args = mock_smtp.send.call_args
    msg = call_args.args[0] if call_args.args else call_args.kwargs.get("message")
    assert msg is not None
    assert "Cancelled" in msg["Subject"]
