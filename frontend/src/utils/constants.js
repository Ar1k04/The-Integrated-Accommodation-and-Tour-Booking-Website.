export const ROOM_TYPES = ['single', 'double', 'suite', 'family', 'villa']

export const TOUR_CATEGORIES = ['adventure', 'cultural', 'beach', 'city', 'nature', 'food']

export const AMENITIES = [
  'wifi', 'pool', 'gym', 'spa', 'parking', 'restaurant',
  'bar', 'room_service', 'air_conditioning', 'laundry',
  'airport_shuttle', 'pet_friendly', 'business_center',
]

// Maps LiteAPI facility_id → local amenity slug.
// Inverse of backend/app/services/facility_mapping.py SLUG_TO_LITEAPI_ID.
// IDs verified against GET /data/facilities on 2026-05-06.
export const LITEAPI_ID_TO_SLUG = {
  107: 'wifi',
  301: 'pool',
  11:  'gym',
  54:  'spa',
  2:   'parking',
  3:   'restaurant',
  7:   'bar',
  5:   'room_service',
  109: 'air_conditioning',
  22:  'laundry',
  17:  'airport_shuttle',
  4:   'pet_friendly',
  20:  'business_center',
}

// LiteAPI hotel-type catalogue (GET /data/hotelTypes).
// Trimmed to the most universally-recognised property categories — the niche
// types (IDs 209–277: ryokan, riad, capsule, treehouse, etc.) are excluded so
// the filter stays usable. Slugs are sent to the backend; LiteAPI IDs are
// forwarded as `hotelTypeIds` for the supplier search.
export const HOTEL_TYPES = [
  { id: 201, slug: 'apartments' },
  { id: 203, slug: 'hostels' },
  { id: 204, slug: 'hotels' },
  { id: 205, slug: 'motels' },
  { id: 206, slug: 'resorts' },
  { id: 207, slug: 'residences' },
  { id: 208, slug: 'bed_and_breakfasts' },
  { id: 278, slug: 'palace' },
]

export const HOTEL_TYPE_SLUG_TO_ID = Object.fromEntries(
  HOTEL_TYPES.map((t) => [t.slug, t.id]),
)

export const BOOKING_STATUSES = ['pending', 'confirmed', 'cancelled', 'completed']

export const CURRENCIES = [
  { code: 'USD', symbol: '$', name: 'US Dollar' },
  { code: 'VND', symbol: '₫', name: 'Vietnamese Dong' },
]

export const DEFAULT_CURRENCY = 'USD'

export const ITEMS_PER_PAGE = 20

// Viator tag IDs surfaced as quick-pick chips in the Tours filter sidebar.
// Each entry is a top-level Viator tag (parent_tag_id = null) chosen for broad appeal.
// `label` is a fallback shown until the live tag tree (/tours/viator/tags) loads.
export const POPULAR_VIATOR_TAGS = [
  { id: 12046, label: 'Walking Tours' },
  { id: 21911, label: 'Food & Drink' },
  { id: 11889, label: 'Day Trips' },
  { id: 12050, label: 'Private Tours' },
  { id: 12028, label: 'Cultural Tours' },
  { id: 12034, label: 'Cooking Classes' },
  { id: 11902, label: 'Hiking Tours' },
  { id: 12075, label: 'City Tours' },
  { id: 21701, label: 'Cruises & Sailing' },
  { id: 11922, label: 'Multi-day Tours' },
]

// Whitelist of Viator product search flags (must match backend VIATOR_FLAGS).
export const VIATOR_FLAGS = [
  'FREE_CANCELLATION',
  'SKIP_THE_LINE',
  'PRIVATE_TOUR',
  'SPECIAL_OFFER',
  'LIKELY_TO_SELL_OUT',
  'NEW_ON_VIATOR',
]

// Preset duration ranges in minutes, mapped to Viator durationInMinutes filter.
export const VIATOR_DURATION_PRESETS = [
  { id: 'less1h',   min: null, max: 60 },
  { id: '1to4h',    min: 60,   max: 240 },
  { id: '4to8h',    min: 240,  max: 480 },
  { id: 'fullDay',  min: 480,  max: 1440 },
  { id: 'multiDay', min: 1440, max: null },
]

export const VIATOR_RATING_PRESETS = [3, 4, 4.5]
