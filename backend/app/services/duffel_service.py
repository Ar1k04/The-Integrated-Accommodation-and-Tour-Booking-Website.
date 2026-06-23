"""Duffel flight search, offer retrieval, booking, and cancellation."""
import logging
import re
from datetime import date
from typing import Any

import httpx
from unidecode import unidecode

from app.core.config import settings


# Duffel / IATA name rules: ASCII letters, spaces, hyphens, apostrophes only.
# We transliterate via the `unidecode` library so users can type their real
# name in any script (Vietnamese, German, Greek, CJK, ...) without getting the
# booking rejected at /air/orders. This matches what airlines print on
# tickets — passport MRZ is ASCII-only by ICAO standard.
_NAME_ALLOWED_CHARS = re.compile(r"[^A-Za-z \-']+")


def _normalize_name_for_duffel(name: str) -> str:
    """Transliterate to ASCII letters / space / hyphen / apostrophe.

    Examples:
      ``"Nguyễn"``   → ``"Nguyen"``
      ``"Müller"``   → ``"Muller"``
      ``"O'Brien"``  → ``"O'Brien"``
      ``"Σωκράτης"`` → ``"Sokrates"``

    Returns an empty string for empty / None input — never None.
    """
    if not name:
        return ""
    # `unidecode` handles every Unicode block with maintained transliteration
    # tables — far more correct than NFD-only stripping.
    transliterated = unidecode(str(name))
    # Drop anything still outside the IATA alphabet (digits, punctuation, …).
    return _NAME_ALLOWED_CHARS.sub("", transliterated).strip()

logger = logging.getLogger(__name__)

_CLIENT: httpx.AsyncClient | None = None


def _is_test_mode() -> bool:
    """True when the configured Duffel token is a sandbox key."""
    return (settings.DUFFEL_TOKEN or "").startswith("duffel_test_")


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
    def __init__(
        self,
        status_code: int,
        message: str,
        *,
        error_type: str | None = None,
        error_code: str | None = None,
        raw: dict | None = None,
    ):
        self.status_code = status_code
        self.message = message
        self.error_type = error_type
        self.error_code = error_code
        self.raw = raw
        super().__init__(message)


# Transient HTTP statuses worth retrying. The 502 we wrap around network
# exceptions also lands here.
RETRYABLE_DUFFEL_STATUS = {429, 500, 502, 503, 504}

# Duffel error codes that will keep failing on retry — usually offer-related.
PERMANENT_DUFFEL_ERROR_CODES = {
    "offer_no_longer_available",
    "duplicate_order",
}

# Duffel error types that are permanent (payload, auth, balance, airline reject).
PERMANENT_DUFFEL_ERROR_TYPES = {
    "airline_error",
    "validation_error",
    "authentication_error",
    "insufficient_balance",
}


def is_retryable_duffel_error(exc: "DuffelError") -> bool:
    """True if the failure is likely transient — safe to retry."""
    if exc.error_code in PERMANENT_DUFFEL_ERROR_CODES:
        return False
    if exc.error_type in PERMANENT_DUFFEL_ERROR_TYPES:
        return False
    return exc.status_code in RETRYABLE_DUFFEL_STATUS or exc.status_code >= 500


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        body: dict | None = None
        detail: str | None = None
        error_type: str | None = None
        error_code: str | None = None
        try:
            body = resp.json()
            errors = body.get("errors") or []
            if errors:
                first = errors[0] or {}
                detail = first.get("message")
                error_type = first.get("type")
                error_code = first.get("code")
            else:
                detail = body.get("message") or resp.text
        except Exception:
            detail = resp.text
        raise DuffelError(
            resp.status_code,
            detail or f"HTTP {resp.status_code}",
            error_type=error_type,
            error_code=error_code,
            raw=body,
        )


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

    # Per-passenger breakdown so the booking UI can label each form
    # ("Adult passenger 1", "Child age 8 — passenger 2") and so the
    # FlightItemCreate validator can ensure submitted info matches the
    # offer's expected adults/children composition.
    breakdown: list[dict] = []
    for p in raw_passengers:
        breakdown.append({
            "passenger_id": p.get("id"),
            "type": p.get("type"),
            "age": p.get("age"),
        })

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
        "passenger_breakdown": breakdown,
        "cabin_class": raw.get("cabin_class"),
        "expires_at": raw.get("expires_at"),
        "conditions": raw.get("conditions") or {},
        "has_baggage": has_baggage,
        "source": "duffel",
    }


