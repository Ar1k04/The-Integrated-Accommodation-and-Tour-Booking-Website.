import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X, Mail, Calendar, Receipt, Search } from 'lucide-react'
import { vouchersApi } from '@/api/vouchersApi'
import { formatCurrency, formatDate } from '@/utils/formatters'

/**
 * Drawer/modal that shows usage history for a single voucher.
 * Filters by date range and user email; paginates server-side.
 */
export default function VoucherUsageDrawer({ voucher, onClose }) {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ date_from: '', date_to: '', user_email: '' })
  const [draft, setDraft] = useState(filters)

  useEffect(() => {
    setPage(1)
    setFilters({ date_from: '', date_to: '', user_email: '' })
    setDraft({ date_from: '', date_to: '', user_email: '' })
  }, [voucher?.id])

  const { data, isLoading } = useQuery({
    enabled: !!voucher?.id,
    queryKey: ['voucher-usages', voucher?.id, page, filters],
    queryFn: () =>
      vouchersApi.listUsages(voucher.id, {
        page,
        per_page: 20,
        ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
      }),
    select: (res) => res.data,
  })

  const items = data?.items || []
  const meta = data?.meta || {}

  if (!voucher) return null

  const applyFilters = (e) => {
    e.preventDefault()
    setPage(1)
    setFilters(draft)
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 flex justify-end"
      onClick={onClose}
      onKeyDown={(e) => e.key === 'Escape' && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="voucher-usage-drawer-title"
        className="bg-white w-full max-w-2xl h-full overflow-y-auto shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between z-10">
          <div>
            <h2 id="voucher-usage-drawer-title" className="font-heading font-bold text-lg">
              {voucher.code} — Usage
            </h2>
            <p className="text-xs text-gray-500">{voucher.name}</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-gray-100"
            aria-label="Close"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        <div className="px-6 py-4 border-b bg-gray-50">
          <div className="grid grid-cols-4 gap-3 mb-3 text-center">
            <div>
              <p className="text-xs text-gray-500">Total uses</p>
              <p className="font-bold text-lg">{meta.total ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Total discount</p>
              <p className="font-bold text-lg">
                {meta.total_discount_amount != null
                  ? formatCurrency(meta.total_discount_amount)
                  : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Limit</p>
              <p className="font-bold text-lg">{voucher.max_uses}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Budget left</p>
              <p className="font-bold text-lg">
                {voucher.budget != null
                  ? formatCurrency(voucher.budget_remaining ?? 0)
                  : '∞'}
              </p>
            </div>
          </div>

          <form onSubmit={applyFilters} className="grid grid-cols-4 gap-2">
            <input
              type="date"
              value={draft.date_from}
              onChange={(e) => setDraft({ ...draft, date_from: e.target.value })}
              className="border rounded px-2 py-1.5 text-xs"
              placeholder="From"
              aria-label="Date from"
            />
            <input
              type="date"
              value={draft.date_to}
              onChange={(e) => setDraft({ ...draft, date_to: e.target.value })}
              className="border rounded px-2 py-1.5 text-xs"
              placeholder="To"
              aria-label="Date to"
            />
            <input
              type="email"
              value={draft.user_email}
              onChange={(e) => setDraft({ ...draft, user_email: e.target.value })}
              placeholder="user@email"
              className="border rounded px-2 py-1.5 text-xs"
              aria-label="User email"
            />
            <button
              type="submit"
              className="bg-primary text-white rounded text-xs px-3 py-1.5 flex items-center justify-center gap-1"
            >
              <Search className="w-3 h-3" aria-hidden="true" /> Apply
            </button>
          </form>
        </div>

        <div className="px-6 py-4">
          {isLoading ? (
            <p className="text-sm text-gray-500 text-center py-8">Loading…</p>
          ) : items.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-8">No usages</p>
          ) : (
            <ul className="space-y-3">
              {items.map((u) => (
                <li key={u.id} className="border rounded-lg p-3 text-sm">
                  <div className="flex items-center justify-between mb-1">
                    <p className="font-medium flex items-center gap-1.5">
                      <Mail className="w-3.5 h-3.5 text-gray-400" aria-hidden="true" />
                      {u.user_email}
                    </p>
                    <span className="text-xs text-gray-400 flex items-center gap-1">
                      <Calendar className="w-3 h-3" aria-hidden="true" />
                      {formatDate(u.used_at, 'MMM dd, yyyy HH:mm')}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span className="flex items-center gap-1">
                      <Receipt className="w-3 h-3" aria-hidden="true" />
                      Booking {u.booking_id.slice(0, 8)}… · {u.booking_status}
                    </span>
                    <span className="font-medium text-success">
                      −{formatCurrency(u.discount_amount)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {meta.total_pages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-3 border-t">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => p - 1)}
                className="px-3 py-1.5 border rounded text-xs disabled:opacity-40"
              >
                Previous
              </button>
              <span className="text-xs text-gray-500">
                {page} / {meta.total_pages}
              </span>
              <button
                disabled={page >= meta.total_pages}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 border rounded text-xs disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
