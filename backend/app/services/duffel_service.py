"""Duffel flight search, offer retrieval, booking, and cancellation."""
import logging
from datetime import date
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_CLIENT: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _CLIENT
    if _CLIENT is None or _CLIENT.is_closed:
        _CLIENT = httpx.AsyncClient(
            base_url=settings.DUFFEL_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.DUFFEL_TOKEN}",
                "Duffel-Version": settings.DUFFEL_VERSION,
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
    return _CLIENT


class DuffelError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        try:
            body = resp.json()
            errors = body.get("errors", [])
            detail = errors[0].get("message") if errors else body.get("message") or resp.text
        except Exception:
            detail = resp.text
        raise DuffelError(resp.status_code, detail or f"HTTP {resp.status_code}")


def _parse_duration(iso: str | None) -> str | None:
    """Convert ISO 8601 duration PT2H30M to human-friendly '2h 30m'."""
    if not iso:
        return None
    result = iso.replace("PT", "").replace("H", "h ").replace("M", "m").strip()
    return result or iso


def _normalize_segment(seg: dict) -> dict:
    carrier = seg.get("marketing_carrier") or {}
    iata = carrier.get("iata_code") or ""
    flight_num = seg.get("operating_carrier_flight_number") or ""
    origin = seg.get("origin") or {}
    destination = seg.get("destination") or {}
    aircraft_obj = seg.get("aircraft") or {}
    return {
        "flight_number": iata + flight_num,
        "airline_name": carrier.get("name") or "Unknown",
        "airline_iata": iata,
        "origin_iata": origin.get("iata_code") or "",
        "origin_name": origin.get("name") or "",
        "destination_iata": destination.get("iata_code") or "",
        "destination_name": destination.get("name") or "",
        "departure_at": seg.get("departing_at") or "",
        "arrival_at": seg.get("arriving_at") or "",
        "duration": _parse_duration(seg.get("duration")),
        "aircraft": aircraft_obj.get("name"),
    }


def _normalize_offer(raw: dict) -> dict:
    slices = []
    for sl in raw.get("slices") or []:
        segs = [_normalize_segment(s) for s in sl.get("segments") or []]
        origin_obj = sl.get("origin") or {}
        dest_obj = sl.get("destination") or {}
        slices.append({
            "origin": origin_obj.get("iata_code") or "",
            "destination": dest_obj.get("iata_code") or "",
            "duration": _parse_duration(sl.get("duration")),
            "segments": segs,
        })

    owner = raw.get("owner") or {}
    return {
        "duffel_offer_id": raw.get("id") or "",
        "total_amount": float(raw.get("total_amount") or 0),
        "currency": raw.get("total_currency") or "USD",
        "airline_name": owner.get("name") or "Unknown Airline",
        "airline_iata": owner.get("iata_code") or "",
        "slices": slices,
        "passengers": len(raw.get("passengers") or []),
        "cabin_class": raw.get("cabin_class"),
        "expires_at": raw.get("expires_at"),
        "source": "duffel",
    }


async def search_offers(
    origin: str,
    destination: str,
    depart_date: date,
    return_date: date | None = None,
    passengers: int = 1,
    cabin_class: str = "economy",
) -> list[dict]:
    """Create an offer_request and return normalized offers list."""
    slices: list[dict] = [
        {"origin": origin.upper(), "destination": destination.upper(), "departure_date": str(depart_date)}
    ]
    if return_date:
        slices.append(
            {"origin": destination.upper(), "destination": origin.upper(), "departure_date": str(return_date)}
        )

    body = {
        "data": {
            "slices": slices,
            "passengers": [{"type": "adult"} for _ in range(passengers)],
            "cabin_class": cabin_class,
        }
    }

    try:
        resp = await _client().post("/air/offer_requests?return_offers=true", json=body)
        _raise_for_status(resp)
        data = resp.json().get("data", {})
        offers_raw = data.get("offers", [])
        return [_normalize_offer(o) for o in offers_raw[:50]]
    except DuffelError:
        raise
    except Exception as exc:
        raise DuffelError(502, f"Duffel search failed: {exc}") from exc


async def get_offer(duffel_offer_id: str) -> dict:
    """Fetch a single offer with fresh price. Not cached — prices can change."""
    try:
        resp = await _client().get(f"/air/offers/{duffel_offer_id}")
        _raise_for_status(resp)
        return _normalize_offer(resp.json()["data"])
    except DuffelError:
        raise
    except Exception as exc:
        raise DuffelError(502, f"Duffel get_offer failed: {exc}") from exc


async def create_order(
    duffel_offer_id: str,
    passenger: dict,
    amount: str,
    currency: str,
) -> dict:
    """Book the offer. Fetches passenger IDs first, then POSTs /air/orders."""
    try:
        # Get fresh offer to retrieve Duffel-assigned passenger IDs
        offer_resp = await _client().get(f"/air/offers/{duffel_offer_id}")
        _raise_for_status(offer_resp)
        offer_data = offer_resp.json()["data"]
        pax_ids = [p["id"] for p in offer_data.get("passengers", [])]
    except DuffelError:
        raise
    except Exception as exc:
        raise DuffelError(502, f"Duffel offer fetch failed: {exc}") from exc

    if not pax_ids:
        raise DuffelError(422, "No passengers found on offer")

    # Build passenger payloads — map to Duffel's expected fields
    passengers_payload = []
    for pax_id in pax_ids:
        pax = {
            "id": pax_id,
            "title": passenger.get("title", "mr"),
            "gender": passenger.get("gender", "M").lower(),
            "given_name": passenger.get("first_name", ""),
            "family_name": passenger.get("last_name", ""),
            "born_on": str(passenger.get("born_on", "1990-01-01")),
            "email": passenger.get("email", ""),
        }
        phone = passenger.get("phone_number")
        if phone:
            pax["phone_number"] = phone
        passengers_payload.append(pax)

    body = {
        "data": {
            "selected_offers": [duffel_offer_id],
            "passengers": passengers_payload,
            "payments": [{"type": "balance", "amount": amount, "currency": currency}],
        }
    }

    try:
        resp = await _client().post("/air/orders", json=body)
        _raise_for_status(resp)
        order = resp.json()["data"]
        return {
            "duffel_order_id": order["id"],
            "duffel_booking_ref": order.get("booking_reference"),
            "status": order.get("status", "confirmed"),
            "total_amount": float(order.get("total_amount") or amount),
            "currency": order.get("total_currency", currency),
        }
    except DuffelError:
        raise
    except Exception as exc:
        raise DuffelError(502, f"Duffel create_order failed: {exc}") from exc


async def cancel_order(duffel_order_id: str) -> bool:
    """Two-step Duffel cancellation: create then confirm."""
    try:
        resp = await _client().post(
            "/air/order_cancellations",
            json={"data": {"order_id": duffel_order_id}},
        )
        if resp.status_code >= 400:
            return False
        cancellation_id = resp.json()["data"]["id"]

        confirm_resp = await _client().post(
            f"/air/order_cancellations/{cancellation_id}/actions/confirm"
        )
        return confirm_resp.status_code < 400
    except Exception as exc:
        logger.warning("Duffel cancel_order failed for %s: %s", duffel_order_id, exc)
        return False
