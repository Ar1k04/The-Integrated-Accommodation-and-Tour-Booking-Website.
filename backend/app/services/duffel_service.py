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

    # Collect baggage info from the first passenger (Duffel returns per-passenger
    # baggages on each segment). Surfaced as a simple flag the UI can check.
    has_baggage = False
    raw_passengers = raw.get("passengers") or []
    if raw_passengers:
        for sl in raw.get("slices") or []:
            for seg in sl.get("segments") or []:
                seg_passengers = seg.get("passengers") or []
                for p in seg_passengers:
                    baggages = p.get("baggages") or []
                    if any((b.get("quantity") or 0) > 0 for b in baggages):
                        has_baggage = True
                        break
                if has_baggage:
                    break
            if has_baggage:
                break

    return {
        "duffel_offer_id": raw.get("id") or "",
        "total_amount": float(raw.get("total_amount") or 0),
        "base_amount": float(raw.get("base_amount")) if raw.get("base_amount") else None,
        "tax_amount": float(raw.get("tax_amount")) if raw.get("tax_amount") else None,
        "currency": raw.get("total_currency") or "USD",
        "airline_name": owner.get("name") or "Unknown Airline",
        "airline_iata": owner.get("iata_code") or "",
        "slices": slices,
        "passengers": len(raw_passengers),
        "cabin_class": raw.get("cabin_class"),
        "expires_at": raw.get("expires_at"),
        "conditions": raw.get("conditions") or {},
        "has_baggage": has_baggage,
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
    passengers: list[dict],
    amount: str,
    currency: str,
    services: list[dict] | None = None,
    selected_seats: dict[str, str] | None = None,
) -> dict:
    """Book the offer. Fetches passenger IDs first, then POSTs /air/orders.

    passengers: one dict per traveler (count MUST equal offer's pax count).
    services: optional Duffel services to add — [{"id": "ase_...", "quantity": 1}].
    selected_seats: optional mapping {pax_index_str: seat_service_id} — injected
        per-passenger as Duffel expects seats attached to the passenger record.
    """
    try:
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

    if len(pax_ids) != len(passengers):
        raise DuffelError(
            422,
            f"Passenger count mismatch: offer expects {len(pax_ids)}, got {len(passengers)}",
        )

    passengers_payload = []
    for idx, (pax_id, pax) in enumerate(zip(pax_ids, passengers)):
        entry = {
            "id": pax_id,
            "title": pax.get("title", "mr"),
            "gender": (pax.get("gender") or "M").lower(),
            "given_name": pax.get("first_name", ""),
            "family_name": pax.get("last_name", ""),
            "born_on": str(pax.get("born_on", "1990-01-01")),
            "email": pax.get("email", ""),
        }
        phone = pax.get("phone_number")
        if phone:
            entry["phone_number"] = phone
        # Attach seat selection by passenger index (frontend keys seats this way)
        if selected_seats:
            seat_service_id = selected_seats.get(str(idx)) or selected_seats.get(pax_id)
            if seat_service_id:
                entry["seat"] = seat_service_id
        passengers_payload.append(entry)

    body_data = {
        "selected_offers": [duffel_offer_id],
        "passengers": passengers_payload,
        "payments": [{"type": "balance", "amount": amount, "currency": currency}],
    }
    if services:
        body_data["services"] = services

    try:
        resp = await _client().post("/air/orders", json={"data": body_data})
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


async def get_order(duffel_order_id: str) -> dict:
    """Fetch a Duffel order with full details (passengers, slices, documents)."""
    try:
        resp = await _client().get(f"/air/orders/{duffel_order_id}")
        _raise_for_status(resp)
        raw = resp.json()["data"]
    except DuffelError:
        raise
    except Exception as exc:
        raise DuffelError(502, f"Duffel get_order failed: {exc}") from exc

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

    passengers_out = []
    for p in raw.get("passengers") or []:
        passengers_out.append({
            "id": p.get("id"),
            "title": p.get("title"),
            "given_name": p.get("given_name"),
            "family_name": p.get("family_name"),
            "email": p.get("email"),
            "born_on": p.get("born_on"),
        })

    return {
        "duffel_order_id": raw.get("id") or "",
        "duffel_booking_ref": raw.get("booking_reference"),
        "status": raw.get("status") or raw.get("synced_at"),
        "total_amount": float(raw.get("total_amount") or 0),
        "currency": raw.get("total_currency") or "USD",
        "passengers": passengers_out,
        "slices": slices,
        "documents": raw.get("documents") or [],
        "conditions": raw.get("conditions") or {},
        "created_at": raw.get("created_at"),
    }


async def get_seat_maps(duffel_offer_id: str) -> list[dict]:
    """Fetch seat map for an offer. Returns empty list if not supported by airline."""
    try:
        resp = await _client().get(f"/air/seat_maps?offer_id={duffel_offer_id}")
        if resp.status_code == 404:
            return []
        _raise_for_status(resp)
        return resp.json().get("data") or []
    except DuffelError as exc:
        if exc.status_code in (404, 422):
            return []
        raise
    except Exception as exc:
        raise DuffelError(502, f"Duffel get_seat_maps failed: {exc}") from exc


async def get_available_services(duffel_offer_id: str) -> list[dict]:
    """Fetch available add-on services (baggage, etc.) for an offer."""
    try:
        resp = await _client().get(
            f"/air/offers/{duffel_offer_id}?return_available_services=true"
        )
        _raise_for_status(resp)
        raw = resp.json()["data"]
        return raw.get("available_services") or []
    except DuffelError:
        raise
    except Exception as exc:
        raise DuffelError(502, f"Duffel get_available_services failed: {exc}") from exc


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
