"""VNPay payment gateway integration (domestic Vietnam payments)."""
import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urlencode

from app.core.config import settings

logger = logging.getLogger(__name__)

USD_TO_VND = settings.USD_TO_VND_RATE

# Checkout soft-lock is 15 min (Redis TTL); expire the VNPay order at the same
# horizon so an abandoned payment can't be completed after the slot is released.
PAYMENT_EXPIRE_MINUTES = 15

# VNPay reads vnp_CreateDate / vnp_ExpireDate as GMT+7 (Vietnam) wall-clock time.
# The backend container runs in UTC, so a naive datetime.now() is 7h behind
# VNPay's clock — that pushed vnp_ExpireDate into the past and VNPay rejected
# every order with "Giao dịch đã quá thời gian chờ thanh toán". Always build the
# timestamps in GMT+7, regardless of the host/container timezone.
VN_TZ = timezone(timedelta(hours=7))


def _hmac_sha512(secret: str, data: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()


def _hash_data(params: dict) -> str:
    """Build the exact string VNPay signs (spec 2.1.0): params sorted by key,
    joined as ``key=value`` with values URL-encoded via quote_plus.

    This MUST be byte-for-byte identical to the query string actually sent on the
    wire. VNPay recomputes the HMAC over the (URL-encoded) values it receives, so
    signing *raw* values while sending *encoded* ones makes the checksums diverge
    on any value with reserved characters — notably ``vnp_ReturnUrl`` (``://``,
    ``/``) — and VNPay rejects with "Sai chữ ký" (code 70).
    """
    return urlencode(sorted(params.items()), quote_via=quote_plus)


def create_payment_url(
    booking_id: str,
    amount_vnd: int,
    return_url: str,
    client_ip: str = "127.0.0.1",
    order_info: str = "Booking Payment",
) -> str:
    """Build the VNPay redirect URL. amount_vnd must be > 0."""
    now = datetime.now(VN_TZ)
    params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": settings.VNPAY_TMN_CODE,
        "vnp_Locale": "vn",
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": str(booking_id),
        "vnp_OrderInfo": order_info,
        "vnp_OrderType": "other",
        "vnp_Amount": str(amount_vnd * 100),
        "vnp_ReturnUrl": return_url,
        "vnp_IpAddr": client_ip,
        "vnp_CreateDate": now.strftime("%Y%m%d%H%M%S"),
        "vnp_ExpireDate": (
            now + timedelta(minutes=PAYMENT_EXPIRE_MINUTES)
        ).strftime("%Y%m%d%H%M%S"),
    }

    # Sign and send the SAME encoded string; only the hash is appended after it.
    hash_data = _hash_data(params)
    secure_hash = _hmac_sha512(settings.VNPAY_HASH_SECRET, hash_data)
    return f"{settings.VNPAY_PAYMENT_URL}?{hash_data}&vnp_SecureHash={secure_hash}"


def verify_return_params(params: dict) -> tuple[bool, dict]:
    """
    Verify HMAC signature on VNPay return/IPN params.

    ``params`` arrive already URL-decoded (FastAPI/Starlette decodes query params),
    so we re-encode them with the same quote_plus scheme used when signing — this
    reproduces VNPay's own checksum exactly.

    Returns (is_valid, cleaned_params).
    """
    received_hash = params.pop("vnp_SecureHash", "")
    params.pop("vnp_SecureHashType", None)

    sorted_params = dict(sorted(params.items()))
    computed_hash = _hmac_sha512(settings.VNPAY_HASH_SECRET, _hash_data(sorted_params))

    is_valid = bool(received_hash) and computed_hash.lower() == received_hash.lower()
    return is_valid, sorted_params
