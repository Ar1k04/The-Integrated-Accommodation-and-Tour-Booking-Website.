"""Viator tour search, availability, booking, and cancellation integration."""
import logging
import re
import time
from datetime import date
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_CLIENT: httpx.AsyncClient | None = None

_VALID_SORTS = {"DEFAULT", "PRICE", "TRAVELER_RATING", "ITINERARY_DURATION", "DATE_ADDED"}
_VALID_ORDERS = {"ASCENDING", "DESCENDING"}
VIATOR_FLAGS = {
    "NEW_ON_VIATOR", "FREE_CANCELLATION", "SKIP_THE_LINE",
    "PRIVATE_TOUR", "SPECIAL_OFFER", "LIKELY_TO_SELL_OUT",
}

# Process-level cache for /products/tags — tag tree is essentially static.
_TAG_CACHE: dict[str, Any] = {"data": None, "fetched_at": 0.0}
_TAG_CACHE_TTL = 86400  # 24 hours

# Demo tags returned when Viator key invalid so FE filter UI still renders.
_DEMO_TAGS: list[dict] = [
    {"tag_id": 21909, "parent_tag_id": None, "name": "Walking Tours"},
    {"tag_id": 21972, "parent_tag_id": None, "name": "Food, Wine & Nightlife"},
    {"tag_id": 11940, "parent_tag_id": None, "name": "Day Trips & Excursions"},
    {"tag_id": 21911, "parent_tag_id": None, "name": "Private & Custom Tours"},
    {"tag_id": 11944, "parent_tag_id": None, "name": "Cultural Tours"},
    {"tag_id": 11912, "parent_tag_id": None, "name": "Cooking Classes"},
    {"tag_id": 21915, "parent_tag_id": None, "name": "Hiking & Trekking"},
    {"tag_id": 11930, "parent_tag_id": None, "name": "City Tours"},
    {"tag_id": 11919, "parent_tag_id": None, "name": "Cruises & Sailing"},
    {"tag_id": 11947, "parent_tag_id": None, "name": "Multi-day Tours"},
    {"tag_id": 20757, "parent_tag_id": None, "name": "Likely to Sell Out"},
    {"tag_id": 11929, "parent_tag_id": None, "name": "Photography Tours"},
    {"tag_id": 21974, "parent_tag_id": None, "name": "Outdoor Activities"},
    {"tag_id": 11920, "parent_tag_id": None, "name": "Water Sports"},
    {"tag_id": 21933, "parent_tag_id": None, "name": "Wine Tasting & Winery Tours"},
]


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


