"""LiteAPI hotel search, rates, prebook, and booking integration."""
import logging
from datetime import date
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_CLIENT: httpx.AsyncClient | None = None
_DASHBOARD_CLIENT: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _CLIENT
    if _CLIENT is None or _CLIENT.is_closed:
        _CLIENT = httpx.AsyncClient(
            base_url=settings.LITEAPI_BASE_URL,
            headers={"X-API-Key": settings.LITEAPI_KEY, "Accept": "application/json"},
            timeout=15.0,
        )
    return _CLIENT


def _dashboard_client() -> httpx.AsyncClient:
    """Separate client for LiteAPI's dashboard API (da.liteapi.travel).

    Voucher management endpoints live on the dashboard host, not the main
    booking host. Same API key works.
    """
    global _DASHBOARD_CLIENT
    if _DASHBOARD_CLIENT is None or _DASHBOARD_CLIENT.is_closed:
        _DASHBOARD_CLIENT = httpx.AsyncClient(
            base_url=settings.LITEAPI_DASHBOARD_BASE_URL,
            headers={"X-API-Key": settings.LITEAPI_KEY, "Accept": "application/json"},
            timeout=15.0,
        )
    return _DASHBOARD_CLIENT


class LiteAPIError(Exception):
    def __init__(self, status_code: int, message: str, code: int | None = None):
        self.status_code = status_code
        self.message = message
        self.code = code  # LiteAPI's domain error code (e.g. 2001), distinct from HTTP status
        super().__init__(message)


def _extract_error(resp: httpx.Response) -> tuple[int | None, str]:
    """Pull (liteapi_code, message) out of a LiteAPI 4xx response.

    LiteAPI nests its domain error inside `{"error": {"code", "description", "message"}}`.
    Falls back to raw text when the response isn't JSON.
    """
    try:
        body = resp.json()
    except Exception:
        return None, resp.text
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        return err.get("code"), err.get("description") or err.get("message") or resp.text
    if isinstance(body, dict):
        return None, body.get("message") or resp.text
    return None, resp.text


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        code, detail = _extract_error(resp)
        raise LiteAPIError(resp.status_code, detail, code=code)


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


def _extract_facilities(raw: dict) -> list:
    """Extract named facilities from a LiteAPI hotel detail response.

    Returns [{id: int, name: str}, ...] from the raw 'facilities' field,
    which is present in the detail endpoint but not in the list endpoint.
    """
    raw_facilities = raw.get("facilities") or raw.get("hotelFacilities") or []
    result = []
    for f in raw_facilities:
        if isinstance(f, dict) and f.get("facilityId") and f.get("name"):
            result.append({"id": f["facilityId"], "name": f["name"]})
    return result


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
        "amenities": _extract_facilities(raw),
        "images": images,
        "min_room_price": float(min_price) if min_price else None,
        "currency": raw.get("currency") or "USD",
        "avg_rating": avg_rating,
        "total_reviews": total_reviews,
        "source": "liteapi",
    }


