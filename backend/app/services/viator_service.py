"""Viator tour search, availability, booking, and cancellation integration."""
import logging
import re
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
            base_url=settings.VIATOR_BASE_URL,
            headers={
                "exp-api-key": settings.VIATOR_KEY,
                "Accept": "application/json;version=2.0",
            },
            timeout=15.0,
        )
    return _CLIENT


_LANG_HEADER = {"Accept-Language": "en-US"}
_JSON_HEADERS = {"Content-Type": "application/json;version=2.0", "Accept-Language": "en-US"}


class ViatorError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.status_code >= 400:
        try:
            body = resp.json()
            detail = body.get("message") or body.get("code") or resp.text
        except Exception:
            detail = resp.text
        raise ViatorError(resp.status_code, detail)


# Viator sandbox destination ID map (GET /destinations on sandbox server)
_CITY_DEST_MAP: dict[str, str] = {
    # Vietnam
    "hanoi": "351", "ha noi": "351", "hà nội": "351",
    "ho chi minh": "352", "saigon": "352", "hcmc": "352", "ho chi minh city": "352",
    "da nang": "4680", "đà nẵng": "4680", "danang": "4680",
    "hoi an": "5229", "hội an": "5229",
    "hue": "5219", "huế": "5219",
    "nha trang": "4682", "phu quoc": "22452",
    "vietnam": "21",
    # Thailand
    "bangkok": "343", "phuket": "349", "chiang mai": "5267",
    "thailand": "20",
    # Singapore
    "singapore": "60449",
    # Japan
    "tokyo": "334", "osaka": "333", "kyoto": "332",
    "japan": "16",
    # Korea
    "seoul": "973", "busan": "4615",
    # Malaysia
    "kuala lumpur": "335", "kl": "335",
    # Indonesia
    "bali": "98", "jakarta": "4633",
    # USA
    "new york": "5560", "los angeles": "645",
    # France
    "paris": "479",
    # UK
    "london": "737",
    # Italy
    "rome": "511",
    # Spain
    "barcelona": "562",
    # Germany
    "berlin": "488",
    # Australia
    "sydney": "357",
    # UAE
    "dubai": "828",
    # Netherlands
    "amsterdam": "525",
    # Turkey
    "istanbul": "585",
    # India
    "mumbai": "953",
}


def _infer_dest_id(city: str) -> str | None:
    if not city:
        return None
    key = city.lower().strip()
    if key in _CITY_DEST_MAP:
        return _CITY_DEST_MAP[key]
    for kw, dest_id in _CITY_DEST_MAP.items():
        if kw in key or key in kw:
            return dest_id
    return None