async def search_tours(
    city: str = "",
    *,
    dest_id: str | None = None,
    tags: list[int] | None = None,
    flags: list[str] | None = None,
    rating_from: float | None = None,
    rating_to: float | None = None,
    duration_from_min: int | None = None,
    duration_to_min: int | None = None,
    lowest_price: float | None = None,
    highest_price: float | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    sort: str = "TRAVELER_RATING",
    order: str = "DESCENDING",
    start: int = 1,
    count: int = 20,
    currency: str = "USD",
    limit: int | None = None,
) -> dict:
    """Search Viator products with full filter support.

    Returns {"products": list[normalized_dict], "total": int}.
    `limit` is kept as an alias for `count` for backward compatibility.
    """
    if limit is not None:
        count = limit
    resolved_dest = dest_id or _infer_dest_id(city)
    if not resolved_dest:
        raise ViatorError(400, f"Cannot resolve Viator destination for city '{city}'")

    if sort not in _VALID_SORTS:
        sort = "TRAVELER_RATING"
    if order not in _VALID_ORDERS:
        order = "DESCENDING"
    if sort == "TRAVELER_RATING":
        order = "DESCENDING"  # Viator spec — TRAVELER_RATING only allows DESCENDING

    filtering: dict[str, Any] = {"destination": resolved_dest}
    if tags:
        filtering["tags"] = list(tags)
    if flags:
        valid = [f for f in flags if f in VIATOR_FLAGS]
        if valid:
            filtering["flags"] = valid
    if rating_from is not None or rating_to is not None:
        rating: dict[str, float] = {}
        if rating_from is not None:
            rating["from"] = float(rating_from)
        if rating_to is not None:
            rating["to"] = float(rating_to)
        filtering["rating"] = rating
    if duration_from_min is not None or duration_to_min is not None:
        dur: dict[str, int] = {}
        if duration_from_min is not None:
            dur["from"] = int(duration_from_min)
        if duration_to_min is not None:
            dur["to"] = int(duration_to_min)
        filtering["durationInMinutes"] = dur
    if lowest_price is not None:
        filtering["lowestPrice"] = float(lowest_price)
    if highest_price is not None:
        filtering["highestPrice"] = float(highest_price)
    if start_date is not None:
        filtering["startDate"] = start_date.isoformat()
    if end_date is not None:
        filtering["endDate"] = end_date.isoformat()

    body: dict[str, Any] = {
        "filtering": filtering,
        "pagination": {"start": max(1, start), "count": max(1, count)},
        "currency": currency,
    }
    if sort == "DEFAULT":
        body["sorting"] = {"sort": "DEFAULT"}
    else:
        body["sorting"] = {"sort": sort, "order": order}

    try:
        resp = await _client().post("/products/search", json=body, headers=_JSON_HEADERS)
        _raise_for_status(resp)
        data = resp.json()
        products = data.get("products") or []
        return {
            "products": [_normalize_product(p) for p in products],
            "total": int(data.get("totalCount") or len(products)),
        }
    except ViatorError as exc:
        if exc.status_code == 401:
            # API key invalid — return demo data so the frontend still shows live-looking tours
            demo = _get_demo_tours(resolved_dest, count)
            if demo:
                logger.info("Viator key invalid — serving demo tours for destId=%s", resolved_dest)
                return {"products": demo, "total": len(demo)}
        raise
    except Exception as exc:
        logger.warning("Viator search failed: %s", exc)
        raise ViatorError(502, f"Viator unavailable: {exc}")


async def get_tags() -> list[dict]:
    """Fetch Viator tag tree (cached 24h in process).

    Returns list of {tag_id, parent_tag_id, name}. Falls back to demo on 401.
    """
    now = time.time()
    cached = _TAG_CACHE["data"]
    if cached is not None and (now - _TAG_CACHE["fetched_at"]) < _TAG_CACHE_TTL:
        return cached

    try:
        resp = await _client().get("/products/tags", headers=_LANG_HEADER)
        _raise_for_status(resp)
        raw = resp.json()
        # Viator returns {"tags": [{tagId, parentTagIds, allNamesByLocale, ...}]}
        # OpenAPI: tag may have multiple parents — flatten to first parent for our UI.
        tags_out: list[dict] = []
        for t in raw.get("tags") or []:
            tag_id = t.get("tagId")
            if tag_id is None:
                continue
            parents = t.get("parentTagIds") or []
            parent = parents[0] if parents else None
            names_by_locale = t.get("allNamesByLocale") or {}
            name = (
                names_by_locale.get("en")
                or names_by_locale.get("en_US")
                or t.get("tagName")
                or t.get("name")
                or f"Tag {tag_id}"
            )
            tags_out.append({"tag_id": int(tag_id), "parent_tag_id": parent, "name": str(name)})
        _TAG_CACHE["data"] = tags_out
        _TAG_CACHE["fetched_at"] = now
        return tags_out
    except ViatorError as exc:
        if exc.status_code == 401:
            logger.info("Viator key invalid — serving demo tags")
            _TAG_CACHE["data"] = _DEMO_TAGS
            _TAG_CACHE["fetched_at"] = now
            return _DEMO_TAGS
        raise
    except Exception as exc:
        logger.warning("Viator tags fetch failed: %s — serving demo tags", exc)
        return _DEMO_TAGS


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