def _normalize_rate_plan(rate: dict, fallback_currency: str = "USD") -> dict:
    """Normalize a single rate plan inside a LiteAPI roomType.rates[]."""
    retail = rate.get("retailRate") or {}
    total_arr = retail.get("total") or []
    suggested_arr = retail.get("suggestedSellingPrice") or []
    taxes_arr = retail.get("taxesAndFees") or []

    price_raw = total_arr[0]["amount"] if total_arr else 0
    currency = total_arr[0]["currency"] if total_arr else fallback_currency
    original_price = suggested_arr[0]["amount"] if suggested_arr else None
    taxes_raw = taxes_arr[0]["amount"] if taxes_arr else None

    discount_percent = None
    if original_price and price_raw and original_price > price_raw:
        discount_percent = round((1 - price_raw / original_price) * 100)

    cancel = rate.get("cancellationPolicies") or {}
    refundable = cancel.get("refundableTag", "") != "NRFN"
    deadline = None
    policies = cancel.get("cancelPolicyInfos") or []
    if policies and isinstance(policies, list):
        deadline = policies[0].get("cancelTime") or policies[0].get("from")

    board = rate.get("boardName") or rate.get("boardType") or ""

    price = float(price_raw) if price_raw else 0.0
    taxes = float(taxes_raw) if taxes_raw is not None else None
    price_excl = (price - taxes) if (taxes is not None and price >= taxes) else None

    # LiteAPI's /hotels/prebook expects offerId, so prefer it over rateId
    # when the rate plan exposes both (newer v3.0 responses do).
    # Echo occupancy from LiteAPI when present so the frontend recommender can
    # filter "adults only" rates and align its per-room display with what the
    # supplier actually accepts. These fields are nullable — older sandbox
    # responses omit them, in which case the recommender trusts LiteAPI's own
    # request-side filtering.
    adult_count_raw = rate.get("adultCount")
    child_count_raw = rate.get("childCount")
    children_ages_raw = rate.get("childrenAges")
    occupancy_number_raw = rate.get("occupancyNumber")

    return {
        "rate_id": rate.get("offerId") or rate.get("rateId") or "",
        "board_name": board,
        "refundable": refundable,
        "cancellation_policy": board,
        "cancellation_deadline": deadline,
        "price": price,
        "price_excl_taxes": price_excl,
        "taxes": taxes,
        "original_price": float(original_price) if original_price else None,
        "discount_percent": discount_percent,
        "currency": currency or fallback_currency,
        "max_occupancy": int(rate.get("maxOccupancy") or 2),
        "adult_count": int(adult_count_raw) if adult_count_raw is not None else None,
        "child_count": int(child_count_raw) if child_count_raw is not None else None,
        "children_ages": [int(a) for a in children_ages_raw] if isinstance(children_ages_raw, list) else None,
        "occupancy_number": int(occupancy_number_raw) if occupancy_number_raw is not None else None,
    }


def _normalize_room_type(room_type: dict) -> dict:
    """Normalize a LiteAPI roomType object from POST /hotels/rates response.

    Structure: roomType = {
        offerId, roomTypeId, rates: [...], offerRetailRate, roomImages, amenities
    }
    Returns a room-type group with a `rates[]` array preserving every rate plan
    so the UI can render Booking.com-style multi-rate rows under one room.
    """
    rates = room_type.get("rates") or []
    first_rate = rates[0] if rates else {}

    room_type_id = (
        room_type.get("roomTypeId")
        or room_type.get("offerId")
        or first_rate.get("rateId")
        or ""
    )
    room_name = (
        first_rate.get("name")
        or room_type.get("roomName")
        or room_type.get("name")
        or "Standard Room"
    )

    offer_price = room_type.get("offerRetailRate") or {}
    fallback_currency = offer_price.get("currency") or "USD"

    max_guests = int(
        first_rate.get("maxOccupancy")
        or room_type.get("maxOccupancy")
        or 2
    )

    images: list[str] = []
    raw_images = room_type.get("roomImages") or first_rate.get("roomImages") or []
    for img in raw_images:
        if isinstance(img, dict):
            url = img.get("url") or img.get("imageUrl")
            if url:
                images.append(url)
        elif isinstance(img, str):
            images.append(img)

    raw_amenities = room_type.get("amenities") or first_rate.get("amenities") or []
    amenities: list[str] = []
    for a in raw_amenities:
        if isinstance(a, dict):
            name = a.get("name") or a.get("description")
            if name:
                amenities.append(name)
        elif isinstance(a, str):
            amenities.append(a)

    # LiteAPI v3.0 exposes `offerId` only at the roomType level — the rate plan
    # itself has only an internal `rateId`. /rates/prebook requires the parent
    # offerId, so propagate it down to each rate plan so the frontend stores
    # the right identifier for the booking flow.
    parent_offer_id = room_type.get("offerId") or ""
    rate_plans = [_normalize_rate_plan(r, fallback_currency) for r in rates]
    if parent_offer_id:
        for plan in rate_plans:
            plan["rate_id"] = parent_offer_id

    return {
        "room_type_id": room_type_id,
        "room_name": room_name,
        "max_guests": max_guests,
        "images": images,
        "amenities": amenities,
        "rates": rate_plans,
    }