def _build_passengers_payload(adults: int, child_ages: list[int] | None) -> list[dict]:
    """Build the `passengers` array Duffel expects on /air/offer_requests.

    Per Duffel docs each passenger may have either ``type`` OR ``age`` (not
    both). We send ``type: "adult"`` for grown-ups and ``age: N`` for anyone
    < 18 — Duffel + the airline decide whether age-N maps to child or
    infant_without_seat based on the airline's own policy.
    """
    adults = max(0, int(adults or 0))
    ages = [int(a) for a in (child_ages or []) if a is not None]
    payload: list[dict] = [{"type": "adult"} for _ in range(adults)]
    payload.extend({"age": age} for age in ages)
    if not payload:
        # Duffel rejects empty passenger lists — fall back to a single adult.
        payload = [{"type": "adult"}]
    return payload


async def search_offers(
    origin: str,
    destination: str,
    depart_date: date,
    return_date: date | None = None,
    adults: int | None = None,
    child_ages: list[int] | None = None,
    cabin_class: str = "economy",
    *,
    passengers: int | None = None,
) -> list[dict]:
    """Create an offer_request and return normalized offers list.

    Pass ``adults`` (and optionally ``child_ages``) for accurate per-age
    pricing. Legacy callers that still pass ``passengers=N`` are treated as
    ``adults=N`` with no children.
    """
    if adults is None:
        adults = passengers if passengers is not None else 1
    adults = max(1, int(adults))
    child_ages = list(child_ages or [])

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
            "passengers": _build_passengers_payload(adults, child_ages),
            "cabin_class": cabin_class,
        }
    }

    try:
        resp = await _client().post("/air/offer_requests?return_offers=true", json=body)
        _raise_for_status(resp)
        data = resp.json().get("data", {})
        offers_raw = data.get("offers", [])
        # In sandbox, only Duffel Airways (ZZ) is a documented stable test
        # airline — others (VJ/VN/W2/...) reject bookings non-deterministically
        # with `airline_error`. Filter them out so test-mode bookings actually
        # complete end-to-end.
        if _is_test_mode() and settings.DUFFEL_TEST_RELIABLE_ONLY:
            offers_raw = [
                o for o in offers_raw
                if ((o.get("owner") or {}).get("iata_code") or "").upper() == "ZZ"
            ]
        # Strict per-airline cap: each carrier shows at most N offers so the
        # result set has a balanced mix instead of one airline dominating.
        # Duffel returns offers sorted within each airline by price/quality,
        # so taking the first N per airline gives the strongest options from
        # each. No "leftover" fill — exceeding the cap defeats the balance.
        PER_AIRLINE_CAP = 10
        per_airline: dict[str, int] = {}
        balanced: list[dict] = []
        for o in offers_raw:
            iata = ((o.get("owner") or {}).get("iata_code") or "").upper() or "?"
            if per_airline.get(iata, 0) < PER_AIRLINE_CAP:
                balanced.append(o)
                per_airline[iata] = per_airline.get(iata, 0) + 1
        return [_normalize_offer(o) for o in balanced]
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

    # Pull offer-side passenger metadata so we can match our submitted passenger
    # order to the right Duffel passenger ID (offer might list adults first,
    # children second — we mirror that order on the frontend).
    offer_passengers = offer_data.get("passengers", [])

    passengers_payload = []
    for idx, (pax_meta, pax) in enumerate(zip(offer_passengers, passengers)):
        pax_id = pax_meta["id"]
        pax_age = pax.get("age")
        # Minors: send age (born_on still required by Duffel for identity check).
        # Adults: send no age — born_on alone is enough.
        # Names go through _normalize_name_for_duffel to strip diacritics that
        # Duffel/IATA will reject ("Nguyễn" → "Nguyen").
        entry = {
            "id": pax_id,
            "title": pax.get("title", "mr"),
            "gender": (pax.get("gender") or "M").lower(),
            "given_name": _normalize_name_for_duffel(pax.get("first_name", "")),
            "family_name": _normalize_name_for_duffel(pax.get("last_name", "")),
            "born_on": str(pax.get("born_on", "1990-01-01")),
            "email": pax.get("email", ""),
        }
        if pax_age is not None and int(pax_age) < 18:
            entry["age"] = int(pax_age)
        phone = pax.get("phone_number")
        if phone:
            entry["phone_number"] = phone
        # Attach seat selection by passenger index (frontend keys seats this way)
        if selected_seats:
            seat_service_id = selected_seats.get(str(idx)) or selected_seats.get(pax_id)
            if seat_service_id:
                entry["seat"] = seat_service_id
        passengers_payload.append(entry)

    # Compute payment amount from the FRESH offer total (just-fetched above) +
    # the price of any selected services. Duffel rejects with
    # `payment_amount_does_not_match_order_amount` (422) if `payments.amount`
    # drifts from the order's `total_amount` — and the offer total may have
    # been re-quoted since we stored the price at search time. The caller's
    # `amount` argument is now used only as a fallback if fresh fetch is
    # missing the field for some reason.
    fresh_total = offer_data.get("total_amount")
    fresh_currency = offer_data.get("total_currency") or currency

    services_total = 0.0
    if services:
        # offer.available_services carries the price of each service id, so we
        # can sum without an extra round-trip. We fetch available_services on
        # the same offer endpoint when needed.
        available = offer_data.get("available_services") or []
        if not available:
            try:
                svc_resp = await _client().get(
                    f"/air/offers/{duffel_offer_id}?return_available_services=true"
                )
                if svc_resp.status_code == 200:
                    available = (svc_resp.json().get("data") or {}).get("available_services") or []
            except Exception:
                available = []
        by_id = {s.get("id"): s for s in available if s.get("id")}
        for svc in services:
            sid = svc.get("id") if isinstance(svc, dict) else None
            qty = int((svc.get("quantity") if isinstance(svc, dict) else 1) or 1)
            svc_meta = by_id.get(sid)
            if svc_meta:
                try:
                    services_total += float(svc_meta.get("total_amount") or 0) * qty
                except (TypeError, ValueError):
                    pass

    try:
        payment_amount = float(fresh_total) + services_total if fresh_total is not None else float(amount)
    except (TypeError, ValueError):
        payment_amount = float(amount)
    # Format with 2 decimals (Duffel expects strings like "71.72")
    payment_amount_str = f"{payment_amount:.2f}"

    body_data = {
        "selected_offers": [duffel_offer_id],
        "passengers": passengers_payload,
        "payments": [{
            "type": "balance",
            "amount": payment_amount_str,
            "currency": fresh_currency,
        }],
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


async def cancel_order(duffel_order_id: str) -> dict | None:
    """Two-step Duffel cancellation. Returns supplier refund info.

    Shape: {"status": "cancelled", "refund_amount": float | None, "currency": str | None}
    or None on failure. Non-refundable fares return `refund_amount=None`.

    Duffel's order_cancellation object includes a `refund_amount` and
    `refund_currency` that reflect what's refundable per the fare rules.
    """
    try:
        resp = await _client().post(
            "/air/order_cancellations",
            json={"data": {"order_id": duffel_order_id}},
        )
        if resp.status_code >= 400:
            return None
        cancellation = resp.json()["data"]
        cancellation_id = cancellation["id"]

        confirm_resp = await _client().post(
            f"/air/order_cancellations/{cancellation_id}/actions/confirm"
        )
        if confirm_resp.status_code >= 400:
            return None
        confirmed = confirm_resp.json().get("data") or cancellation
        refund_amount_raw = confirmed.get("refund_amount")
        try:
            refund_amount = float(refund_amount_raw) if refund_amount_raw is not None else None
        except (TypeError, ValueError):
            refund_amount = None
        return {
            "status": "cancelled",
            "refund_amount": refund_amount,
            "currency": confirmed.get("refund_currency"),
        }
    except Exception as exc:
        logger.warning("Duffel cancel_order failed for %s: %s", duffel_order_id, exc)
        return None