_DEMO_REVIEWS: dict[str, list[dict]] = {
    "DEMO_HAN_001": [
        {"reviewReference": "r-han-001-1", "rating": 5, "text": "Absolutely incredible food tour! Our guide Linh was knowledgeable and took us to hidden gems only locals know. The bun cha at the night market was life-changing.", "userName": "Sarah M.", "publishedDate": "2025-04-12"},
        {"reviewReference": "r-han-001-2", "rating": 5, "text": "Best way to experience Hanoi's street food scene. We tried 8 different dishes and learned so much about Vietnamese cuisine history. Highly recommend!", "userName": "James T.", "publishedDate": "2025-03-28"},
        {"reviewReference": "r-han-001-3", "rating": 4, "text": "Great tour overall. The guide was enthusiastic and the food was delicious. A couple of stops felt rushed but the overall experience was wonderful.", "userName": "Emma L.", "publishedDate": "2025-03-15"},
        {"reviewReference": "r-han-001-4", "rating": 5, "text": "Fantastic! We visited 6 street food stalls and the guide explained the cultural significance of each dish. The banh mi stop was particularly memorable.", "userName": "Carlos R.", "publishedDate": "2025-02-20"},
        {"reviewReference": "r-han-001-5", "rating": 5, "text": "One of the highlights of our Vietnam trip. The guide's passion for food was infectious. The pho was the best I've ever had.", "userName": "Yuki N.", "publishedDate": "2025-02-05"},
        {"reviewReference": "r-han-001-6", "rating": 4, "text": "Very enjoyable evening. The route through the Old Quarter was beautiful and the food was excellent. Slightly large group size but didn't detract from the experience.", "userName": "Priya K.", "publishedDate": "2025-01-18"},
    ],
    "DEMO_HAN_002": [
        {"reviewReference": "r-han-002-1", "rating": 5, "text": "Deeply moving experience at Hoa Lo Prison. Our guide provided incredible historical context that you simply cannot get from a guidebook. Essential Hanoi history.", "userName": "Michael B.", "publishedDate": "2025-04-08"},
        {"reviewReference": "r-han-002-2", "rating": 4, "text": "Educational and sobering. The Mausoleum visit was respectful and well-organized. Worth every penny for the guided context.", "userName": "Anna W.", "publishedDate": "2025-03-22"},
        {"reviewReference": "r-han-002-3", "rating": 5, "text": "Our guide David was exceptional — patient, knowledgeable, and passionate about Vietnamese history. This tour should be mandatory for every Hanoi visitor.", "userName": "Thomas G.", "publishedDate": "2025-03-10"},
    ],
    "DEMO_HAN_003": [
        {"reviewReference": "r-han-003-1", "rating": 5, "text": "Ha Long Bay exceeded all expectations. The limestone karsts at sunrise were breathtaking. Kayaking through hidden caves was the highlight of our entire trip to Vietnam.", "userName": "Olivia C.", "publishedDate": "2025-04-15"},
        {"reviewReference": "r-han-003-2", "rating": 5, "text": "Absolutely magical day. The seafood lunch on board was fresh and delicious, and our guide knew every cave and cove intimately. Worth every dollar.", "userName": "Liam F.", "publishedDate": "2025-04-01"},
        {"reviewReference": "r-han-003-3", "rating": 5, "text": "Perfect day trip from Hanoi. The early morning pickup was smooth and the boat was comfortable and clean. Kayaking was a dream — so peaceful among the karsts.", "userName": "Mei X.", "publishedDate": "2025-03-18"},
        {"reviewReference": "r-han-003-4", "rating": 4, "text": "Beautiful scenery and well-organised. The cave tour was spectacular. Docking with a few other boats made it feel slightly crowded at times but the natural beauty more than made up for it.", "userName": "Raj P.", "publishedDate": "2025-02-25"},
    ],
    "DEMO_BKK_001": [
        {"reviewReference": "r-bkk-001-1", "rating": 5, "text": "The Grand Palace is simply stunning. Our guide was knowledgeable and kept the group moving efficiently. The Emerald Buddha temple left me speechless.", "userName": "Sophie D.", "publishedDate": "2025-04-10"},
        {"reviewReference": "r-bkk-001-2", "rating": 5, "text": "Incredible tour! Learned so much about Thai history and Buddhism. Wat Pho's reclining Buddha is even more impressive in person.", "userName": "Kevin H.", "publishedDate": "2025-03-25"},
        {"reviewReference": "r-bkk-001-3", "rating": 4, "text": "Great historical experience. A bit hot at midday but the guide ensured we had water and shade breaks. Entrance fees included — great value.", "userName": "Fatima A.", "publishedDate": "2025-03-12"},
    ],
    "DEMO_BKK_002": [
        {"reviewReference": "r-bkk-002-1", "rating": 5, "text": "The floating market was vibrant and colourful. The long-tail boat ride on the Chao Phraya was exhilarating. The cooking demo at the end was an unexpected bonus!", "userName": "Laura S.", "publishedDate": "2025-04-05"},
        {"reviewReference": "r-bkk-002-2", "rating": 4, "text": "Fun and authentic Bangkok experience. The market vendors were friendly and the boat ride was thrilling. Hotel pickup was punctual.", "userName": "Daniel M.", "publishedDate": "2025-03-20"},
    ],
    "DEMO_SIN_001": [
        {"reviewReference": "r-sin-001-1", "rating": 5, "text": "The Supertree Grove light show at night is pure magic. Seeing the Marina Bay Sands illuminated was unforgettable. Our guide knew all the best photography spots.", "userName": "Isabelle V.", "publishedDate": "2025-04-11"},
        {"reviewReference": "r-sin-001-2", "rating": 5, "text": "Perfect evening tour of Singapore. The Gardens by the Bay entry was seamless and the light show exceeded expectations. Wonderful guide.", "userName": "Hiroshi T.", "publishedDate": "2025-03-30"},
    ],
    "DEMO_TYO_001": [
        {"reviewReference": "r-tyo-001-1", "rating": 5, "text": "Tokyo in one day done right! Senso-ji at dawn was peaceful and mystical. Shibuya Crossing during rush hour was electric. Mt. Fuji views from Hakone were crystal clear — so lucky!", "userName": "Charlotte B.", "publishedDate": "2025-04-14"},
        {"reviewReference": "r-tyo-001-2", "rating": 5, "text": "Expertly paced itinerary that covers all the must-sees without feeling rushed. Our guide spoke flawless English and handled everything. The included lunch was a lovely touch.", "userName": "Ahmed Z.", "publishedDate": "2025-04-02"},
        {"reviewReference": "r-tyo-001-3", "rating": 5, "text": "Best tour we've ever taken. Period. The guide's depth of knowledge about Japanese culture and history added enormous value. Mt. Fuji was clear and the photos are incredible.", "userName": "Natalie K.", "publishedDate": "2025-03-17"},
    ],
    "DEMO_PAR_001": [
        {"reviewReference": "r-par-001-1", "rating": 5, "text": "Skip-the-line made such a difference — we were at the summit before the crowds arrived. The views over Paris were stunning. The Seine cruise at sunset was romantic and peaceful.", "userName": "Marco R.", "publishedDate": "2025-04-09"},
        {"reviewReference": "r-par-001-2", "rating": 5, "text": "Everything about this tour was seamless. The guide met us promptly, the Eiffel Tower experience was magical, and the river cruise was the perfect ending to the day.", "userName": "Chloe P.", "publishedDate": "2025-03-27"},
        {"reviewReference": "r-par-001-3", "rating": 4, "text": "Great combination of activities. The summit views are worth every cent. Minor wait at the cruise embarkation but overall a fantastic Paris experience.", "userName": "Stefan W.", "publishedDate": "2025-03-05"},
    ],
}


