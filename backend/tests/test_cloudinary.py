"""Unit tests cho app/services/cloudinary_service.py (mock SDK — KHÔNG cần DB).

Chỉ kiểm tra điều phối: đọc file → gọi cloudinary.uploader.upload với folder →
trả secure_url. Không upload thật.

Test IDs: UT-BE-CLOUD-01..NN.
"""
import pytest

from app.services import cloudinary_service
from app.services.cloudinary_service import upload_image, upload_images

pytestmark = pytest.mark.nodb


class _FakeUpload:
    """Đóng vai fastapi.UploadFile với .read() async."""

    def __init__(self, data=b"imgdata"):
        self._data = data

    async def read(self):
        return self._data


async def test_upload_image_returns_secure_url(monkeypatch):
    captured = {}

    def _fake_upload(contents, **kwargs):
        captured["contents"] = contents
        captured["kwargs"] = kwargs
        return {"secure_url": "https://cdn.example/abc.jpg"}

    monkeypatch.setattr(cloudinary_service.cloudinary.uploader, "upload", _fake_upload)

    url = await upload_image(_FakeUpload(b"bytes"), folder="hotels")
    assert url == "https://cdn.example/abc.jpg"
    assert captured["contents"] == b"bytes"
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
