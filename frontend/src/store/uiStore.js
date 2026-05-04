import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useUiStore = create(persist(
  (set) => ({
    currency: 'USD',
    locale: 'en',
    setCurrency: (currency) => set({ currency }),
    setLocale: (locale) => set({ locale }),
  }),
  { name: 'ui-prefs' }
))