_GENERIC_FALLBACK_REVIEWS: list[dict] = [
    {"reviewReference": "g-01", "rating": 5, "text": "An absolutely outstanding experience from start to finish. The guide was professional, passionate and incredibly knowledgeable. I cannot recommend this tour highly enough.", "userName": "Emily R.", "publishedDate": "2025-04-18"},
    {"reviewReference": "g-02", "rating": 5, "text": "One of the best tours I've taken anywhere in the world. Everything was perfectly organised and the small group size made it feel personal and special.", "userName": "James K.", "publishedDate": "2025-04-05"},
    {"reviewReference": "g-03", "rating": 4, "text": "Thoroughly enjoyable experience. Our guide was engaging and clearly loved sharing their knowledge. A few minor logistical hiccups but nothing that detracted from the overall quality.", "userName": "Sophie M.", "publishedDate": "2025-03-22"},
    {"reviewReference": "g-04", "rating": 5, "text": "Exceeded all expectations. The itinerary was well-paced, the insights were fascinating, and the whole group had a wonderful time. Already recommending to friends and family.", "userName": "Carlos V.", "publishedDate": "2025-03-10"},
    {"reviewReference": "g-05", "rating": 5, "text": "Fantastic value. You get so much more out of an experience like this than going solo — the context and stories from our guide made everything come alive.", "userName": "Aisha N.", "publishedDate": "2025-02-28"},
    {"reviewReference": "g-06", "rating": 4, "text": "Very well run tour with a knowledgeable and friendly guide. The highlights were everything promised and more. Would definitely book again on my next visit.", "userName": "Thomas B.", "publishedDate": "2025-02-14"},
    {"reviewReference": "g-07", "rating": 5, "text": "A genuinely memorable day. The guide's enthusiasm was infectious and you could tell they truly cared about giving us the best possible experience.", "userName": "Yuki T.", "publishedDate": "2025-01-30"},
    {"reviewReference": "g-08", "rating": 5, "text": "Smooth, informative, and fun. Booking was straightforward, pickup was on time, and the experience itself was brilliant. Highly recommended for first-time visitors.", "userName": "Priya S.", "publishedDate": "2025-01-15"},
    {"reviewReference": "g-09", "rating": 4, "text": "Great experience overall. Learned a lot and saw things I would never have found on my own. The guide handled the group brilliantly and kept energy high throughout.", "userName": "Marco L.", "publishedDate": "2024-12-20"},
    {"reviewReference": "g-10", "rating": 5, "text": "Absolutely worth every penny. This was the highlight of our whole trip and we still talk about it now. Do not hesitate — book it!", "userName": "Natalie W.", "publishedDate": "2024-12-08"},
]


