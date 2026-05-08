from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.rate_limit import limiter

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    yield
    await app.state.redis.close()


app = FastAPI(title="Travel Booking API", version="1.0.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": "Internal server error", "detail": str(exc)},
    )


# --- routers ---
from app.api.v1.routes.auth import router as auth_router  # noqa: E402
from app.api.v1.routes.hotels import router as hotels_router  # noqa: E402
from app.api.v1.routes.rooms import router as rooms_router  # noqa: E402
from app.api.v1.routes.bookings import router as bookings_router  # noqa: E402
from app.api.v1.routes.tours import router as tours_router  # noqa: E402
from app.api.v1.routes.reviews import router as reviews_router  # noqa: E402
from app.api.v1.routes.payments import router as payments_router  # noqa: E402
from app.api.v1.routes.wishlists import router as wishlists_router  # noqa: E402
from app.api.v1.routes.vouchers import router as vouchers_router  # noqa: E402
from app.api.v1.routes.loyalty import router as loyalty_router  # noqa: E402
from app.api.v1.routes.admin import router as admin_router  # noqa: E402
from app.api.v1.routes.flights import router as flights_router  # noqa: E402

app.include_router(auth_router, prefix="/api/v1")
app.include_router(hotels_router, prefix="/api/v1")
app.include_router(rooms_router, prefix="/api/v1")
app.include_router(bookings_router, prefix="/api/v1")
app.include_router(tours_router, prefix="/api/v1")
app.include_router(reviews_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(wishlists_router, prefix="/api/v1")
app.include_router(vouchers_router, prefix="/api/v1")
app.include_router(loyalty_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")
app.include_router(flights_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok"}
