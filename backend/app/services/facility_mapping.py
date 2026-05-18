# Maps our local amenity slugs (Hotel.amenities JSONB values + frontend AMENITIES constant)
# to LiteAPI canonical facility_ids from GET /data/facilities.
# IDs verified against the live endpoint on 2026-05-06.
SLUG_TO_LITEAPI_ID: dict[str, int] = {
    "wifi": 107,            # Free WiFi
    "pool": 301,            # Swimming pool
    "gym": 11,              # Fitness centre
    "spa": 54,              # Spa and wellness centre
    "parking": 2,           # Parking
    "restaurant": 3,        # Restaurant
    "bar": 7,               # Bar
    "room_service": 5,      # Room service
    "air_conditioning": 109,
    "laundry": 22,          # Laundry
    "airport_shuttle": 17,  # Airport shuttle
    "pet_friendly": 4,      # Pets allowed
    "business_center": 20,  # Business centre
}

# Maps our local hotel-type slugs to LiteAPI hotel-type IDs from GET /data/hotelTypes.
# Niche types (209–277: ryokan, riad, capsule, treehouse, etc.) are intentionally
# omitted — see frontend/src/utils/constants.js HOTEL_TYPES for the matching list.
HOTEL_TYPE_SLUG_TO_ID: dict[str, int] = {
    "apartments": 201,
    "hostels": 203,
    "hotels": 204,
    "motels": 205,
    "resorts": 206,
    "residences": 207,
    "bed_and_breakfasts": 208,
    "palace": 278,
}
