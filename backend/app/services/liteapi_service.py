"""LiteAPI hotel search, rates, prebook, and booking integration."""
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
            base_url=settings.LITEAPI_BASE_URL,
            headers={"X-API-Key": settings.LITEAPI_KEY, "Accept": "application/json"},
            timeout=15.0,
        )
    return _CLIENT


class LiteAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("message") or resp.text
        except Exception:
            detail = resp.text
        raise LiteAPIError(resp.status_code, detail)


# Keyword → ISO-3166-1 alpha-2 mapping for common travel destinations
_CITY_COUNTRY_MAP: dict[str, str] = {
    # Vietnam
    "hanoi": "VN", "ha noi": "VN", "hà nội": "VN",
    "ho chi minh": "VN", "saigon": "VN", "hcmc": "VN",
    "da nang": "VN", "đà nẵng": "VN", "danang": "VN",
    "hoi an": "VN", "hội an": "VN",
    "hue": "VN", "huế": "VN",
    "nha trang": "VN", "ha long": "VN", "phu quoc": "VN",
    "can tho": "VN", "vung tau": "VN",
    "vietnam": "VN", "viet nam": "VN",
    # Thailand
    "bangkok": "TH", "phuket": "TH", "chiang mai": "TH",
    "pattaya": "TH", "krabi": "TH", "koh samui": "TH",
    "thailand": "TH",
    # Singapore
    "singapore": "SG",
    # Japan
    "tokyo": "JP", "osaka": "JP", "kyoto": "JP", "hiroshima": "JP",
    "japan": "JP",
    # Korea
    "seoul": "KR", "busan": "KR", "jeju": "KR", "korea": "KR",
    # Malaysia
    "kuala lumpur": "MY", "kl": "MY", "penang": "MY", "langkawi": "MY",
    "malaysia": "MY",
    # Indonesia
    "bali": "ID", "jakarta": "ID", "lombok": "ID", "yogyakarta": "ID",
    "indonesia": "ID",
    # USA
    "new york": "US", "los angeles": "US", "las vegas": "US",
    "miami": "US", "chicago": "US", "usa": "US",
    # France
    "paris": "FR", "nice": "FR", "lyon": "FR", "france": "FR",
    # UK
    "london": "GB", "manchester": "GB", "edinburgh": "GB",
    "uk": "GB", "england": "GB",
    # Others
    "rome": "IT", "milan": "IT", "venice": "IT", "italy": "IT",
    "barcelona": "ES", "madrid": "ES", "spain": "ES",
    "berlin": "DE", "munich": "DE", "germany": "DE",
    "sydney": "AU", "melbourne": "AU", "australia": "AU",
    "dubai": "AE", "uae": "AE",
    "beijing": "CN", "shanghai": "CN", "china": "CN",
    "amsterdam": "NL", "netherlands": "NL",
    "prague": "CZ", "czech": "CZ",
    "istanbul": "TR", "turkey": "TR",
    "cairo": "EG", "egypt": "EG",
    "mumbai": "IN", "delhi": "IN", "india": "IN",
}


def _infer_country_code(text: str) -> str | None:
    """Infer a 2-letter ISO country code from a city/country name string."""
    if not text:
        return None
    key = text.lower().strip()
    # Direct lookup
    if key in _CITY_COUNTRY_MAP:
        return _CITY_COUNTRY_MAP[key]
    # Substring match (e.g. "Ho Chi Minh City" contains "ho chi minh")
    for kw, code in _CITY_COUNTRY_MAP.items():
        if kw in key or key in kw:
            return code
    # Already a 2-letter code
    if len(key) == 2 and key.isalpha():
        return key.upper()
    return None


