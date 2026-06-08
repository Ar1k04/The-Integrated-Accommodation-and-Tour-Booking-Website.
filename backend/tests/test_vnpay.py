"""Unit tests cho app/services/vnpay_service.py (pure logic — KHÔNG cần DB).

VNPay dùng HMAC-SHA512 trên chuỗi query đã sort. Sai một byte → chữ ký lệch,
nên đây là chốt chặn chống giả mạo callback/IPN. Ta monkeypatch secret cố định.

Test IDs: UT-BE-VNPAY-01..NN.
"""
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit

import pytest

from app.core.config import settings
from app.services import vnpay_service
from app.services.vnpay_service import (
    _hmac_sha512,
    create_payment_url,
    verify_return_params,
)

pytestmark = pytest.mark.nodb

SECRET = "TESTHASHSECRET123"


@pytest.fixture(autouse=True)
def _vnpay_settings(monkeypatch):
    monkeypatch.setattr(settings, "VNPAY_HASH_SECRET", SECRET)
    monkeypatch.setattr(settings, "VNPAY_TMN_CODE", "TESTTMN")
    monkeypatch.setattr(
        settings, "VNPAY_PAYMENT_URL", "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
    )


def _sign(params: dict) -> str:
    """Ký params theo đúng thuật toán service: sorted + URL-encode (quote_plus)."""
    query = urlencode(sorted(params.items()), quote_via=quote_plus)
    return _hmac_sha512(SECRET, query)


# ── create_payment_url ───────────────────────────────────────────────────────
class TestCreatePaymentUrl:
    def test_url_targets_payment_endpoint(self):
        url = create_payment_url("booking-123", 100, "https://app/return")
        assert url.startswith(settings.VNPAY_PAYMENT_URL + "?")

    def test_amount_is_multiplied_by_100(self):
        # VNPay yêu cầu số tiền × 100 (đơn vị nhỏ nhất).
        url = create_payment_url("booking-123", 250000, "https://app/return")
        q = dict(parse_qsl(urlsplit(url).query))
        assert q["vnp_Amount"] == str(250000 * 100)

    def test_includes_secure_hash_and_core_fields(self):
        url = create_payment_url("booking-xyz", 100, "https://app/return")
        q = dict(parse_qsl(urlsplit(url).query))
        assert q["vnp_SecureHash"]  # có chữ ký
        assert q["vnp_TxnRef"] == "booking-xyz"
        assert q["vnp_TmnCode"] == "TESTTMN"
        assert q["vnp_Command"] == "pay"

    def test_generated_url_passes_own_verification(self):
        # Round-trip: URL do create_payment_url sinh ra phải verify hợp lệ.
        url = create_payment_url("booking-1", 100, "https://app/return", order_info="Booking Payment")
        q = dict(parse_qsl(urlsplit(url).query))
        is_valid, _ = verify_return_params(dict(q))
        assert is_valid is True

    def test_signed_string_equals_wire_query_with_encoded_values(self):
        # Regression cho lỗi "Sai chữ ký": VNPay tính lại HMAC trên ĐÚNG các value
        # (đã URL-encode) mà nó nhận, nên chuỗi-đem-ký phải GIỐNG HỆT chuỗi-gửi-đi.
        # Nếu ai đó quay lại ký trên value thô, return_url chứa '://' '/' sẽ làm hai
        # chuỗi lệch nhau → test này fail.
        url = create_payment_url("booking-1", 100, "https://my.app/payments/vnpay/return")
        query = urlsplit(url).query
        wire_without_hash, _, sent_hash = query.rpartition("&vnp_SecureHash=")
        # 1) hash gửi đi phải bằng HMAC tính trên chính chuỗi wire (consistency).
        assert sent_hash.lower() == _hmac_sha512(SECRET, wire_without_hash).lower()
        # 2) return_url phải xuất hiện ở dạng ĐÃ ENCODE trên wire (không phải thô).
        assert "https%3A%2F%2Fmy.app" in wire_without_hash
        assert "https://my.app" not in wire_without_hash

    def test_includes_expire_date_after_create_date(self):
        # vnp_ExpireDate (chuẩn 2.1.0) phải có và muộn hơn vnp_CreateDate.
        url = create_payment_url("booking-1", 100, "https://app/return")
        q = dict(parse_qsl(urlsplit(url).query))
        assert q["vnp_ExpireDate"] > q["vnp_CreateDate"]


# ── verify_return_params ─────────────────────────────────────────────────────
class TestVerifyReturnParams:
    def _valid_return(self) -> dict:
        params = {
            "vnp_Amount": "10000000",
            "vnp_BankCode": "NCB",
            "vnp_ResponseCode": "00",
            "vnp_TxnRef": "booking-1",
        }
        params["vnp_SecureHash"] = _sign(params)
        return params

    def test_valid_signature_accepted(self):
        is_valid, cleaned = verify_return_params(self._valid_return())
        assert is_valid is True
        assert "vnp_SecureHash" not in cleaned  # đã được loại khỏi chuỗi ký

    def test_tampered_amount_rejected(self):
        params = self._valid_return()
        params["vnp_Amount"] = "1"  # đổi số tiền sau khi đã ký → lệch hash
        is_valid, _ = verify_return_params(params)
        assert is_valid is False

    def test_wrong_secret_rejects(self, monkeypatch):
        params = self._valid_return()
        monkeypatch.setattr(settings, "VNPAY_HASH_SECRET", "OTHER-SECRET")
        is_valid, _ = verify_return_params(params)
        assert is_valid is False

    def test_hash_type_field_is_ignored(self):
        params = self._valid_return()
        params["vnp_SecureHashType"] = "SHA512"  # không tham gia ký
        is_valid, _ = verify_return_params(params)
        assert is_valid is True

    def test_case_insensitive_hash_compare(self):
        params = self._valid_return()
        params["vnp_SecureHash"] = params["vnp_SecureHash"].upper()
        is_valid, _ = verify_return_params(params)
        assert is_valid is True


def test_hmac_sha512_is_deterministic():
    assert _hmac_sha512(SECRET, "a=1&b=2") == _hmac_sha512(SECRET, "a=1&b=2")
    assert _hmac_sha512(SECRET, "a=1") != _hmac_sha512(SECRET, "a=2")
