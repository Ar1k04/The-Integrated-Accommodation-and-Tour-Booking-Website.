"""Duffel flight search and offer endpoints."""
import json
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.schemas.flight import FlightOfferResponse
from app.services import duffel_service
from app.services.duffel_service import DuffelError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/flights", tags=["flights"])


def _cache(request: Request):
    return getattr(request.app.state, "redis", None)


@router.get("/search")
async def search_flights(
    request: Request,
    origin: str = Query(..., min_length=3, max_length=3, description="IATA origin code e.g. HAN"),
    destination: str = Query(..., min_length=3, max_length=3, description="IATA destination code e.g. SGN"),
    depart_date: date = Query(..., alias="depart_date"),
    return_date: date | None = Query(None, alias="return_date"),
    passengers: int = Query(default=1, ge=1, le=9),
    cabin_class: str = Query(default="economy"),
):
    cache_key = f"duffel:search:{origin.upper()}:{destination.upper()}:{depart_date}:{return_date}:{passengers}:{cabin_class}"
    redis = _cache(request)

    if redis:
        cached = await redis.get(cache_key)
        if cached:
            return {"data": json.loads(cached), "status": "success", "message": "OK", "source": "cache"}

    try:
        offers = await duffel_service.search_offers(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            passengers=passengers,
            cabin_class=cabin_class,
        )
    except DuffelError as exc:
        logger.warning("Duffel search error: %s", exc.message)
        raise HTTPException(
            status_code=exc.status_code if exc.status_code < 500 else 502,
            detail=exc.message or "Flight search unavailable — try again later",
        )

    if redis and offers:
        await redis.setex(cache_key, 300, json.dumps(offers))

    return {"data": offers, "status": "success", "message": "OK", "count": len(offers)}


@router.get("/offers/{duffel_offer_id}")
async def get_flight_offer(duffel_offer_id: str):
    """Return a single offer with fresh price — not cached."""
    try:
        offer = await duffel_service.get_offer(duffel_offer_id)
    except DuffelError as exc:
        raise HTTPException(
            status_code=exc.status_code if exc.status_code < 500 else 502,
            detail=exc.message or "Offer not found or expired",
        )
    return {"data": offer, "status": "success", "message": "OK"}