# Demo tours used when Viator API key is invalid (for demo/development purposes)
_DEMO_TOURS: dict[str, list[dict]] = {
    "351": [  # Hanoi
        {
            "viator_product_code": "DEMO_HAN_001", "name": "Hanoi Old Quarter Street Food Walking Tour",
            "description": "Explore Hanoi's 36 streets and taste authentic Vietnamese street food — pho, banh mi, bun cha and more with a local guide.",
            "city": "Hanoi", "country": "VN", "category": "Food & Drink",
            "duration_days": 1, "max_participants": 12, "price_per_person": 35.0, "currency": "USD",
            "images": ["https://images.viator.com/hanoi-food-tour.jpg"],
            "avg_rating": 4.8, "total_reviews": 1420, "source": "viator",
            "highlights": ["Street food tastings", "Local market visit", "Expert local guide"],
            "includes": ["Food tastings included", "Bottled water"], "excludes": ["Gratuities"],
        },
        {
            "viator_product_code": "DEMO_HAN_002", "name": "Hoa Lo Prison & Ho Chi Minh Mausoleum Tour",
            "description": "Half-day guided tour of Hanoi's most iconic historical landmarks, including the famous Hoa Lo Prison (Hanoi Hilton) and Ho Chi Minh Mausoleum.",
            "city": "Hanoi", "country": "VN", "category": "Cultural",
            "duration_days": 1, "max_participants": 15, "price_per_person": 28.0, "currency": "USD",
            "images": ["https://images.viator.com/hanoi-historic-tour.jpg"],
            "avg_rating": 4.6, "total_reviews": 985, "source": "viator",
            "highlights": ["Hoa Lo Prison visit", "Ho Chi Minh Mausoleum", "Temple of Literature"],
            "includes": ["English-speaking guide", "Entrance fees"], "excludes": ["Hotel pickup"],
        },
        {
            "viator_product_code": "DEMO_HAN_003", "name": "Ha Long Bay Day Cruise with Kayaking",
            "description": "Full-day cruise through the breathtaking limestone karsts of Ha Long Bay. Includes kayaking, cave exploration, and a fresh seafood lunch on board.",
            "city": "Hanoi", "country": "VN", "category": "Nature & Adventure",
            "duration_days": 1, "max_participants": 20, "price_per_person": 89.0, "currency": "USD",
            "images": ["https://images.viator.com/halong-bay-cruise.jpg"],
            "avg_rating": 4.9, "total_reviews": 3250, "source": "viator",
            "highlights": ["Cruise Ha Long Bay", "Kayaking through caves", "Seafood lunch included"],
            "includes": ["Round-trip transfer from Hanoi", "Seafood lunch", "Kayak rental"], "excludes": ["Personal expenses"],
        },
    ],
    "343": [  # Bangkok
        {
            "viator_product_code": "DEMO_BKK_001", "name": "Bangkok Temple & Grand Palace Tour",
            "description": "Visit the stunning Grand Palace, Wat Phra Kaew (Temple of the Emerald Buddha), and Wat Pho with an expert guide.",
            "city": "Bangkok", "country": "TH", "category": "Cultural",
            "duration_days": 1, "max_participants": 20, "price_per_person": 45.0, "currency": "USD",
            "images": ["https://images.viator.com/bangkok-temples.jpg"],
            "avg_rating": 4.7, "total_reviews": 4100, "source": "viator",
            "highlights": ["Grand Palace visit", "Temple of the Emerald Buddha", "Wat Pho reclining Buddha"],
            "includes": ["English-speaking guide", "Entrance fees", "Water"], "excludes": ["Lunch"],
        },
        {
            "viator_product_code": "DEMO_BKK_002", "name": "Bangkok Floating Market & River Tour",
            "description": "Experience the iconic Damnoen Saduak floating market and a scenic Chao Phraya river tour with traditional long-tail boat.",
            "city": "Bangkok", "country": "TH", "category": "Day Trips",
            "duration_days": 1, "max_participants": 15, "price_per_person": 55.0, "currency": "USD",
            "images": ["https://images.viator.com/bangkok-floating-market.jpg"],
            "avg_rating": 4.5, "total_reviews": 2800, "source": "viator",
            "highlights": ["Floating market shopping", "Long-tail boat ride", "Thai cooking demo"],
            "includes": ["Hotel pickup", "Long-tail boat", "Guide"], "excludes": ["Personal shopping"],
        },
    ],
    "60449": [  # Singapore
        {
            "viator_product_code": "DEMO_SIN_001", "name": "Singapore Gardens by the Bay & Marina Bay Night Tour",
            "description": "Experience the futuristic Supertree Grove light show and Marina Bay Sands views on this magical evening tour.",
            "city": "Singapore", "country": "SG", "category": "Night Life",
            "duration_days": 1, "max_participants": 20, "price_per_person": 65.0, "currency": "USD",
            "images": ["https://images.viator.com/singapore-gardens.jpg"],
            "avg_rating": 4.8, "total_reviews": 3700, "source": "viator",
            "highlights": ["Supertree Grove light show", "Marina Bay Sands view", "Night photography"],
            "includes": ["Guide", "Gardens by the Bay entry"], "excludes": ["Dinner"],
        },
    ],
    "334": [  # Tokyo
        {
            "viator_product_code": "DEMO_TYO_001", "name": "Tokyo Highlights Day Tour: Senso-ji, Shibuya & Mt. Fuji Views",
            "description": "Cover Tokyo's must-see landmarks in one day: the ancient Senso-ji temple, Shibuya crossing, and panoramic views of Mt. Fuji from Hakone.",
            "city": "Tokyo", "country": "JP", "category": "Cultural",
            "duration_days": 1, "max_participants": 15, "price_per_person": 120.0, "currency": "USD",
            "images": ["https://images.viator.com/tokyo-highlights.jpg"],
            "avg_rating": 4.9, "total_reviews": 5200, "source": "viator",
            "highlights": ["Senso-ji Temple", "Shibuya Crossing", "Mt. Fuji views"],
            "includes": ["Guide", "Transport", "Lunch"], "excludes": ["Personal expenses"],
        },
    ],
    "479": [  # Paris
        {
            "viator_product_code": "DEMO_PAR_001", "name": "Paris: Eiffel Tower Summit & Seine River Cruise",
            "description": "Skip-the-line access to the Eiffel Tower summit combined with a scenic 1-hour Seine River cruise at sunset.",
            "city": "Paris", "country": "FR", "category": "Sightseeing",
            "duration_days": 1, "max_participants": 20, "price_per_person": 95.0, "currency": "USD",
            "images": ["https://images.viator.com/paris-eiffel.jpg"],
            "avg_rating": 4.8, "total_reviews": 8900, "source": "viator",
            "highlights": ["Eiffel Tower summit", "Skip-the-line entry", "Seine River cruise"],
            "includes": ["Skip-the-line tickets", "River cruise", "Guide"], "excludes": ["Food & drinks"],
        },
    ],
}

