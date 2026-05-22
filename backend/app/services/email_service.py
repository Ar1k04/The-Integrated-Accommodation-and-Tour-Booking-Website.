"""Async SMTP email notifications using aiosmtplib."""
import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html_body: str) -> bool:
    if not settings.SMTP_USER or to == "guest@example.com":
        return False

    msg = EmailMessage()
    msg["From"] = settings.FROM_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("Please view this email in an HTML-capable email client.")
    msg.add_alternative(html_body, subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER,
            password=settings.SMTP_PASSWORD,
            start_tls=True,
        )
        return True
    except Exception as exc:
        logger.warning("SMTP send to %s failed: %s", to, exc)
        return False


async def send_admin_alert(subject: str, body: str) -> bool:
    """Send an operations alert to STRIPE_ADMIN_ALERT_EMAIL (no-op if unset)."""
    if not settings.STRIPE_ADMIN_ALERT_EMAIL:
        logger.info("Admin alert (no recipient configured): %s — %s", subject, body)
        return False
    html = f"<p>{body}</p>"
    return await send_email(settings.STRIPE_ADMIN_ALERT_EMAIL, f"[Alert] {subject}", html)


def _items_html(items) -> str:
    rows = []
    for item in items:
        if item.item_type == "room":
            label = "Hotel Stay"
            detail = f"{item.check_in} — {item.check_out}"
            if item.liteapi_booking_id:
                detail += f" (Ref: {item.liteapi_booking_id})"
        elif item.item_type == "tour":
            label = "Tour"
            detail = str(item.check_in or "")
            if item.viator_booking_ref:
                detail += f" (Ref: {item.viator_booking_ref})"
        elif item.item_type == "flight":
            fb = item.flight_booking
            if fb:
                label = f"Flight {fb.departure_airport} → {fb.arrival_airport}"
                detail = str(fb.departure_at.strftime("%b %d, %Y") if fb.departure_at else "")
                if fb.duffel_booking_ref:
                    detail += f" (Ref: {fb.duffel_booking_ref})"
            else:
                label, detail = "Flight", ""
        else:
            label, detail = item.item_type.title(), ""

        rows.append(
            f"<tr>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0'>{label}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;color:#666'>{detail}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #f0f0f0;text-align:right;font-weight:bold'>"
            f"${float(item.subtotal):.2f}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


async def send_password_reset(to: str, reset_link: str) -> bool:
    html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;padding:0">
<div style="background:#1a1a2e;color:white;padding:24px;border-radius:8px 8px 0 0">
  <h1 style="margin:0;font-size:22px">Reset Your Password</h1>
  <p style="margin:4px 0 0;opacity:0.7;font-size:13px">TravelBooking</p>
</div>
<div style="padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
  <p>You requested a password reset. Click the button below to set a new password:</p>
  <p style="text-align:center;margin:24px 0">
    <a href="{reset_link}" style="background:#3b82f6;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold">Reset Password</a>
  </p>
  <p style="color:#666;font-size:13px">This link expires in 1 hour. If you did not request a password reset, you can safely ignore this email.</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
  <p style="font-size:12px;color:#9ca3af">This is an automated email. Please do not reply to this message.</p>
</div>
</body></html>
"""
    return await send_email(to, "TravelBooking — Reset Your Password", html)


async def send_booking_confirmation(booking, user_email: str) -> bool:
    items_rows = _items_html(booking.items)
    discount_row = ""
    if booking.discount_amount and float(booking.discount_amount) > 0:
        discount_row = f"<p style='color:#10b981'><strong>Discount applied:</strong> -${float(booking.discount_amount):.2f}</p>"

    html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;padding:0">
<div style="background:#1a1a2e;color:white;padding:24px;border-radius:8px 8px 0 0">
  <h1 style="margin:0;font-size:22px">Booking Confirmed!</h1>
  <p style="margin:4px 0 0;opacity:0.7;font-size:13px">TravelBooking — Your trip is all set</p>
</div>
<div style="padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
  <p>Hi there! Your booking has been confirmed and payment processed.</p>
  <p><strong>Booking ID:</strong> <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px">{booking.id}</code></p>
  <h3 style="margin-top:20px">Items Booked</h3>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead>
      <tr style="background:#f9fafb">
        <th style="padding:8px 12px;text-align:left">Item</th>
        <th style="padding:8px 12px;text-align:left;color:#666">Details</th>
        <th style="padding:8px 12px;text-align:right">Amount</th>
      </tr>
    </thead>
    <tbody>{items_rows}</tbody>
  </table>
  {discount_row}
  <p style="font-size:16px;font-weight:bold;margin-top:16px">Total Paid: ${float(booking.total_price):.2f}</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
  <p style="color:#10b981;font-weight:bold">Thank you for booking with TravelBooking! Have a great trip.</p>
  <p style="font-size:12px;color:#9ca3af">This is an automated email. Please do not reply to this message.</p>
</div>
</body></html>
"""
    return await send_email(
        user_email,
        f"Booking Confirmed — #{str(booking.id)[:8].upper()}",
        html,
    )


async def send_booking_cancellation(booking, user_email: str) -> bool:
    html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;padding:0">
<div style="background:#ef4444;color:white;padding:24px;border-radius:8px 8px 0 0">
  <h1 style="margin:0;font-size:22px">Booking Cancelled</h1>
  <p style="margin:4px 0 0;opacity:0.7;font-size:13px">TravelBooking</p>
</div>
<div style="padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
  <p>Your booking has been successfully cancelled.</p>
  <p><strong>Booking ID:</strong> <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px">{booking.id}</code></p>
  <p>If a payment was made, a refund will be processed within 5-7 business days to your original payment method.</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
  <p>We hope to welcome you back soon. Feel free to browse our latest deals!</p>
  <p style="font-size:12px;color:#9ca3af">This is an automated email. Please do not reply to this message.</p>
</div>
</body></html>
"""
    return await send_email(
        user_email,
        f"Booking Cancelled — #{str(booking.id)[:8].upper()}",
        html,
    )


async def send_flight_booking_failed(
    booking, user_email: str, failure: dict, refund: dict | None
) -> bool:
    """Sent when a flight booking failed AFTER payment was captured (e.g. Duffel
    rejected the order). The user is told the payment was refunded and asked
    to re-search.
    """
    user_message = (failure or {}).get("user_message") or (
        "Your flight booking could not be completed. Your payment has been refunded."
    )
    refund_amount = (refund or {}).get("amount_usd")
    refund_issued = bool((refund or {}).get("issued"))
    refund_block = (
        f"<p><strong>Refund:</strong> ${float(refund_amount):.2f} returned to your "
        f"original payment method (allow 5-7 business days).</p>"
        if refund_issued and refund_amount is not None
        else (
            "<p><strong>Refund:</strong> A refund is being processed manually by our "
            "support team. You'll receive a confirmation within 24 hours.</p>"
        )
    )
    html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;padding:0">
<div style="background:#ef4444;color:white;padding:24px;border-radius:8px 8px 0 0">
  <h1 style="margin:0;font-size:22px">We couldn't book your flight</h1>
  <p style="margin:4px 0 0;opacity:0.7;font-size:13px">TravelBooking</p>
</div>
<div style="padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
  <p>We're sorry — your flight booking did not go through.</p>
  <p><strong>What happened:</strong> {user_message}</p>
  {refund_block}
  <p><strong>Booking reference:</strong> <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px">{str(booking.id)[:8].upper()}</code></p>
  <p>Please search again — fares change quickly and a fresh offer should be bookable.</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
  <p style="font-size:12px;color:#9ca3af">If you have any questions, reply to this email or contact our support team and quote the booking reference above.</p>
</div>
</body></html>
"""
    return await send_email(
        user_email,
        f"Flight booking failed — refund issued — #{str(booking.id)[:8].upper()}",
        html,
    )


async def send_booking_partial_failure(
    booking, user_email: str, failed_items: list[dict], refund: dict | None
) -> bool:
    """Sent when SOME items in a multi-item booking succeeded but others
    (typically the flight) failed. The user is told what's confirmed, what
    wasn't, and that a partial refund has been issued.
    """
    failed_rows = "".join(
        f"<li><strong>{(it or {}).get('type','item').title()}:</strong> "
        f"{(it or {}).get('user_message','could not be booked')}</li>"
        for it in (failed_items or [])
    )
    refund_amount = (refund or {}).get("amount_usd")
    refund_issued = bool((refund or {}).get("issued"))
    refund_block = (
        f"<p><strong>Partial refund:</strong> ${float(refund_amount):.2f} returned to your "
        f"original payment method (allow 5-7 business days).</p>"
        if refund_issued and refund_amount is not None
        else (
            "<p><strong>Partial refund:</strong> A refund for the failed item is being "
            "processed manually by our support team.</p>"
        )
    )
    html = f"""
<html><body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;padding:0">
<div style="background:#f59e0b;color:white;padding:24px;border-radius:8px 8px 0 0">
  <h1 style="margin:0;font-size:22px">Booking partially completed</h1>
  <p style="margin:4px 0 0;opacity:0.7;font-size:13px">TravelBooking</p>
</div>
<div style="padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px">
  <p>Part of your booking was confirmed, but the following item(s) could not be completed:</p>
  <ul>{failed_rows}</ul>
  {refund_block}
  <p><strong>Booking ID:</strong> <code style="background:#f3f4f6;padding:2px 6px;border-radius:4px">{booking.id}</code></p>
  <p>Items that were successfully booked remain confirmed — check "My Bookings" for full details.</p>
  <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
  <p style="font-size:12px;color:#9ca3af">Reply to this email if you'd like our support team to rebook the failed item for you.</p>
</div>
</body></html>
"""
    return await send_email(
        user_email,
        f"Booking partially completed — #{str(booking.id)[:8].upper()}",
        html,
    )