def _normalize_hotel(raw: dict) -> dict:
    """Normalize a LiteAPI hotel object (list or detail endpoint) to a flat dict."""
    # list endpoint uses: id, stars, rating, main_photo, city, country (lowercase)
    # detail endpoint uses: id, starRating, hotelImages[{url}], city, country
    hotel_id = raw.get("id") or raw.get("hotelId") or ""
    name = raw.get("name") or raw.get("hotelName") or ""
    description = raw.get("hotelDescription") or raw.get("shortDescription") or raw.get("description") or ""
    # Strip HTML tags from description
    import re
    description = re.sub(r"<[^>]+>", " ", description).strip()

    address = raw.get("address") or ""
    city = raw.get("city") or ""
    country = (raw.get("country") or "").upper()

    latitude = raw.get("latitude")
    longitude = raw.get("longitude")
    if not latitude and raw.get("location"):
        loc = raw["location"]
        latitude = loc.get("latitude")
        longitude = loc.get("longitude")

    # stars: list uses "stars", detail uses "starRating"
    stars = int(raw.get("stars") or raw.get("starRating") or 3)

    # images: list uses main_photo (string), detail uses hotelImages[{url}]
    hotel_images = raw.get("hotelImages") or []
    images = [img["url"] for img in hotel_images if isinstance(img, dict) and img.get("url")]
    if not images and raw.get("main_photo"):
        images = [raw["main_photo"]]
    elif not images and raw.get("thumbnail"):
        images = [raw["thumbnail"]]

    avg_rating = float(raw.get("rating") or 0)
    total_reviews = int(raw.get("reviewCount") or 0)
    min_price = raw.get("minRate") or raw.get("lowestRate")

    return {
        "liteapi_hotel_id": hotel_id,
        "name": name,
        "description": description,
        "address": address,
        "city": city,
        "country": country,
        "latitude": latitude,
        "longitude": longitude,
        "star_rating": stars,
        "property_type": raw.get("propertyType") or raw.get("hotelTypeId") and "hotel",
        "amenities": [],  # facilityIds are integers; skip for display
        "images": images,
        "min_room_price": float(min_price) if min_price else None,
        "currency": raw.get("currency") or "USD",
        "avg_rating": avg_rating,
        "total_reviews": total_reviews,
        "source": "liteapi",
    }


def _normalize_rate(room_type: dict) -> dict:
    """Normalize a LiteAPI roomType object from POST /hotels/rates response.

    Structure: roomType = { offerId, rates: [{name, maxOccupancy, boardName, retailRate, cancellationPolicies}], offerRetailRate }
    """
    # offerId is used for prebook
    offer_id = room_type.get("offerId") or room_type.get("rateId") or ""

    # First rate contains room name, board, occupancy, and cancellation policy
    rates = room_type.get("rates") or []
    first_rate = rates[0] if rates else {}

    room_name = first_rate.get("name") or room_type.get("roomName") or "Standard Room"

    # Price from offerRetailRate (top-level) or retailRate.total in first_rate
    offer_price = room_type.get("offerRetailRate", {})
    retail_rate = first_rate.get("retailRate", {})
    total_arr = retail_rate.get("total") or []
    price_raw = offer_price.get("amount") or (total_arr[0]["amount"] if total_arr else 0)
    currency_raw = offer_price.get("currency") or (total_arr[0]["currency"] if total_arr else "USD")

    max_guests = int(first_rate.get("maxOccupancy") or 2)
    board_name = first_rate.get("boardName") or first_rate.get("boardType") or ""

    cancel_policies = first_rate.get("cancellationPolicies") or {}
    refundable_tag = cancel_policies.get("refundableTag") or ""
    refundable = refundable_tag != "NRFN"

    return {
        "rate_id": offer_id,
        "room_name": room_name,
        "price": float(price_raw) if price_raw else 0.0,
        "currency": currency_raw or "USD",
        "cancellation_policy": board_name,
        "max_guests": max_guests,
        "images": [],
        "meal_type": board_name,
        "refundable": refundable,
    }


