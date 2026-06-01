import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { useTranslation } from 'react-i18next'
import ErrorBoundary from './ErrorBoundary'
import PageTransition from './PageTransition'
import { Toaster } from 'sonner'
import {
  LayoutDashboard, Hotel, MapPin, Briefcase,
  CalendarCheck, UserCheck, LogOut, ChevronRight, Crown, Tag, Award,
} from 'lucide-react'

export default function AdminLayout() {
  const { user, logout, isAdmin, isPartner } = useAuth()
  const { t } = useTranslation('admin')
  const location = useLocation()
  const navigate = useNavigate()

  const BASE_LINKS = [
    { label: t('sidebar.dashboard'), to: '/admin', icon: LayoutDashboard },
    { label: t('sidebar.hotels'), to: '/admin/hotels', icon: Hotel },
    { label: t('sidebar.rooms'), to: '/admin/rooms', icon: MapPin },
    { label: t('sidebar.tours'), to: '/admin/tours', icon: Briefcase },
    { label: t('sidebar.bookings'), to: '/admin/bookings', icon: CalendarCheck },
    { label: t('sidebar.vouchers'), to: '/admin/vouchers', icon: Tag },
  ]

  const SUPERADMIN_LINKS = [
    { label: t('sidebar.users'), to: '/admin/users', icon: UserCheck },
    { label: t('sidebar.partners'), to: '/admin/partners', icon: UserCheck },
    { label: t('sidebar.tiers'), to: '/admin/loyalty-tiers', icon: Award },
  ]

  const sidebarLinks = isAdmin
    ? [...BASE_LINKS, ...SUPERADMIN_LINKS]
    : BASE_LINKS

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  // Partner approval gate: a pending/rejected partner can log in but cannot use
  // the dashboard until an admin approves (backend enforces this too).
  if (isPartner && user?.partner_status && user.partner_status !== 'approved') {
    const rejected = user.partner_status === 'rejected'
    return (
      <div className="min-h-screen bg-surface flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl border shadow-sm max-w-md w-full p-8 text-center">
          <div className={`w-16 h-16 mx-auto rounded-full flex items-center justify-center mb-4 ${rejected ? 'bg-red-100' : 'bg-amber-100'}`}>
            <UserCheck className={`w-8 h-8 ${rejected ? 'text-error' : 'text-amber-600'}`} aria-hidden="true" />
          </div>
          <h1 className="font-heading text-xl font-bold text-gray-900 mb-2">
            {rejected ? t('partners.notice.rejectedTitle') : t('partners.notice.pendingTitle')}
          </h1>
          <p className="text-gray-500 text-sm mb-6">
            {rejected ? t('partners.notice.rejectedBody') : t('partners.notice.pendingBody')}
          </p>
          <button onClick={handleLogout}
            className="inline-flex items-center gap-2 bg-primary hover:bg-primary-dark text-white px-4 py-2.5 rounded-lg text-sm font-semibold">
            <LogOut className="w-4 h-4" /> {t('sidebar.signOut')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen bg-surface">
      <aside className="hidden md:flex w-64 flex-col bg-primary text-white" aria-label="Admin sidebar">
        <div className="px-6 py-5 border-b border-white/10">
          <Link to="/admin" className="flex items-center gap-2 font-heading text-xl font-bold tracking-tight">
            <Briefcase className="w-6 h-6" aria-hidden="true" />
            TravelBooking
          </Link>
          <p className="text-xs text-white/60 mt-1">{isPartner ? t('sidebar.partnerSubtitle') : t('sidebar.adminSubtitle')}</p>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1" aria-label="Admin navigation">
          {sidebarLinks.map((link) => {
            const Icon = link.icon
            const isActive = location.pathname === link.to
            return (
              <Link
                key={link.to}
                to={link.to}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-white/15 text-white'
                    : 'text-white/70 hover:bg-white/10 hover:text-white'
                }`}
              >
                <Icon className="w-5 h-5" aria-hidden="true" />
                {link.label}
                {isActive && <ChevronRight className="w-4 h-4 ml-auto" aria-hidden="true" />}
              </Link>
            )
          })}
        </nav>

        <div className="px-3 py-4 border-t border-white/10">
          <div className="flex items-center gap-3 px-3 py-2 mb-2" aria-label={`Logged in as ${user?.full_name}`}>
            <div className="relative w-8 h-8 shrink-0">
              <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-xs font-bold" aria-hidden="true">
                {user?.full_name?.[0]?.toUpperCase() || 'A'}
              </div>
              {isAdmin && (
                <Crown className="absolute -top-2 -right-1 w-3.5 h-3.5 text-yellow-300" aria-hidden="true" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{user?.full_name}</p>
              <p className="text-xs text-white/50 truncate">{user?.email}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            aria-label={t('sidebar.signOut')}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-white/70 hover:bg-white/10 hover:text-white transition-colors w-full"
          >
            <LogOut className="w-5 h-5" aria-hidden="true" />
            {t('sidebar.signOut')}
          </button>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="md:hidden sticky top-0 z-50 bg-primary text-white px-4 h-14 flex items-center justify-between shadow-lg">
          <Link to="/admin" className="flex items-center gap-2 font-heading text-lg font-bold">
            <Briefcase className="w-5 h-5" aria-hidden="true" />
            {t('sidebar.adminLabel')}
          </Link>
          <button
            onClick={handleLogout}
            aria-label={t('sidebar.signOut')}
            className="text-white/80 hover:text-white"
          >
            <LogOut className="w-5 h-5" aria-hidden="true" />
          </button>
        </header>

        <div className="md:hidden flex overflow-x-auto bg-white border-b px-2 py-2 gap-1" role="navigation" aria-label="Admin mobile navigation">
          {sidebarLinks.map((link) => {
            const Icon = link.icon
            const isActive = location.pathname === link.to
            return (
              <Link
                key={link.to}
                to={link.to}
                aria-current={isActive ? 'page' : undefined}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium whitespace-nowrap transition-colors ${
                  isActive
                    ? 'bg-primary text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                <Icon className="w-4 h-4" aria-hidden="true" />
                {link.label}
              </Link>
            )
          })}
        </div>

        <main className="flex-1">
          <ErrorBoundary>
            <PageTransition>
              <Outlet />
            </PageTransition>
          </ErrorBoundary>
        </main>
      </div>

      <Toaster position="top-right" richColors closeButton />
    </div>
  )
}
