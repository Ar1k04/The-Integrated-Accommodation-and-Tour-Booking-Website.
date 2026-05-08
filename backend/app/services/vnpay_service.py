"""VNPay payment gateway integration (domestic Vietnam payments)."""
import hashlib
import hmac
import logging
from datetime import datetime
from urllib.parse import quote_plus, urlencode

from app.core.config import settings

logger = logging.getLogger(__name__)

USD_TO_VND = settings.USD_TO_VND_RATE


def _hmac_sha512(secret: str, data: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()


def create_payment_url(
    booking_id: str,
    amount_vnd: int,
    return_url: str,
    client_ip: str = "127.0.0.1",
    order_info: str = "Booking Payment",
) -> str:
    """Build the VNPay redirect URL. amount_vnd must be > 0."""
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
        "vnp_CreateDate": datetime.now().strftime("%Y%m%d%H%M%S"),
    }

    sorted_params = dict(sorted(params.items()))
    # VNPay official algorithm: raw values (no URL encoding) for the hash data string
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params.items())
    secure_hash = _hmac_sha512(settings.VNPAY_HASH_SECRET, query_string)

    sorted_params["vnp_SecureHash"] = secure_hash
    return f"{settings.VNPAY_PAYMENT_URL}?{urlencode(sorted_params)}"


def verify_return_params(params: dict) -> tuple[bool, dict]:
    """
    Verify HMAC signature on VNPay return/IPN params.

    Returns (is_valid, cleaned_params).
    """
    received_hash = params.pop("vnp_SecureHash", "")
    params.pop("vnp_SecureHashType", None)

    sorted_params = dict(sorted(params.items()))
    # Use raw values — consistent with create_payment_url
    query_string = "&".join(f"{k}={v}" for k, v in sorted_params.items())
    computed_hash = _hmac_sha512(settings.VNPAY_HASH_SECRET, query_string)

    is_valid = computed_hash.lower() == received_hash.lower()
    return is_valid, sorted_params
