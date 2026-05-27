// Legacy import path. Real implementation lives in `locationsApi.js` — backed
// by our Postgres-synced cities table (with backend-side Nominatim fallback).
// Kept as a thin re-export so existing imports keep working without a sweep.
export { searchCities } from './locationsApi'