def _strip_room_type_prices(rt: dict) -> dict:
    """Return a room-type group with prices/policies stripped — for the no-dates catalog."""
    return {
        "room_type_id": rt.get("room_type_id") or "",
        "room_name": rt.get("room_name") or "",
        "max_guests": rt.get("max_guests") or 2,
        "images": rt.get("images") or [],
        "amenities": rt.get("amenities") or [],
        "rates": [],
    }


async def list_facilities() -> list[dict]:
    """Fetch canonical hotel facility list from LiteAPI GET /data/facilities.

    Returns [{id: int, name: str}, ...]. The list is essentially static;
    callers should cache the result (e.g. 24 h in Redis).
    """
    try:
        resp = await _client().get("/data/facilities")
        _raise_for_status(resp)
        data = resp.json()
        raw = data.get("data") if isinstance(data, dict) else data
        facilities = raw if isinstance(raw, list) else []
        result = []
        for item in facilities:
            fid = item.get("facility_id")
            name = item.get("facility") or ""
            # Prefer English translation when available
            for t in item.get("translation") or []:
                if t.get("lang") == "en":
                    name = t.get("facility") or name
                    break
            if fid and name:
                result.append({"id": fid, "name": name})
        return result
    except LiteAPIError:
        raise
    except Exception as exc:
        logger.warning("LiteAPI list_facilities failed: %s", exc)
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def search_hotels(
    country_code: str = "",
    city: str = "",
    check_in: date | None = None,
    check_out: date | None = None,
    guests: int = 1,
    limit: int = 20,
    facility_ids: list[int] | None = None,
    strict_facilities_filtering: bool = False,
    hotel_type_ids: list[int] | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float | None = None,
) -> list[dict]:
    """Search hotels via LiteAPI /data/hotels. Returns normalized hotel dicts.

    Two modes:
    - **Geo mode** (when both `latitude` and `longitude` provided): proximity
      search; countryCode/cityName are optional and skipped. LiteAPI's
      `/data/hotels` accepts `radius` in metres.
    - **City mode** (default): requires countryCode (inferred from city name
      when omitted). Raises LiteAPIError if country can't be resolved.
    """
    params: dict[str, Any] = {"limit": limit}

    if latitude is not None and longitude is not None:
        params["latitude"] = latitude
        params["longitude"] = longitude
        params["radius"] = int((radius_km or 5) * 1000)
    else:
        resolved_cc = country_code or _infer_country_code(city) or ""
        if not resolved_cc:
            raise LiteAPIError(400, f"Cannot resolve country code for city '{city}'. Provide country explicitly.")
        params["countryCode"] = resolved_cc
        if city:
            params["cityName"] = city

    if facility_ids:
        # LiteAPI expects a comma-separated string, e.g. "107,301"
        params["facilityIds"] = ",".join(str(fid) for fid in facility_ids)
        params["strictFacilitiesFiltering"] = strict_facilities_filtering
    if hotel_type_ids:
        params["hotelTypeIds"] = ",".join(str(tid) for tid in hotel_type_ids)

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


def _normalize_review(raw: dict) -> dict:
    """Normalize a LiteAPI guest review to the same shape ReviewCard expects.

    LiteAPI returns ratings on a 0–10 scale; the UI displays 0–5 stars,
    so we halve the score and round to one decimal. Pros/cons are folded
    into a single comment block alongside the headline.
    """
    name = raw.get("name") or raw.get("author") or "Guest"
    country = raw.get("country") or ""
    full_name = f"{name} ({country})" if country else name

    raw_score = raw.get("averageScore") or raw.get("rating") or 0
    try:
        score10 = float(raw_score)
    except (TypeError, ValueError):
        score10 = 0.0
    rating = round(score10 / 2, 1) if score10 > 5 else round(score10, 1)

    headline = (raw.get("headline") or "").strip()
    pros = (raw.get("pros") or "").strip()
    cons = (raw.get("cons") or "").strip()
    parts: list[str] = []
    if headline:
        parts.append(headline)
    if pros:
        parts.append(f"+ {pros}")
    if cons:
        parts.append(f"- {cons}")
    comment = "\n\n".join(parts) if parts else None

    review_id = raw.get("id") or raw.get("reviewId") or f"liteapi-{name}-{raw.get('date', '')}"

    return {
        "id": str(review_id),
        "user": {"full_name": full_name},
        "rating": rating,
        "comment": comment,
        "created_at": raw.get("date") or raw.get("createdAt"),
    }


