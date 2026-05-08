const ACCESS_KEY = import.meta.env.VITE_UNSPLASH_ACCESS_KEY
const BASE_URL = 'https://api.unsplash.com'

const LS_PREFIX = 'unsplash_photo:'
const CACHE_TTL_MS = 90 * 60 * 1000 // 90 minutes

/**
 * Search for a single landscape photo matching a destination query.
 * Result is cached in localStorage for 90 minutes, then a fresh photo
 * is fetched. With 6 destinations this uses ~4 requests/hour on average,
 * well within Unsplash's 50 req/hour limit.
 */
export async function searchDestinationPhoto(query) {
  const cacheKey = `${LS_PREFIX}${query}`

  try {
    const stored = localStorage.getItem(cacheKey)
    if (stored) {
      const { url, cachedAt } = JSON.parse(stored)
      if (Date.now() - cachedAt < CACHE_TTL_MS) return url || null
    }
  } catch {
    // Corrupted entry — fall through to re-fetch
    localStorage.removeItem(cacheKey)
  }

  if (!ACCESS_KEY || ACCESS_KEY === 'your_unsplash_access_key_here') return null

  try {
    const params = new URLSearchParams({
      query: `${query} city landmark travel`,
      per_page: 1,
      orientation: 'landscape',
    })
    const res = await fetch(`${BASE_URL}/search/photos?${params}`, {
      headers: { Authorization: `Client-ID ${ACCESS_KEY}` },
    })
    if (!res.ok) return null
    const data = await res.json()
    const url = data.results?.[0]?.urls?.small || null

    localStorage.setItem(cacheKey, JSON.stringify({ url, cachedAt: Date.now() }))
    return url
  } catch {
    return null
  }
}