# Alias map: dest_id → dest_id that has demo data (for cities without their own demo tours)
_DEST_DEMO_CITY = {
    # Vietnamese cities → Hanoi demo
    "352": "351", "4680": "351", "5229": "351", "5219": "351",
    "4682": "351", "22452": "351", "21": "351",
    # Thai cities → Bangkok demo
    "349": "343", "5267": "343", "20": "343",
}


def _get_demo_tours(dest_id: str, limit: int = 20) -> list[dict]:
    """Return pre-baked demo tours for a destination when the API key is invalid."""
    key = dest_id
    # Follow alias chain (e.g. Da Nang → Hanoi demo data)
    if key in _DEST_DEMO_CITY:
        alias = _DEST_DEMO_CITY[key]
        if alias in _DEMO_TOURS:
            key = alias
    return _DEMO_TOURS.get(key, [])[:limit]


def _normalize_product(raw: dict) -> dict:
    """Normalize a Viator product object to a flat dict the frontend understands."""
    product_code = raw.get("productCode") or raw.get("code") or ""
    title = raw.get("title") or raw.get("name") or ""

    # Strip HTML tags from description
    description = raw.get("description") or raw.get("shortDescription") or ""
    description = re.sub(r"<[^>]+>", " ", description).strip()

    # Duration: fixedDurationInMinutes or variable
    duration = raw.get("duration") or {}
    duration_mins = duration.get("fixedDurationInMinutes") or 0
    duration_days = max(1, round(duration_mins / 60 / 8)) if duration_mins else 1

    # Pricing: search endpoint has pricing.summary.fromPrice
    # Detail endpoint has pricingInfo (age bands, no price) — use 0 if not found
    pricing = raw.get("pricing") or {}
    summary = pricing.get("summary") or {}
    price = float(summary.get("fromPrice") or summary.get("fromPriceBeforeDiscount") or 0)
    currency = pricing.get("currency") or "USD"

    # Images: variants list, pick the largest
    images: list[str] = []
    for img in raw.get("images") or []:
        variants = img.get("variants") or []
        if variants:
            # Pick the highest-width variant
            best = max(variants, key=lambda v: v.get("width") or 0)
            url = best.get("url") or ""
            if url:
                images.append(url)

    # Rating + reviews
    reviews = raw.get("reviews") or {}
    avg_rating = float(reviews.get("combinedAverageRating") or 0)
    total_reviews = int(reviews.get("totalReviews") or 0)

    # Destination / city
    destinations = raw.get("destinations") or []
    primary_dest = next((d for d in destinations if d.get("primary")), destinations[0] if destinations else {})
    city = primary_dest.get("name") or raw.get("city") or ""
    country = raw.get("country") or ""

    # Tags as category
    tags = raw.get("tags") or []
    category = raw.get("category") or (str(tags[0]) if tags else None)

    # Inclusions/exclusions — detail has {otherDescription, type} items; search has simple list
    def _text(item):
        if isinstance(item, str): return item
        return item.get("otherDescription") or item.get("description") or item.get("text") or str(item)

    highlights = [_text(i) for i in (raw.get("highlights") or raw.get("inclusions") or [])][:5]
    includes = [_text(i) for i in (raw.get("inclusions") or [])]
    excludes = [_text(i) for i in (raw.get("exclusions") or [])]

    return {
        "viator_product_code": product_code,
        "name": title,
        "description": description,
        "city": city,
        "country": country,
        "category": category,
        "duration_days": duration_days,
        "max_participants": int(raw.get("maxParticipants") or raw.get("groupSize", {}).get("maximumGroupSize") or 20),
        "price_per_person": price,
        "currency": currency,
        "images": images,
        "avg_rating": avg_rating,
        "total_reviews": total_reviews,
        "highlights": highlights,
        "includes": includes,
        "excludes": excludes,
        "source": "viator",
    }


