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

export const BOOKING_STATUSES = ['pending', 'confirmed', 'cancelled', 'completed']

export const CURRENCIES = [
  { code: 'USD', symbol: '$', name: 'US Dollar' },
  { code: 'VND', symbol: '₫', name: 'Vietnamese Dong' },
]

export const DEFAULT_CURRENCY = 'USD'

export const ITEMS_PER_PAGE = 20
