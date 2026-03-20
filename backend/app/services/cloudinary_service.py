import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True,
)


async def upload_image(file: UploadFile, folder: str = "travel") -> str:
    contents = await file.read()
    result = cloudinary.uploader.upload(contents, folder=folder)
    return result["secure_url"]


async def upload_images(files: list[UploadFile], folder: str = "travel") -> list[str]:
    urls = []
    for f in files:
        url = await upload_image(f, folder=folder)
        urls.append(url)
    return urls