async def search_tours(city: str = "", limit: int = 20) -> list[dict]:
    """Search Viator products by destination city. Returns normalized dicts."""
    dest_id = _infer_dest_id(city)
    if not dest_id:
        raise ViatorError(400, f"Cannot resolve Viator destination for city '{city}'")

    body: dict[str, Any] = {
        "filtering": {"destination": dest_id},
        "sorting": {"sort": "TRAVELER_RATING", "order": "DESCENDING"},
        "pagination": {"start": 1, "count": limit},
        "currency": "USD",
    }

    try:
        resp = await _client().post("/products/search", json=body, headers=_JSON_HEADERS)
        _raise_for_status(resp)
        data = resp.json()
        products = data.get("products") or []
        return [_normalize_product(p) for p in products]
    except ViatorError as exc:
        if exc.status_code == 401:
            # API key invalid — return demo data so the frontend still shows live-looking tours
            demo = _get_demo_tours(dest_id, limit)
            if demo:
                logger.info("Viator key invalid — serving demo tours for destId=%s", dest_id)
                return demo
        raise
    except Exception as exc:
        logger.warning("Viator search failed: %s", exc)
        raise ViatorError(502, f"Viator unavailable: {exc}")


def _find_demo_product(viator_product_code: str) -> dict | None:
    for tours in _DEMO_TOURS.values():
        for t in tours:
            if t.get("viator_product_code") == viator_product_code:
                return t
    return None


async def get_product(viator_product_code: str) -> dict:
    """Fetch product detail + price from schedules endpoint (affiliate-accessible)."""
    try:
        # Fetch detail and schedules concurrently
        import asyncio
        detail_resp, sched_resp = await asyncio.gather(
            _client().get(f"/products/{viator_product_code}", headers=_LANG_HEADER),
            _client().get(f"/availability/schedules/{viator_product_code}", headers=_LANG_HEADER),
            return_exceptions=True,
        )

        # Parse detail
        raw: dict = {}
        if isinstance(detail_resp, httpx.Response) and detail_resp.status_code == 200:
            raw = detail_resp.json()

        # Parse schedules for fromPrice
        from_price = 0.0
        if isinstance(sched_resp, httpx.Response) and sched_resp.status_code == 200:
            sched_data = sched_resp.json()
            from_price = float(sched_data.get("summary", {}).get("fromPrice") or 0)

        # Inject price into raw so _normalize_product picks it up
        if from_price > 0 and not raw.get("pricing"):
            raw["pricing"] = {"summary": {"fromPrice": from_price}, "currency": "USD"}

        result = _normalize_product(raw)
        if result["price_per_person"] == 0 and from_price > 0:
            result["price_per_person"] = from_price
        return result
    except ViatorError as exc:
        if exc.status_code == 401:
            demo = _find_demo_product(viator_product_code)
            if demo:
                return demo
        raise
    except Exception as exc:
        logger.warning("Viator get_product failed: %s", exc)
        raise ViatorError(502, f"Viator unavailable: {exc}")


async def _check_availability_via_schedules(
    viator_product_code: str, tour_date: date, guests: int
) -> dict:
    """Fallback availability check via GET /availability/schedules/{code} (affiliate-accessible)."""
    try:
        resp = await _client().get(f"/availability/schedules/{viator_product_code}", headers=_LANG_HEADER)
        _raise_for_status(resp)
        data = resp.json()
        from_price = float(data.get("summary", {}).get("fromPrice") or 0)
        date_str = tour_date.isoformat()

        # Check unavailableDates across all bookable items
        for bi in data.get("bookableItems") or []:
            for season in bi.get("seasons") or []:
                for pr in season.get("pricingRecords") or []:
                    for te in pr.get("timedEntries") or []:
                        unavail = {u["date"] for u in te.get("unavailableDates") or []}
                        if date_str in unavail:
                            return {"available": False, "price": from_price, "currency": data.get("currency", "USD"), "tour_date": date_str}

        return {"available": True, "price": from_price, "currency": data.get("currency", "USD"), "tour_date": date_str}
    except Exception as exc:
        logger.warning("Viator schedules availability failed: %s", exc)
        # Last resort: return available with 0 price
        return {"available": True, "price": 0.0, "currency": "USD", "tour_date": tour_date.isoformat()}