async def get_hotel_reviews(liteapi_hotel_id: str, limit: int = 50) -> list[dict]:
    """Fetch guest reviews for a LiteAPI hotel via GET /data/reviews.

    Returns reviews normalized to the shape the ReviewCard component expects.
    Quietly returns [] if LiteAPI has no reviews for the hotel.
    """
    try:
        resp = await _client().get(
            "/data/reviews",
            params={"hotelId": liteapi_hotel_id, "limit": limit, "timeout": 5},
        )
        _raise_for_status(resp)
        data = resp.json()
        raw = data.get("data") if isinstance(data, dict) else data
        reviews = raw if isinstance(raw, list) else []
        return [_normalize_review(r) for r in reviews]
    except LiteAPIError as exc:
        if exc.status_code == 404:
            return []
        raise
    except Exception as exc:
        logger.warning("LiteAPI get_hotel_reviews failed: %s", exc)
        return []


async def get_min_rates_batch(
    hotel_ids: list[str],
    check_in: date,
    check_out: date,
    guests: int = 1,
    children_ages: list[int] | None = None,
) -> dict[str, float]:
    """Batch-fetch minimum room rate for multiple LiteAPI hotels.

    Calls POST /hotels/min-rates, which returns the cheapest available rate per
    hotel as a flat object `{hotelId, price, suggestedSellingPrice, offerId}` —
    much lighter than /hotels/rates for populating "from $X" on search cards.
    Returns {liteapi_hotel_id: min_price}; hotels with no availability are omitted.

    ``children_ages`` is a list of child ages (0–17). When provided, suppliers
    apply their own per-hotel child-pricing policy.
    """
    if not hotel_ids:
        return {}
    body = {
        "hotelIds": hotel_ids,
        "checkin": check_in.isoformat(),
        "checkout": check_out.isoformat(),
        "occupancies": [{"adults": guests, "children": list(children_ages or [])}],
        "currency": "USD",
        "guestNationality": "US",
    }
    try:
        resp = await _client().post("/hotels/min-rates", json=body)
        _raise_for_status(resp)
        data = resp.json()
        hotels_data = data.get("data") or []
        result: dict[str, float] = {}
        for entry in hotels_data:
            hid = entry.get("hotelId") or entry.get("id") or ""
            price_raw = entry.get("price")
            if not hid or price_raw is None:
                continue
            try:
                price = float(price_raw)
            except (TypeError, ValueError):
                continue
            if price > 0:
                result[hid] = price
        return result
    except LiteAPIError as exc:
        # 2001 "no availability found" is normal for date ranges with no inventory.
        if exc.code == 2001 or exc.status_code == 404:
            return {}
        logger.warning("LiteAPI batch min-rates failed: %s", exc)
        return {}
    except Exception as exc:
        logger.warning("LiteAPI batch min-rates failed: %s", exc)
        return {}


