"""Canonical tour-type taxonomy shared by Partner tours and Viator search.

The Tours filter UI ("Tour type") sends Viator tag IDs, but Partner-created
tours store a free-text ``category`` string. To make the single "Tour type"
filter narrow BOTH sources, we keep one canonical list pairing each Viator tag
ID with the exact ``category`` label the Partner form offers. The frontend's
``TOUR_TYPES`` constant mirrors this list 1:1 — keep them in sync.

When the filter sends ``tags=[12046]`` (Walking Tours) the route maps it to the
matching Partner category string(s) and adds ``Tour.category IN (...)`` to the
DB query, so a Partner "Walking Tours" product surfaces alongside Viator's.
"""

# (viator_tag_id, partner_category_label)
TOUR_TYPES: list[tuple[int, str]] = [
    (12046, "Walking Tours"),
    (21911, "Food & Drink"),
    (11889, "Day Trips"),
    (12050, "Private Tours"),
    (12028, "Cultural Tours"),
    (12034, "Cooking Classes"),
    (11902, "Hiking Tours"),
    (12075, "City Tours"),
    (21701, "Cruises & Sailing"),
    (11922, "Multi-day Tours"),
]

# Viator tag ID → Partner category label.
TAG_ID_TO_CATEGORY: dict[int, str] = {tag_id: cat for tag_id, cat in TOUR_TYPES}

# Partner category label → Viator tag ID (case-insensitive lookups handled by
# callers that lowercase first).
CATEGORY_TO_TAG_ID: dict[str, int] = {cat: tag_id for tag_id, cat in TOUR_TYPES}


# Feature flags a Partner can truthfully guarantee on their own product. The
# Tours "Features" filter exposes the full Viator flag set, but the two
# Viator-computed flags (NEW_ON_VIATOR, LIKELY_TO_SELL_OUT) are dynamic and not
# something a Partner declares, so the Partner form only offers these four.
PARTNER_SETTABLE_FLAGS: list[str] = [
    "FREE_CANCELLATION",
    "SKIP_THE_LINE",
    "PRIVATE_TOUR",
    "SPECIAL_OFFER",
]


def tags_to_categories(tag_ids: list[int] | None) -> list[str]:
    """Map a list of Viator tag IDs to the Partner category labels they pair
    with. Tag IDs with no canonical Partner equivalent (e.g. niche tags picked
    from the "More categories" modal) are dropped — Partner tours simply can't
    match those, which is correct."""
    if not tag_ids:
        return []
    return [TAG_ID_TO_CATEGORY[t] for t in tag_ids if t in TAG_ID_TO_CATEGORY]
