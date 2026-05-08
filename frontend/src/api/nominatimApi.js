const BASE_URL = 'https://nominatim.openstreetmap.org'

/**
 * Search for cities/places via Nominatim (OpenStreetMap geocoding).
 * Returns [{city, country, state, countryCode}] deduplicated by city+country.
 */
export async function searchCities(query) {
  if (!query || query.length < 2) return []
  const params = new URLSearchParams({
    q: query,
    format: 'json',
    limit: 8,
    addressdetails: 1,
    'accept-language': 'en',
    featuretype: 'settlement',
  })
  try {
    const res = await fetch(`${BASE_URL}/search?${params}`, {
      headers: { 'User-Agent': 'TravelBookingApp/1.0 (graduation-project)' },
    })
    if (!res.ok) return []
    const data = await res.json()

    const seen = new Set()
    const results = []
    for (const item of data) {
      const addr = item.address || {}
      const city =
        addr.city ||
        addr.town ||
        addr.village ||
        addr.municipality ||
        addr.county ||
        item.display_name.split(',')[0].trim()
      const country = addr.country || ''
      const state = addr.state || addr.region || ''
      const countryCode = (addr.country_code || '').toUpperCase()
      const key = `${city.toLowerCase()}|${country.toLowerCase()}`
      if (city && !seen.has(key)) {
        seen.add(key)
        results.push({ city, country, state, countryCode })
      }
    }
    return results
  } catch {
    return []
  }
}
