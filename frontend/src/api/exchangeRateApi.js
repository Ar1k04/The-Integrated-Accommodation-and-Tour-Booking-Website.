const API_KEY = import.meta.env.VITE_EXCHANGE_RATE_API_KEY
const FALLBACK_RATE = 25_000

/**
 * Fetch live USD → VND rate from open.er-api.com.
 * Falls back to 25,000 on any error.
 */
export async function fetchUsdToVnd() {
  try {
    const res = await fetch(
      `https://open.er-api.com/v6/latest/USD?apikey=${API_KEY}`
    )
    if (!res.ok) return FALLBACK_RATE
    const data = await res.json()
    const rate = data?.rates?.VND
    return rate && rate > 0 ? Math.round(rate) : FALLBACK_RATE
  } catch {
    return FALLBACK_RATE
  }
}
