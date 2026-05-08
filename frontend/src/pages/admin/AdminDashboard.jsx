import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { adminApi } from '@/api/adminApi'
import { useAuth } from '@/hooks/useAuth'
import Skeleton from '@/components/common/Skeleton'
import { formatCurrency } from '@/utils/formatters'
import {
  DollarSign, CalendarCheck, Users, TrendingUp,
  Hotel, MapPin, Briefcase, UserCheck,
} from 'lucide-react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts'

const PIE_COLORS = ['#F59E0B', '#003580', '#EF4444', '#10B981']

export default function AdminDashboard() {
  const { isPartner } = useAuth()
  const { t } = useTranslation('admin')
  const [period, setPeriod] = useState('month')

  const PERIOD_OPTIONS = [
    { label: t('dashboard.thisWeek'), value: 'week' },
    { label: t('dashboard.thisMonth'), value: 'month' },
    { label: t('dashboard.thisYear'), value: 'year' },
  ]

  const { data: stats, isLoading } = useQuery({
    queryKey: ['admin-stats', period],
    queryFn: () => adminApi.getStats({ period }),
    select: (res) => res.data,
  })

  const statCards = [
    { label: t('dashboard.totalRevenue'), value: formatCurrency(stats?.total_revenue || 0), icon: DollarSign, color: 'bg-green-100 text-green-700' },
    { label: t('dashboard.bookings'), value: stats?.bookings_count || 0, icon: CalendarCheck, color: 'bg-blue-100 text-blue-700' },
    { label: t('dashboard.occupancyRate'), value: `${(stats?.occupancy_rate || 0).toFixed(1)}%`, icon: TrendingUp, color: 'bg-purple-100 text-purple-700' },
    { label: t('dashboard.newUsers'), value: stats?.new_users || 0, icon: Users, color: 'bg-amber-100 text-amber-700' },
  ]

  const bookingsByStatus = stats?.bookings_by_status
    ? Object.entries(stats.bookings_by_status).map(([name, value]) => ({ name, value }))
    : []

  const revenueChart = stats?.revenue_chart_data || []

  const quickLinks = [
    { label: t('dashboard.manageHotels'), to: '/admin/hotels', icon: Hotel },
    { label: t('dashboard.manageRooms'), to: '/admin/rooms', icon: MapPin },
    { label: t('dashboard.manageTours'), to: '/admin/tours', icon: Briefcase },
    { label: t('dashboard.manageBookings'), to: '/admin/bookings', icon: CalendarCheck },
    !isPartner && { label: t('dashboard.manageUsers'), to: '/admin/users', icon: UserCheck },
  ].filter(Boolean)

  return (
    <>
      <Helmet><title>{isPartner ? t('dashboard.partnerTitle') : t('dashboard.adminTitle')} — TravelBooking</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-8">
            <h1 className="font-heading text-2xl font-bold text-gray-900">{isPartner ? t('dashboard.partnerTitle') : t('dashboard.adminTitle')}</h1>
            <div className="flex gap-2" role="group" aria-label={t('dashboard.title')}>
              {PERIOD_OPTIONS.map((p) => (
                <button key={p.value} onClick={() => setPeriod(p.value)}
                  aria-pressed={period === p.value}
                  className={`px-4 py-2 rounded-lg text-sm font-medium ${
                    period === p.value ? 'bg-primary text-white' : 'bg-white border text-gray-600 hover:bg-gray-50'
                  }`}>
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
            {isLoading ? (
              Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)
            ) : (
              statCards.map((s, i) => {
                const Icon = s.icon
                return (
                  <div key={i} className="bg-white rounded-xl border p-5 flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-xl ${s.color} flex items-center justify-center`}>
                      <Icon className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="text-sm text-gray-500">{s.label}</p>
                      <p className="text-2xl font-bold text-gray-900">{s.value}</p>
                    </div>
                  </div>
                )
              })
            )}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
            <div className="lg:col-span-2 bg-white rounded-xl border p-5">
              <h2 className="font-heading font-bold text-lg mb-4">{t('dashboard.revenueOverview')}</h2>
              {revenueChart.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={revenueChart}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip formatter={(v) => formatCurrency(v)} />
                    <Line type="monotone" dataKey="revenue" stroke="#003580" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[300px] flex items-center justify-center text-gray-400 text-sm">{t('dashboard.noRevenueData')}</div>
              )}
            </div>

            <div className="bg-white rounded-xl border p-5">
              <h2 className="font-heading font-bold text-lg mb-4">{t('dashboard.bookingsByStatus')}</h2>
              {bookingsByStatus.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={bookingsByStatus} dataKey="value" nameKey="name" cx="50%" cy="50%"
                      outerRadius={90} innerRadius={50} paddingAngle={3} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    >
                      {bookingsByStatus.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[300px] flex items-center justify-center text-gray-400 text-sm">{t('dashboard.noBookingData')}</div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
            {quickLinks.map((link) => {
              const Icon = link.icon
              return (
                <Link key={link.to} to={link.to}
                  className="bg-white rounded-xl border p-5 text-center hover:shadow-md transition-shadow group">
                  <Icon className="w-8 h-8 mx-auto text-primary mb-2 group-hover:scale-110 transition-transform" aria-hidden="true" />
                  <p className="text-sm font-medium text-gray-700">{link.label}</p>
                </Link>
              )
            })}
          </div>

        </div>
      </div>
    </>
  )
}
