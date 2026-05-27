import api from './axiosInstance'

/**
 * City autocomplete backed by our LiteAPI-synced Postgres table (with Nominatim
 * fallback handled server-side). Drop-in replacement for the legacy
 * `searchCities` from `nominatimApi.js` — same response shape, dramatically faster.
 *
 * @param {string} query
 * @param {{ limit?: number, countryCode?: string }} [opts]
 * @returns {Promise<Array<{city:string, country:string, state:string, countryCode:string, latitude?:number, longitude?:number}>>}
 */
export async function searchCities(query, opts = {}) {
  if (!query || query.length < 2) return []
  const params = { q: query, limit: opts.limit ?? 8 }
  if (opts.countryCode) params.country_code = opts.countryCode
  try {
    const res = await api.get('/locations/autocomplete', { params })
    return Array.isArray(res?.data) ? res.data : []
  } catch {
    return []
  }
}