async def search_hotels(
    country_code: str = "",
    city: str = "",
    check_in: date | None = None,
    check_out: date | None = None,
    guests: int = 1,
    limit: int = 20,
) -> list[dict]:
    """Search hotels via LiteAPI /data/hotels. Returns normalized hotel dicts.

    LiteAPI requires countryCode. If not provided, it is inferred from the city name.
    Raises LiteAPIError if country cannot be determined.
    """
    # Resolve country code — required by LiteAPI
    resolved_cc = country_code or _infer_country_code(city) or ""
    if not resolved_cc:
        raise LiteAPIError(400, f"Cannot resolve country code for city '{city}'. Provide country explicitly.")

    params: dict[str, Any] = {"countryCode": resolved_cc, "limit": limit}
    if city:
        params["cityName"] = city

    try:
        resp = await _client().get("/data/hotels", params=params)
        _raise_for_status(resp)
        data = resp.json()
        hotels_raw = data.get("data") if isinstance(data, dict) else data
        hotels = hotels_raw if isinstance(hotels_raw, list) else []
        return [_normalize_hotel(h) for h in hotels]
    except LiteAPIError:
        raise
    except Exception as exc:
        logger.warning("LiteAPI search failed: %s", exc)
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def get_hotel(liteapi_hotel_id: str) -> dict:
    """Fetch a single hotel's detail from LiteAPI."""
    try:
        resp = await _client().get("/data/hotel", params={"hotelId": liteapi_hotel_id})
        _raise_for_status(resp)
        data = resp.json()
        raw = data.get("data") if isinstance(data, dict) else data
        if isinstance(raw, list):
            raw = raw[0] if raw else {}
        return _normalize_hotel(raw or {})
    except LiteAPIError:
        raise
    except Exception as exc:
        logger.warning("LiteAPI get_hotel failed: %s", exc)
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def get_rates(
    liteapi_hotel_id: str,
    check_in: date,
    check_out: date,
    guests: int = 1,
) -> list[dict]:
    """Fetch live room rates for a hotel via POST /hotels/rates."""
    body = {
        "hotelIds": [liteapi_hotel_id],
        "checkin": check_in.isoformat(),
        "checkout": check_out.isoformat(),
        "occupancies": [{"adults": guests, "children": []}],
        "currency": "USD",
        "guestNationality": "US",
    }
    try:
        resp = await _client().post("/hotels/rates", json=body)
        _raise_for_status(resp)
        data = resp.json()
        # Response: {"data": [{"hotelId": ..., "roomTypes": [...]}]}
        hotels_data = data.get("data") or []
        if not hotels_data:
            return []
        hotel_data = hotels_data[0] if isinstance(hotels_data, list) else hotels_data
        room_types = hotel_data.get("roomTypes") or hotel_data.get("rooms") or []
        return [_normalize_rate(rt) for rt in room_types]
    except LiteAPIError:
        raise
    except Exception as exc:
        logger.warning("LiteAPI get_rates failed: %s", exc)
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def prebook(rate_id: str, guests: int = 1) -> dict:
    """Prebook a rate to lock the price. Returns prebook_id + confirmed price.

    The sandbox may return an empty 200 body — treat that as success and use
    the offerId as the prebookId (standard sandbox behaviour).
    """
    body = {"offerId": rate_id}
    try:
        resp = await _client().post("/hotels/prebook", json=body)
        _raise_for_status(resp)
        # Sandbox returns empty 200; production returns prebookId JSON
        if not resp.content:
            return {"prebook_id": rate_id, "price": 0.0, "currency": "USD", "expires_at": None}
        data = resp.json()
        raw = data.get("data") or data
        return {
            "prebook_id": raw.get("prebookId") or raw.get("offerId") or rate_id,
            "price": float(raw.get("offerRetailRate", {}).get("amount") or raw.get("price") or 0),
            "currency": raw.get("offerRetailRate", {}).get("currency") or raw.get("currency") or "USD",
            "expires_at": raw.get("expiryTime"),
        }
    except LiteAPIError:
        raise
    except Exception as exc:
        logger.warning("LiteAPI prebook failed: %s", exc)
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def book(
    prebook_id: str,
    guest_first_name: str,
    guest_last_name: str,
    guest_email: str,
    payment_ref: str = "",
) -> dict:
    """Complete a booking via POST /hotels/book. Returns liteapi_booking_id."""
    body = {
        "prebookId": prebook_id,
        "guests": [
            {
                "firstName": guest_first_name,
                "lastName": guest_last_name,
                "email": guest_email,
            }
        ],
        "payment": {"holderName": f"{guest_first_name} {guest_last_name}", "method": "CREDIT_CARD"},
    }
    try:
        resp = await _client().post("/hotels/book", json=body)
        _raise_for_status(resp)
        data = resp.json()
        raw = data.get("data") or data
        return {
            "liteapi_booking_id": raw.get("bookingId") or raw.get("id", ""),
            "status": raw.get("status") or "CONFIRMED",
        }
    except LiteAPIError:
        raise
    except Exception as exc:
        logger.warning("LiteAPI book failed: %s", exc)
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def get_booking(liteapi_booking_id: str) -> dict:
    """Retrieve a booking by ID."""
    try:
        resp = await _client().get(f"/bookings/{liteapi_booking_id}")
        _raise_for_status(resp)
        return (resp.json().get("data") or resp.json())
    except LiteAPIError:
        raise
    except Exception as exc:
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def cancel_booking(liteapi_booking_id: str) -> bool:
    """Cancel a booking. Returns True on success."""
    try:
        resp = await _client().put(
            f"/bookings/{liteapi_booking_id}",
            json={"status": "CANCELLED"},
        )
        _raise_for_status(resp)
        return True
    except LiteAPIError as exc:
        logger.warning("LiteAPI cancel failed for %s: %s", liteapi_booking_id, exc.message)
        return False
    except Exception as exc:
        logger.warning("LiteAPI cancel error: %s", exc)
        return False
