import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { adminApi } from '@/api/adminApi'
import { useAuth } from '@/hooks/useAuth'
import { toast } from 'sonner'
import Skeleton from '@/components/common/Skeleton'
import BookingStatusBadge from '@/components/common/BookingStatusBadge'
import { formatCurrency, formatDate } from '@/utils/formatters'
import { Link } from 'react-router-dom'
import { BOOKING_STATUSES } from '@/utils/constants'
import { Search, ChevronLeft, ChevronRight, Info } from 'lucide-react'

export default function ManageBookings() {
  const qc = useQueryClient()
  const { isPartner } = useAuth()
  const { t } = useTranslation('admin')
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [search, setSearch] = useState('')
  const { data, isLoading } = useQuery({
    queryKey: ['admin-bookings', page, statusFilter, search],
    queryFn: () => adminApi.listBookings({ page, per_page: 10, status: statusFilter || undefined, q: search || undefined }),
    select: (res) => res.data,
  })

  const updateMut = useMutation({
    mutationFn: ({ id, status }) => adminApi.updateBooking(id, status),
    onSuccess: () => { toast.success('Status updated'); qc.invalidateQueries({ queryKey: ['admin-bookings'] }) },
    onError: () => toast.error('Failed to update'),
  })

  const bookings = data?.items || []
  const meta = data?.meta || {}

  return (
    <>
      <Helmet><title>{t('dashboard.manageBookings')} — Admin</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="mb-6">
            <Link to="/admin" className="text-sm text-primary hover:underline">{t('actions.backToDashboard')}</Link>
            <h1 className="font-heading text-2xl font-bold text-gray-900">{t('dashboard.manageBookings')}</h1>
          </div>

          {isPartner && (
            <div role="note" className="flex items-start gap-2 mb-4 bg-blue-50 border border-blue-200 text-blue-800 text-sm rounded-lg px-4 py-3">
              <Info className="w-4 h-4 mt-0.5 shrink-0" aria-hidden="true" />
              <span>{t('booking.partnerBanner')}</span>
            </div>
          )}

          <div className="bg-white rounded-xl border p-5">
            <div className="flex flex-col md:flex-row gap-3 mb-4">
              <div className="relative flex-1 max-w-sm">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" aria-hidden="true" />
                <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }}
                  placeholder={t('filter.searchById')} aria-label={t('filter.searchById')}
                  className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm" />
              </div>
              <div className="flex gap-2" role="group" aria-label={t('filter.all')}>
                <button onClick={() => { setStatusFilter(''); setPage(1) }}
                  aria-pressed={!statusFilter}
                  className={`px-3 py-2 rounded-lg text-xs font-medium border ${!statusFilter ? 'bg-primary text-white border-primary' : ''}`}>
                  {t('filter.all')}
                </button>
                {BOOKING_STATUSES.map((s) => (
                  <button key={s} onClick={() => { setStatusFilter(s); setPage(1) }}
                    className={`px-3 py-2 rounded-lg text-xs font-medium border capitalize ${statusFilter === s ? 'bg-primary text-white border-primary' : ''}`}>
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {isLoading ? (
              <div className="space-y-3">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-3 font-medium">{t('table.id')}</th>
                      <th className="pb-3 font-medium">{t('table.user')}</th>
                      <th className="pb-3 font-medium">{t('table.item')}</th>
                      <th className="pb-3 font-medium">{t('table.dates')}</th>
                      <th className="pb-3 font-medium">{t('table.status')}</th>
                      <th className="pb-3 font-medium">{t('table.amount')}</th>
                      <th className="pb-3 font-medium text-right">{t('table.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {bookings.map((b) => (
                      <tr key={b.id} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="py-3 font-mono text-xs">{b.id?.slice(0, 8)}</td>
                        <td className="py-3">
                          <div className="font-medium">{b.user?.full_name || b.user_id?.slice(0, 8)}</div>
                          {b.user?.email && <div className="text-xs text-gray-500">{b.user.email}</div>}
                          {b.user?.phone && <div className="text-xs text-gray-500">{b.user.phone}</div>}
                          {typeof b.user?.loyalty_points === 'number' && (
                            <div className="text-xs text-gray-400">{t('booking.loyalty')}: {b.user.loyalty_points}</div>
                          )}
                        </td>
                        <td className="py-3">
                          {(() => {
                            const firstItem = b.items?.[0]
                            if (!firstItem) return <span className="text-gray-400">—</span>
                            if (firstItem.item_type === 'room') {
                              const hotelName = firstItem?.room?.hotel?.name
                              const roomName = firstItem?.room?.name
                              const isApi = !!firstItem.liteapi_booking_id
                              return (
                                <>
                                  <div className="font-medium">{hotelName || '—'}</div>
                                  <div className="text-xs text-gray-500">{roomName || '—'}</div>
                                  {isApi && <div className="text-xs text-orange-500">{t('booking.viaLiteapi')}</div>}
                                  {b.items?.length > 1 && <div className="text-xs text-gray-400">+{b.items.length - 1} more</div>}
                                </>
                              )
                            }
                            if (firstItem.item_type === 'tour') {
                              const isApi = !!firstItem.viator_product_code
                              return (
                                <>
                                  <div className="font-medium">{firstItem.tour_name || 'Tour'}</div>
                                  <div className="text-xs text-gray-500">
                                    Tour · {firstItem.quantity} pax
                                    {isApi && <span className="ml-1 text-orange-500">· {t('booking.viaViator')}</span>}
                                  </div>
                                </>
                              )
                            }
                            if (firstItem.item_type === 'flight') {
                              return <div className="font-medium text-xs">{t('booking.flight')} <span className="text-orange-500">· {t('booking.viaDuffel')}</span></div>
                            }
                            return <span className="text-gray-400">{firstItem.item_type}</span>
                          })()}
                        </td>
                        <td className="py-3">
                          {(() => {
                            const firstItem = b.items?.[0]
                            if (!firstItem?.check_in) return '—'
                            if (firstItem.item_type === 'room') {
                              return <>{formatDate(firstItem.check_in)} — {formatDate(firstItem.check_out)}</>
                            }
                            return formatDate(firstItem.check_in)
                          })()}
                        </td>
                        <td className="py-3"><BookingStatusBadge status={b.status} /></td>
                        <td className="py-3 font-semibold">{formatCurrency(b.total_price)}</td>
                        <td className="py-3 text-right">
                          <select
                            value={b.status}
                            onChange={(e) => updateMut.mutate({ id: b.id, status: e.target.value })}
                            className="border rounded-lg px-2 py-1 text-xs"
                          >
                            {BOOKING_STATUSES.map((s) => <option key={s} value={s} className="capitalize">{s}</option>)}
                          </select>
                        </td>
                      </tr>
                    ))}
                    {bookings.length === 0 && (
                      <tr><td colSpan={7} className="py-12 text-center text-gray-400">{t('empty.noBookings')}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}

            {meta.total_pages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <p className="text-sm text-gray-500">Page {meta.page} of {meta.total_pages}</p>
                <div className="flex gap-2">
                  <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}
                    className="p-2 border rounded-lg disabled:opacity-30"><ChevronLeft className="w-4 h-4" /></button>
                  <button onClick={() => setPage(Math.min(meta.total_pages, page + 1))} disabled={page >= meta.total_pages}
                    className="p-2 border rounded-lg disabled:opacity-30"><ChevronRight className="w-4 h-4" /></button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
