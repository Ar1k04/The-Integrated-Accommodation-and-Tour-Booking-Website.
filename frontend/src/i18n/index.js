import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import enCommon from './locales/en/common.json'
import enHotels from './locales/en/hotels.json'
import enTours from './locales/en/tours.json'
import enBooking from './locales/en/booking.json'
import enAuth from './locales/en/auth.json'
import enProfile from './locales/en/profile.json'
import enAdmin from './locales/en/admin.json'

import viCommon from './locales/vi/common.json'
import viHotels from './locales/vi/hotels.json'
import viTours from './locales/vi/tours.json'
import viBooking from './locales/vi/booking.json'
import viAuth from './locales/vi/auth.json'
import viProfile from './locales/vi/profile.json'
import viAdmin from './locales/vi/admin.json'

const storedLocale = (() => {
  try {
    const prefs = JSON.parse(localStorage.getItem('ui-prefs') || '{}')
    return prefs?.state?.locale
  } catch (_) {
    return null
  }
})()

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    lng: storedLocale || 'en',
    fallbackLng: 'en',
    supportedLngs: ['en', 'vi'],
    ns: ['common', 'hotels', 'tours', 'booking', 'auth', 'profile', 'admin'],
    defaultNS: 'common',
    resources: {
      en: {
        common: enCommon,
        hotels: enHotels,
        tours: enTours,
        booking: enBooking,
        auth: enAuth,
        profile: enProfile,
        admin: enAdmin,
      },
      vi: {
        common: viCommon,
        hotels: viHotels,
        tours: viTours,
        booking: viBooking,
        auth: viAuth,
        profile: viProfile,
        admin: viAdmin,
      },
    },
    interpolation: { escapeValue: false },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: [],
    },
  })

export default i18n