async def get_rates(
    liteapi_hotel_id: str,
    check_in: date,
    check_out: date,
    guests: int = 1,
    rooms: int = 1,
    adults: int | None = None,
    children_ages: list[int] | None = None,
) -> list[dict]:
    """Fetch live room rates for a hotel via POST /hotels/rates.

    Returns a list of room-type groups, each with a `rates[]` array of rate plans.
    When ``rooms > 1``, the request is split into multiple occupancies of
    roughly equal size so LiteAPI knows the search is for a multi-room booking.

    Children pricing: each room's ``children`` slot gets an integer age list.
    Children are distributed round-robin across rooms so supplier policies can
    apply per-room. When only ``guests`` is provided (legacy callers) every
    guest is sent as an adult.
    """
    rooms = max(1, rooms)
    ages = list(children_ages or [])
    if adults is None:
        # Legacy single-int "guests" path → treat all as adults, no children.
        adults = guests
    adults = max(rooms, int(adults))  # at least one adult per room

    base_adults = adults // rooms
    extra_adults = adults - base_adults * rooms
    adults_per_room = [base_adults + (1 if i < extra_adults else 0) for i in range(rooms)]
    children_per_room: list[list[int]] = [[] for _ in range(rooms)]
    for idx, age in enumerate(ages):
        children_per_room[idx % rooms].append(int(age))
    occupancies = [
        {"adults": adults_per_room[i], "children": children_per_room[i]}
        for i in range(rooms)
    ]
    body = {
        "hotelIds": [liteapi_hotel_id],
        "checkin": check_in.isoformat(),
        "checkout": check_out.isoformat(),
        "occupancies": occupancies,
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
        return [_normalize_room_type(rt) for rt in room_types]
    except LiteAPIError:
        raise
    except Exception as exc:
        logger.warning("LiteAPI get_rates failed: %s", exc)
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def get_room_types_catalog(liteapi_hotel_id: str) -> list[dict]:
    """Fetch the room-type catalog for a hotel without exposing prices.

    Used for the no-dates state of the availability table — probes LiteAPI rates
    with a default 2-night window 7 days out, then strips price/cancellation data.
    """
    from datetime import timedelta
    today = date.today()
    probe_in = today + timedelta(days=7)
    probe_out = probe_in + timedelta(days=2)
    try:
        room_types = await get_rates(liteapi_hotel_id, probe_in, probe_out, guests=1)
    except LiteAPIError:
        return []
    return [_strip_room_type_prices(rt) for rt in room_types]


def _parse_price_block(raw: dict, fallback_currency: str = "USD") -> tuple[float, str]:
    """Extract (price, currency) from a LiteAPI prebook response.

    LiteAPI v3.0 returns the confirmed amount under different keys depending on
    sandbox vs production; we probe the common shapes in order.
    """
    # Shape A: { "price": 123.45, "currency": "USD" }
    if raw.get("price") is not None:
        return float(raw["price"]), raw.get("currency") or fallback_currency
    # Shape B: { "offerRetailRate": {"amount": 123.45, "currency": "USD"} }
    retail = raw.get("offerRetailRate")
    if isinstance(retail, dict) and retail.get("amount") is not None:
        return float(retail["amount"]), retail.get("currency") or fallback_currency
    # Shape C: { "total": [{"amount": 123.45, "currency": "USD"}] }
    total = raw.get("total")
    if isinstance(total, list) and total and total[0].get("amount") is not None:
        return float(total[0]["amount"]), total[0].get("currency") or fallback_currency
    return 0.0, fallback_currency


async def prebook(
    rate_id: str,
    guests: int = 1,
    voucher_code: str | None = None,
    use_payment_sdk: bool = False,
) -> dict:
    """Prebook a rate via POST /hotels/prebook to lock price and inventory.

    Returns a dict with:
        prebook_id        — pass this to book()
        price, currency   — supplier-confirmed price (may differ from quoted)
        supplier          — supplier name for audit
        secret_key        — Stripe clientSecret if use_payment_sdk=True
        transaction_id    — PaymentIntent ID if use_payment_sdk=True
        payment_types     — list of accepted payment.method values for /hotels/book
        expires_at        — ISO datetime or seconds-from-now; caller normalises
    """
    body: dict[str, Any] = {"offerId": rate_id, "usePaymentSdk": use_payment_sdk}
    if voucher_code:
        body["voucherCode"] = voucher_code

    try:
        # LiteAPI v3.0 booking ops live under `/rates/...`, NOT `/hotels/...`.
        # The earlier `/hotels/prebook` path returned 404 (rendered as a gzip-empty
        # body to httpx) which silently bypassed the booking flow.
        resp = await _client().post("/rates/prebook", json=body)
        _raise_for_status(resp)
        if not resp.content:
            raise LiteAPIError(502, "LiteAPI prebook returned empty body")
        data = resp.json()
        raw = data.get("data") or data
        prebook_id = raw.get("prebookId") or raw.get("preBookId")
        if not prebook_id:
            raise LiteAPIError(502, f"LiteAPI prebook missing prebookId: {raw}")
        price, currency = _parse_price_block(raw)
        # expiry: either "expireInSeconds" (int) or "expiryTime" (ISO)
        expires_at = raw.get("expiryTime") or raw.get("expireInSeconds")
        return {
            "prebook_id": prebook_id,
            "price": price,
            "currency": currency,
            "supplier": raw.get("supplier") or raw.get("supplierName"),
            "secret_key": raw.get("secretKey"),
            "transaction_id": raw.get("transactionId"),
            "payment_types": raw.get("paymentTypes") or [],
            "expires_at": expires_at,
        }
    except LiteAPIError:
        raise
    except Exception as exc:
        logger.warning("LiteAPI prebook failed: %s", exc)
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def book(
    prebook_id: str,
    holder: dict,
    guests: list[dict],
    payment: dict | None = None,
    client_reference: str = "",
    transaction_id: str | None = None,
) -> dict:
    """Complete a booking via POST /hotels/book. Returns liteapi_booking_id + status.

    holder:    {"firstName", "lastName", "email", "phoneNumber"?}
    guests:    [{"occupancyNumber":1, "firstName","lastName","email","remarks"?}, ...]
               one entry per room (the lead guest); occupancyNumber starts at 1.
    payment:   defaults to {"method": "ACC_CREDIT_CARD"} for the partner-pre-paid flow
               (LiteAPI sandbox accepts this without card details). For the LiteAPI
               Stripe SDK flow, pass {"method": "TRANSACTION_ID"} together with
               transaction_id from prebook().
    """
    if payment is None:
        payment = {"method": "ACC_CREDIT_CARD"}
    if transaction_id and "transactionId" not in payment:
        payment = {**payment, "transactionId": transaction_id}

    body: dict[str, Any] = {
        "prebookId": prebook_id,
        "holder": holder,
        "guests": guests,
        "payment": payment,
    }
    if client_reference:
        body["clientReference"] = client_reference

    try:
        # LiteAPI v3.0 booking ops live under `/rates/...`, NOT `/hotels/...`.
        resp = await _client().post("/rates/book", json=body)
        _raise_for_status(resp)
        data = resp.json()
        raw = data.get("data") or data
        booking_id = raw.get("bookingId") or raw.get("id")
        if not booking_id:
            raise LiteAPIError(502, f"LiteAPI book missing bookingId: {raw}")
        return {
            "liteapi_booking_id": booking_id,
            "status": raw.get("status") or "CONFIRMED",
            "supplier_booking_id": raw.get("supplierBookingId"),
            "supplier": raw.get("supplier"),
            "hotel_confirmation_code": raw.get("hotelConfirmationCode"),
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


async def get_prebook(prebook_id: str) -> dict:
    """Retrieve a prebook by ID (GET /prebooks/{prebookId})."""
    try:
        resp = await _client().get(f"/prebooks/{prebook_id}")
        _raise_for_status(resp)
        return (resp.json().get("data") or resp.json())
    except LiteAPIError:
        raise
    except Exception as exc:
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def cancel_booking(liteapi_booking_id: str) -> dict | None:
    """
    Cancel a LiteAPI booking.

    Per LiteAPI docs (PUT /bookings/{id}, no body):
    returns 200 with the booking object, or 304 if already cancelled (idempotent).
    LiteAPI applies the rate plan's cancellation policy automatically and returns
    `status` ("CANCELLED" if fully refundable, "CANCELLED_WITH_CHARGES" if past
    the deadline or non-refundable), plus `cancellation_fee` and `refund_amount`.

    Returns a dict with the supplier's cancellation result on success, or None
    on failure. We never raise — the local cancel still proceeds either way.
    """
    try:
        resp = await _client().put(f"/bookings/{liteapi_booking_id}")
        # 304 = already cancelled; treat as success and synthesise the status
        if resp.status_code == 304:
            return {
                "status": "CANCELLED",
                "cancellation_fee": 0.0,
                "refund_amount": None,
                "currency": None,
                "already_cancelled": True,
            }
        _raise_for_status(resp)
        payload = resp.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        data = data or payload or {}
        return {
            "status": data.get("status") or "CANCELLED",
            "cancellation_fee": data.get("cancellation_fee"),
            "refund_amount": data.get("refund_amount"),
            "currency": data.get("currency"),
            "already_cancelled": False,
        }
    except LiteAPIError as exc:
        logger.warning("LiteAPI cancel failed for %s: %s", liteapi_booking_id, exc.message)
        return None
    except Exception as exc:
        logger.warning("LiteAPI cancel error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Voucher management (dashboard API: https://da.liteapi.travel/vouchers)
# ---------------------------------------------------------------------------

def _unwrap_voucher(data: dict) -> dict:
    """LiteAPI's voucher endpoints return one of:
        {"voucher": {...}}       — POST/PUT/GET single
        {"vouchers": [...]}      — GET list
        {"data": {...}}          — some endpoints (defensive)
        {...}                    — the bare object
    Return the inner object for single-voucher responses, or the list dict
    untouched so callers can pick the right key.
    """
    if not isinstance(data, dict):
        return data
    if "voucher" in data and isinstance(data["voucher"], dict):
        return data["voucher"]
    if "data" in data and isinstance(data["data"], dict):
        return data["data"]
    return data


async def create_voucher(payload: dict) -> dict:
    """POST /vouchers. Returns the LiteAPI voucher object including its id."""
    try:
        resp = await _dashboard_client().post("/vouchers", json=payload)
        _raise_for_status(resp)
        return _unwrap_voucher(resp.json())
    except LiteAPIError:
        raise
    except Exception as exc:
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def update_voucher(liteapi_id: str, payload: dict) -> dict:
    """PUT /vouchers/{id}. LiteAPI requires all fields (not patch semantics)."""
    try:
        resp = await _dashboard_client().put(f"/vouchers/{liteapi_id}", json=payload)
        _raise_for_status(resp)
        return _unwrap_voucher(resp.json())
    except LiteAPIError:
        raise
    except Exception as exc:
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def set_voucher_status(liteapi_id: str, status_value: str) -> dict:
    """PUT /vouchers/{id}/status. status_value: 'active' or 'inactive'."""
    try:
        resp = await _dashboard_client().put(
            f"/vouchers/{liteapi_id}/status", json={"status": status_value}
        )
        _raise_for_status(resp)
        return _unwrap_voucher(resp.json())
    except LiteAPIError:
        raise
    except Exception as exc:
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def delete_voucher(liteapi_id: str) -> None:
    """DELETE /vouchers/{id}/. Permanent — caller should call only when local
    delete is intended."""
    try:
        resp = await _dashboard_client().delete(f"/vouchers/{liteapi_id}/")
        _raise_for_status(resp)
    except LiteAPIError:
        raise
    except Exception as exc:
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def get_voucher(liteapi_id: str) -> dict:
    """GET /vouchers/{voucherID}."""
    try:
        resp = await _dashboard_client().get(f"/vouchers/{liteapi_id}")
        _raise_for_status(resp)
        return _unwrap_voucher(resp.json())
    except LiteAPIError:
        raise
    except Exception as exc:
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def list_vouchers() -> list[dict]:
    """GET /vouchers. Returns the raw vouchers[] list, used for code → id lookup."""
    try:
        resp = await _dashboard_client().get("/vouchers")
        _raise_for_status(resp)
        body = resp.json()
        if isinstance(body, dict):
            return body.get("vouchers") or body.get("data") or []
        return body if isinstance(body, list) else []
    except LiteAPIError:
        raise
    except Exception as exc:
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")


async def get_voucher_history() -> dict:
    """GET /vouchers/history. Returns supplier-side usage records."""
    try:
        resp = await _dashboard_client().get("/vouchers/history")
        _raise_for_status(resp)
        data = resp.json()
        return data.get("data") or data
    except LiteAPIError:
        raise
    except Exception as exc:
        raise LiteAPIError(502, f"LiteAPI unavailable: {exc}")