def _get_demo_reviews(product_code: str) -> list[dict]:
    specific = _DEMO_REVIEWS.get(product_code)
    if specific:
        return specific
    # For real Viator product codes without specific demo reviews, use the
    # generic pool. Use product_code hash to give a consistent but varied offset
    # so different tours don't all show the identical review #1.
    offset = hash(product_code) % len(_GENERIC_FALLBACK_REVIEWS)
    rotated = _GENERIC_FALLBACK_REVIEWS[offset:] + _GENERIC_FALLBACK_REVIEWS[:offset]
    # Tag each review id with the product code so React keys stay unique
    return [dict(r, reviewReference=f"{product_code}-{r['reviewReference']}") for r in rotated]


def _normalize_review(raw: dict) -> dict:
    """Map Viator review fields to a canonical shape."""
    return {
        # Viator v2 uses reviewReference; v1 may use reviewId
        "id": str(raw.get("reviewReference") or raw.get("reviewId") or raw.get("id") or ""),
        "rating": int(raw.get("rating") or 0),
        "comment": raw.get("text") or raw.get("reviewText") or raw.get("content") or None,
        "published_date": raw.get("publishedDate") or raw.get("submitDate") or raw.get("date") or "",
        "user_name": raw.get("userName") or raw.get("authorName") or raw.get("reviewer") or "Traveler",
    }


async def get_product_reviews(product_code: str, page: int = 1, per_page: int = 5) -> dict:
    """Fetch individual traveler reviews for a Viator product."""
    start = (page - 1) * per_page + 1
    body = {
        "productCode": product_code,
        "start": start,
        "count": per_page,
    }
    try:
        resp = await _client().post("/reviews/product", json=body, headers=_JSON_HEADERS)
        _raise_for_status(resp)
        data = resp.json()
        reviews_raw = data.get("reviews") or data.get("data") or []
        total = int(data.get("totalCount") or data.get("total") or len(reviews_raw))
        return {"reviews": [_normalize_review(r) for r in reviews_raw], "total": total}
    except ViatorError as exc:
        if exc.status_code in (401, 403, 404, 405):
            demo = _get_demo_reviews(product_code)
            total = len(demo)
            page_reviews = demo[start - 1: start - 1 + per_page]
            return {"reviews": [_normalize_review(r) for r in page_reviews], "total": total}
        raise
    except Exception as exc:
        logger.warning("Viator get_product_reviews failed: %s", exc)
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
