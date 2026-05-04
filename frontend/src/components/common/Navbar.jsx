import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/hooks/useAuth'
import { useUiStore } from '@/store/uiStore'
import { authApi } from '@/api/authApi'
import { CURRENCIES } from '@/utils/constants'
import {
  Menu, X, User, LogOut, Heart, ChevronDown, Globe, Briefcase, LayoutDashboard,
} from 'lucide-react'

const LOCALES = [
  { code: 'en', label: 'English', flag: '🇺🇸' },
  { code: 'vi', label: 'Tiếng Việt', flag: '🇻🇳' },
]

export default function Navbar() {
  const { user, isAuthenticated, isStaff, logout } = useAuth()
  const navigate = useNavigate()
  const { t, i18n } = useTranslation('common')

  const currency = useUiStore((s) => s.currency)
  const locale = useUiStore((s) => s.locale)
  const setCurrency = useUiStore((s) => s.setCurrency)
  const setLocale = useUiStore((s) => s.setLocale)

  const [mobileOpen, setMobileOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [currencyOpen, setCurrencyOpen] = useState(false)
  const [localeOpen, setLocaleOpen] = useState(false)

  const handleLogout = async () => {
    await logout()
    setUserMenuOpen(false)
    navigate('/')
  }

  const handleCurrencyChange = async (code) => {
    setCurrency(code)
    setCurrencyOpen(false)
    if (isAuthenticated) {
      try { await authApi.updateMe({ preferred_currency: code }) } catch (_) {}
    }
  }

  const handleLocaleChange = async (code) => {
    setLocale(code)
    i18n.changeLanguage(code)
    setLocaleOpen(false)
    if (isAuthenticated) {
      try { await authApi.updateMe({ preferred_locale: code }) } catch (_) {}
    }
  }

  const closeAll = () => { setCurrencyOpen(false); setLocaleOpen(false); setUserMenuOpen(false) }

  return (
    <nav className="sticky top-0 z-50 bg-primary text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-heading text-xl font-bold tracking-tight">
          <Briefcase className="w-6 h-6" />
          TravelBooking
        </Link>

        <div className="hidden md:flex items-center gap-6">
          <Link to="/hotels/search" className="text-sm font-medium hover:text-accent-light transition-colors">
            {t('nav.hotels')}
          </Link>
          <Link to="/tours" className="text-sm font-medium hover:text-accent-light transition-colors">
            {t('nav.tours')}
          </Link>
          <Link to="/flights" className="text-sm font-medium hover:text-accent-light transition-colors">
            {t('nav.flights')}
          </Link>

          {/* Currency picker */}
          <div className="relative">
            <button
              onClick={() => { setCurrencyOpen(!currencyOpen); setLocaleOpen(false); setUserMenuOpen(false) }}
              aria-expanded={currencyOpen}
              aria-haspopup="menu"
              aria-label={t('nav.currency', 'Currency')}
              className="flex items-center gap-1 text-sm hover:text-accent-light"
            >
              {CURRENCIES.find(c => c.code === currency)?.symbol || '$'} {currency}
              <ChevronDown className="w-3 h-3" />
            </button>
            {currencyOpen && (
              <div className="absolute right-0 mt-2 w-44 bg-white text-gray-800 rounded-lg shadow-xl py-1 z-50">
                {CURRENCIES.map((c) => (
                  <button
                    key={c.code}
                    onClick={() => handleCurrencyChange(c.code)}
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-100 ${currency === c.code ? 'font-semibold text-primary' : ''}`}
                  >
                    {c.symbol} {c.code} — {c.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Language picker */}
          <div className="relative">
            <button
              onClick={() => { setLocaleOpen(!localeOpen); setCurrencyOpen(false); setUserMenuOpen(false) }}
              aria-expanded={localeOpen}
              aria-haspopup="menu"
              aria-label={t('nav.language', 'Language')}
              className="flex items-center gap-1 text-sm hover:text-accent-light"
            >
              <Globe className="w-4 h-4" />
              {LOCALES.find(l => l.code === locale)?.flag || '🌐'}
              <ChevronDown className="w-3 h-3" />
            </button>
            {localeOpen && (
              <div className="absolute right-0 mt-2 w-44 bg-white text-gray-800 rounded-lg shadow-xl py-1 z-50">
                {LOCALES.map((l) => (
                  <button
                    key={l.code}
                    onClick={() => handleLocaleChange(l.code)}
                    className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-100 flex items-center gap-2 ${locale === l.code ? 'font-semibold text-primary' : ''}`}
                  >
                    <span>{l.flag}</span> {l.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {isAuthenticated ? (
            <div className="relative">
              <button
                onClick={() => { setUserMenuOpen(v => !v); setCurrencyOpen(false); setLocaleOpen(false) }}
                aria-expanded={userMenuOpen}
                aria-haspopup="menu"
                aria-label={t('nav.userMenu', 'User menu')}
                className="flex items-center gap-2 bg-white/10 rounded-full px-3 py-1.5 hover:bg-white/20 transition"
              >
                <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center text-xs font-bold">
                  {user?.full_name?.[0]?.toUpperCase() || 'U'}
                </div>
                <span className="text-sm font-medium max-w-[100px] truncate">{user?.full_name}</span>
                <ChevronDown className="w-3 h-3" />
              </button>
              {userMenuOpen && (
                <div className="absolute right-0 mt-2 w-52 bg-white text-gray-800 rounded-lg shadow-xl py-1 z-50">
                  {isStaff && (
                    <Link to="/admin" onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-100">
                      <LayoutDashboard className="w-4 h-4" /> {t('nav.dashboard')}
                    </Link>
                  )}
                  <Link to="/profile" onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-100">
                    <User className="w-4 h-4" /> {t('nav.profile')}
                  </Link>
                  <Link to="/profile?tab=bookings" onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-100">
                    <Briefcase className="w-4 h-4" /> {t('nav.bookings')}
                  </Link>
                  <Link to="/profile?tab=wishlist" onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-100">
                    <Heart className="w-4 h-4" /> {t('nav.wishlist')}
                  </Link>
                  <hr className="my-1" />
                  <button onClick={handleLogout}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-100 w-full text-left text-error">
                    <LogOut className="w-4 h-4" /> {t('nav.signOut')}
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <Link to="/login" className="text-sm font-medium hover:text-accent-light transition-colors">
                {t('nav.signIn')}
              </Link>
              <Link to="/register"
                className="bg-accent hover:bg-accent-dark text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors">
                {t('nav.register')}
              </Link>
            </div>
          )}
        </div>

        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-expanded={mobileOpen}
          aria-label={mobileOpen ? t('common.close', 'Close menu') : t('nav.openMenu', 'Open menu')}
          className="md:hidden"
        >
          {mobileOpen ? <X className="w-6 h-6" aria-hidden="true" /> : <Menu className="w-6 h-6" aria-hidden="true" />}
        </button>
      </div>

      {mobileOpen && (
        <div className="md:hidden bg-primary-dark px-4 pb-4 space-y-2">
          <Link to="/hotels/search" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">{t('nav.hotels')}</Link>
          <Link to="/tours" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">{t('nav.tours')}</Link>
          <Link to="/flights" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">{t('nav.flights')}</Link>
          <div className="flex gap-3 py-2">
            {CURRENCIES.map((c) => (
              <button key={c.code} onClick={() => handleCurrencyChange(c.code)}
                className={`text-xs px-2 py-1 rounded ${currency === c.code ? 'bg-accent' : 'bg-white/10'}`}>
                {c.symbol} {c.code}
              </button>
            ))}
            {LOCALES.map((l) => (
              <button key={l.code} onClick={() => handleLocaleChange(l.code)}
                className={`text-xs px-2 py-1 rounded ${locale === l.code ? 'bg-accent' : 'bg-white/10'}`}>
                {l.flag}
              </button>
            ))}
          </div>
          {isAuthenticated ? (
            <>
              {isStaff && (
                <Link to="/admin" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">{t('nav.dashboard')}</Link>
              )}
              <Link to="/profile" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">{t('nav.profile')}</Link>
              <Link to="/my-bookings" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">{t('nav.bookings')}</Link>
              <button onClick={handleLogout} className="block py-2 text-sm text-error">{t('nav.signOut')}</button>
            </>
          ) : (
            <>
              <Link to="/login" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">{t('nav.signIn')}</Link>
              <Link to="/register" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">{t('nav.register')}</Link>
            </>
          )}
        </div>
      )}
    </nav>
  )
}
