import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { fetchUsdToVnd } from '@/api/exchangeRateApi'
import { setUsdToVnd, setDisplayCurrency } from '@/utils/rateStore'

const RATE_TTL_MS = 24 * 60 * 60 * 1000 // refresh every 24 hours

export const useUiStore = create(persist(
  (set, get) => ({
    currency: 'USD',
    locale: 'en',
    usdToVnd: 25_000,
    rateLastFetchedAt: null,

    setCurrency: (currency) => { setDisplayCurrency(currency); set({ currency }) },
    setLocale: (locale) => set({ locale }),

    // Called once on app startup (main.jsx). Refreshes the rate if stale.
    initExchangeRate: async () => {
      const { usdToVnd, rateLastFetchedAt } = get()

      // Seed singletons immediately with persisted values
      setUsdToVnd(usdToVnd)
      setDisplayCurrency(get().currency)

      const isStale =
        !rateLastFetchedAt ||
        Date.now() - rateLastFetchedAt > RATE_TTL_MS ||
        usdToVnd === 25_000  // fallback value means a previous fetch failed — always retry

      if (!isStale) return

      const rate = await fetchUsdToVnd()
      setUsdToVnd(rate)
      set({ usdToVnd: rate, rateLastFetchedAt: Date.now() })
    },
  }),
  { name: 'ui-prefs' }
))
