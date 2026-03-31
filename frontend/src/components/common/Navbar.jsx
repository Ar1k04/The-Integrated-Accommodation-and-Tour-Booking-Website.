import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { CURRENCIES } from '@/utils/constants'
import {
  Menu, X, User, LogOut, Heart, ChevronDown, Globe, Briefcase,
} from 'lucide-react'

export default function Navbar() {
  const { user, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const [currencyOpen, setCurrencyOpen] = useState(false)
  const [currency, setCurrency] = useState('USD')

  const handleLogout = async () => {
    await logout()
    setUserMenuOpen(false)
    navigate('/')
  }

  return (
    <nav className="sticky top-0 z-50 bg-primary text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-heading text-xl font-bold tracking-tight">
          <Briefcase className="w-6 h-6" />
          TravelBooking
        </Link>

        <div className="hidden md:flex items-center gap-6">
          <Link to="/hotels/search" className="text-sm font-medium hover:text-accent-light transition-colors">
            Hotels
          </Link>
          <Link to="/tours" className="text-sm font-medium hover:text-accent-light transition-colors">
            Tours
          </Link>

          <div className="relative">
            <button
              onClick={() => { setCurrencyOpen(!currencyOpen); setUserMenuOpen(false) }}
              className="flex items-center gap-1 text-sm hover:text-accent-light"
            >
              <Globe className="w-4 h-4" />
              {currency}
              <ChevronDown className="w-3 h-3" />
            </button>
            {currencyOpen && (
              <div className="absolute right-0 mt-2 w-40 bg-white text-gray-800 rounded-lg shadow-xl py-1 z-50">
                {CURRENCIES.map((c) => (
                  <button
                    key={c.code}
                    onClick={() => { setCurrency(c.code); setCurrencyOpen(false) }}
                    className="w-full text-left px-4 py-2 text-sm hover:bg-gray-100"
                  >
                    {c.symbol} {c.code} — {c.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          {isAuthenticated ? (
            <div className="relative">
              <button
                onClick={() => { setUserMenuOpen(!userMenuOpen); setCurrencyOpen(false) }}
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
                  <Link to="/profile" onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-100">
                    <User className="w-4 h-4" /> My Profile
                  </Link>
                  <Link to="/profile?tab=bookings" onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-100">
                    <Briefcase className="w-4 h-4" /> My Bookings
                  </Link>
                  <Link to="/profile?tab=wishlist" onClick={() => setUserMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-100">
                    <Heart className="w-4 h-4" /> Wishlist
                  </Link>
                  <hr className="my-1" />
                  <button onClick={handleLogout}
                    className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-gray-100 w-full text-left text-error">
                    <LogOut className="w-4 h-4" /> Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <Link to="/login" className="text-sm font-medium hover:text-accent-light transition-colors">
                Sign In
              </Link>
              <Link to="/register"
                className="bg-accent hover:bg-accent-dark text-white text-sm font-semibold px-4 py-2 rounded-lg transition-colors">
                Register
              </Link>
            </div>
          )}
        </div>

        <button onClick={() => setMobileOpen(!mobileOpen)} className="md:hidden">
          {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {mobileOpen && (
        <div className="md:hidden bg-primary-dark px-4 pb-4 space-y-2">
          <Link to="/hotels/search" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">Hotels</Link>
          <Link to="/tours" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">Tours</Link>
          {isAuthenticated ? (
            <>
              <Link to="/profile" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">Profile</Link>
              <Link to="/my-bookings" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">My Bookings</Link>
              <button onClick={handleLogout} className="block py-2 text-sm text-error">Sign Out</button>
            </>
          ) : (
            <>
              <Link to="/login" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">Sign In</Link>
              <Link to="/register" onClick={() => setMobileOpen(false)} className="block py-2 text-sm">Register</Link>
            </>
          )}
        </div>
      )}
    </nav>
  )
}
