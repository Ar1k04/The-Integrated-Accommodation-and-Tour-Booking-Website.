"""Unit tests cho app/services/cloudinary_service.py (mock SDK — KHÔNG cần DB).

Chỉ kiểm tra điều phối: đọc file → gọi cloudinary.uploader.upload với folder →
trả secure_url. Không upload thật.

Test IDs: UT-BE-CLOUD-01..NN.
"""
import pytest

from app.services import cloudinary_service
from app.services.cloudinary_service import upload_image, upload_images

pytestmark = pytest.mark.nodb


JPEG_MAGIC = b"\xff\xd8\xff\xe0"


class _FakeUpload:
    """Đóng vai fastapi.UploadFile với .read(size) async (bytes hợp lệ JPEG)."""

    def __init__(self, data=JPEG_MAGIC + b"imgdata", content_type="image/jpeg"):
        self._data = data
        self.content_type = content_type

    async def read(self, n=-1):
        return self._data if n is None or n < 0 else self._data[:n]


async def test_upload_image_returns_secure_url(monkeypatch):
    captured = {}

    def _fake_upload(contents, **kwargs):
        captured["contents"] = contents
        captured["kwargs"] = kwargs
        return {"secure_url": "https://cdn.example/abc.jpg"}

    monkeypatch.setattr(cloudinary_service.cloudinary.uploader, "upload", _fake_upload)

    payload = JPEG_MAGIC + b"bytes"
    url = await upload_image(_FakeUpload(payload), folder="hotels")
    assert url == "https://cdn.example/abc.jpg"
    assert captured["contents"] == payload
    assert captured["kwargs"]["folder"] == "hotels"


async def test_upload_images_returns_list_of_urls(monkeypatch):
    monkeypatch.setattr(
        cloudinary_service.cloudinary.uploader,
        "upload",
        lambda contents, **k: {"secure_url": "https://cdn/x.jpg"},
    )
    urls = await upload_images([_FakeUpload(), _FakeUpload()], folder="tours")
    assert urls == ["https://cdn/x.jpg", "https://cdn/x.jpg"]


async def test_upload_images_empty_list_makes_no_call(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("không upload khi danh sách rỗng")

    monkeypatch.setattr(cloudinary_service.cloudinary.uploader, "upload", _boom)
    assert await upload_images([]) == []