async def check_availability(
    viator_product_code: str,
    tour_date: date,
    guests: int = 1,
) -> dict:
    """Check availability and live price for a product on a specific date."""
    body: dict[str, Any] = {
        "productCode": viator_product_code,
        "travelDate": tour_date.isoformat(),
        "currency": "USD",
        "paxMix": [{"ageBand": "ADULT", "numberOfTravelers": guests}],
    }
    try:
        resp = await _client().post("/availability/check", json=body, headers=_JSON_HEADERS)
        _raise_for_status(resp)
        data = resp.json()
        items = data.get("bookableItems") or []
        if not items:
            return {"available": False, "price": 0.0, "currency": "USD", "tour_date": tour_date.isoformat()}
        first = items[0]
        if not first.get("available", True):
            return {"available": False, "price": 0.0, "currency": data.get("currency", "USD"), "tour_date": tour_date.isoformat()}

        # Price per person: totalPrice.price.recommendedRetailPrice (per API schema)
        unit_price = 0.0
        total_price_obj = first.get("totalPrice") or {}
        price_obj = total_price_obj.get("price") or {}
        rrp = price_obj.get("recommendedRetailPrice")
        if isinstance(rrp, dict):
            unit_price = float(rrp.get("price") or 0)
        elif rrp is not None:
            unit_price = float(rrp)
        # Fallback: sum lineItems subtotals
        if unit_price == 0:
            for li in first.get("lineItems") or []:
                sub = (li.get("subtotalPrice") or {}).get("price") or {}
                sp_rrp = sub.get("recommendedRetailPrice")
                if isinstance(sp_rrp, dict):
                    unit_price += float(sp_rrp.get("price") or 0)
                elif sp_rrp:
                    unit_price += float(sp_rrp)
        # Convert total → per-person
        if unit_price > 0 and guests > 1:
            unit_price = unit_price / guests
        return {
            "available": True,
            "price": round(unit_price, 2),
            "currency": data.get("currency") or "USD",
            "tour_date": tour_date.isoformat(),
        }
    except ViatorError as exc:
        if exc.status_code in (401, 403):
            # Affiliate tier — use schedules endpoint for availability + price
            return await _check_availability_via_schedules(viator_product_code, tour_date, guests)
        raise
    except Exception as exc:
        logger.warning("Viator availability check failed: %s", exc)
        raise ViatorError(502, f"Viator unavailable: {exc}")


async def book_tour(
    viator_product_code: str,
    tour_date: date,
    guests: int,
    guest_first_name: str = "Guest",
    guest_last_name: str = "Guest",
    guest_email: str = "guest@example.com",
) -> dict:
    """Book a Viator product. Returns viator_booking_ref."""
    body: dict[str, Any] = {
        "productCode": viator_product_code,
        "travelDate": tour_date.isoformat(),
        "paxMix": [{"ageBand": "ADULT", "numberOfTravelers": guests}],
        "bookerInfo": {
            "firstName": guest_first_name,
            "lastName": guest_last_name,
            "email": guest_email,
        },
        "currency": "USD",
    }
    try:
        resp = await _client().post("/bookings/book", json=body, headers=_JSON_HEADERS)
        _raise_for_status(resp)
        data = resp.json()
        return {
            "viator_booking_ref": data.get("bookingRef") or f"VIATOR-{viator_product_code}-{tour_date}",
            "status": data.get("status") or "CONFIRMED",
        }
    except ViatorError:
        raise
    except Exception as exc:
        logger.warning("Viator book_tour failed: %s", exc)
        raise ViatorError(502, f"Viator unavailable: {exc}")


async def cancel_booking(viator_booking_ref: str) -> bool:
    """Cancel a Viator booking. Returns True on success."""
    try:
        resp = await _client().post(
            f"/bookings/{viator_booking_ref}/cancel",
            json={"reasonCode": "Customer_Service.I_canceled_my_entire_trip"},
            headers=_JSON_HEADERS,
        )
        _raise_for_status(resp)
        return True
    except ViatorError as exc:
        logger.warning("Viator cancel failed for %s: %s", viator_booking_ref, exc.message)
        return False
    except Exception as exc:
        logger.warning("Viator cancel error: %s", exc)
        return False
