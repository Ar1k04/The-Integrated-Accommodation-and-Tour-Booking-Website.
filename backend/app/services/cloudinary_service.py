import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile, status

from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)

# Upload guards applied to every image upload (avatar, hotel, room, tour).
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB


def _sniff_image_type(data: bytes) -> str | None:
    """Return the real image type from magic bytes, or None if not an image.

    The declared Content-Type is attacker-controlled, so the bytes are checked
    against known signatures for the formats we accept.
    """
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


async def upload_image(file: UploadFile, folder: str = "travel") -> str:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unsupported image type. Allowed: "
                + ", ".join(sorted(ALLOWED_IMAGE_TYPES))
            ),
        )
    # Read at most one byte past the limit so an oversized upload is rejected
    # without buffering the whole (potentially huge) file into memory.
    contents = await file.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image exceeds the {MAX_IMAGE_BYTES // (1024 * 1024)} MB size limit.",
        )
    if _sniff_image_type(contents) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content is not a valid JPEG, PNG, WebP, or GIF image.",
        )
    result = cloudinary.uploader.upload(contents, folder=folder)
    return result["secure_url"]


async def upload_images(files: list[UploadFile], folder: str = "travel") -> list[str]:
    urls = []
    for f in files:
        url = await upload_image(f, folder=folder)
        urls.append(url)
    return urls
