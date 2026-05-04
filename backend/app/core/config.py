from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://travel_user:travel_password@postgres:5432/travel_db"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # Auth / JWT
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Email (SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@travelbooking.com"

    # Duffel (Flights)
    DUFFEL_TOKEN: str = ""
    DUFFEL_BASE_URL: str = "https://api.duffel.com"
    DUFFEL_VERSION: str = "v2"

    # VNPay
    VNPAY_TMN_CODE: str = ""
    VNPAY_HASH_SECRET: str = ""
    VNPAY_PAYMENT_URL: str = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"

    # LiteAPI
    LITEAPI_KEY: str = ""
    LITEAPI_BASE_URL: str = "https://api.liteapi.travel/v3.0"

    # Viator
    VIATOR_KEY: str = ""
    VIATOR_BASE_URL: str = "https://api.sandbox.viator.com/partner"

    # Frontend
    FRONTEND_URL: str = "http://localhost:5173"

    # Currency conversion (display only — bookings stored in USD)
    USD_TO_VND_RATE: int = 25_000


settings = Settings()
