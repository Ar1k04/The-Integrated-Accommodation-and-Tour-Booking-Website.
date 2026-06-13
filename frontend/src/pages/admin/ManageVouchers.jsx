import { useMemo, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { vouchersApi } from '@/api/vouchersApi'
import { formatDate, formatCurrency } from '@/utils/formatters'
import {
  Plus,
  Pencil,
  Trash2,
  Tag,
  Eye,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  MinusCircle,
} from 'lucide-react'
import VoucherUsageDrawer from '@/components/admin/VoucherUsageDrawer'

const STATUS_BADGE = {
  active: 'bg-success/10 text-success',
  expired: 'bg-warning/10 text-warning',
  disabled: 'bg-gray-100 text-gray-500',
}

const SYNC_BADGE = {
  synced: { cls: 'bg-success/10 text-success', icon: CheckCircle2, label: 'Synced' },
  failed: { cls: 'bg-error/10 text-error', icon: XCircle, label: 'Failed' },
  not_synced: { cls: 'bg-gray-100 text-gray-500', icon: MinusCircle, label: 'Not synced' },
  disabled: { cls: 'bg-gray-100 text-gray-400', icon: AlertTriangle, label: 'Sync disabled' },
}

const CURRENCIES = ['USD', 'VND', 'EUR', 'GBP', 'SGD']
const APPLICABLE_TO = [
  { value: 'all', label: 'All products' },
  { value: 'hotel', label: 'Hotels only' },
  { value: 'tour', label: 'Tours only' },
  { value: 'flight', label: 'Flights only' },
]

const EMPTY_FORM = {
  code: '',
  name: '',
  discount_type: 'percentage',
  discount_value: '',
  maximum_discount_amount: '',
  currency: 'USD',
  min_order_value: '0',
  budget: '',
  max_uses: '100',
  valid_from: '',
  valid_to: '',
  status: 'active',
  guest_id: '',
  description: '',
  terms_and_conditions: '',
  applicable_to: 'all',
}

function SyncBadge({ status, error }) {
  const cfg = SYNC_BADGE[status] || SYNC_BADGE.not_synced
  const Icon = cfg.icon
  return (
    <span
      className={`text-xs px-2 py-1 rounded-full inline-flex items-center gap-1 ${cfg.cls}`}
      title={status === 'failed' && error ? error : undefined}
    >
      <Icon className="w-3 h-3" aria-hidden="true" />
      {cfg.label}
    </span>
  )
}

export default function ManageVouchers() {
  const qc = useQueryClient()
  const { t } = useTranslation('admin')
  const [tab, setTab] = useState('vouchers')
  const [page, setPage] = useState(1)
  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editingVoucher, setEditingVoucher] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [drawerVoucher, setDrawerVoucher] = useState(null)

  const { data, isLoading } = useQuery({
    queryKey: ['admin-vouchers', page],
    queryFn: () => vouchersApi.list({ page, per_page: 20 }),
    select: (res) => res.data,
  })

  const items = data?.items || []
  const meta = data?.meta || {}

  const createMut = useMutation({
    mutationFn: (body) => vouchersApi.create(body),
    onSuccess: () => {
      toast.success('Voucher created')
      qc.invalidateQueries({ queryKey: ['admin-vouchers'] })
      closeModal()
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to create'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => vouchersApi.update(id, data),
    onSuccess: () => {
      toast.success('Voucher updated')
      qc.invalidateQueries({ queryKey: ['admin-vouchers'] })
      closeModal()
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to update'),
  })

  const disableMut = useMutation({
    mutationFn: (id) => vouchersApi.toggleStatus(id, 'disabled'),
    onSuccess: () => {
      toast.success('Voucher disabled')
      qc.invalidateQueries({ queryKey: ['admin-vouchers'] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to disable'),
  })

  const deleteMut = useMutation({
    mutationFn: (id) => vouchersApi.delete(id),
    onSuccess: () => {
      toast.success('Voucher deleted')
      qc.invalidateQueries({ queryKey: ['admin-vouchers'] })
    },
    onError: (err, id) => {
      const detail = err.response?.data?.detail
      // A used voucher can't be deleted (it would drop usage history). Offer to
      // disable it instead, which is the supported way to retire it.
      if (err.response?.status === 409) {
        if (confirm(`${detail}\n\nDisable this voucher instead?`)) {
          disableMut.mutate(id)
        }
        return
      }
      toast.error(detail || 'Failed to delete')
    },
  })

  const syncMut = useMutation({
    mutationFn: (id) => vouchersApi.syncToLiteapi(id),
    onSuccess: () => {
      toast.success('Synced to LiteAPI')
      qc.invalidateQueries({ queryKey: ['admin-vouchers'] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Sync failed'),
  })

  const openCreate = () => {
    setEditingId(null)
    setEditingVoucher(null)
    setForm(EMPTY_FORM)
    setShowModal(true)
  }

  const openEdit = (v) => {
    setEditingId(v.id)
    setEditingVoucher(v)
    setForm({
      code: v.code,
      name: v.name,
      discount_type: v.discount_type,
      discount_value: String(v.discount_value),
      maximum_discount_amount: v.maximum_discount_amount != null ? String(v.maximum_discount_amount) : '',
      currency: v.currency || 'USD',
      min_order_value: String(v.min_order_value),
      budget: v.budget != null ? String(v.budget) : '',
      max_uses: String(v.max_uses),
      valid_from: v.valid_from,
      valid_to: v.valid_to,
      status: v.status,
      guest_id: v.guest_id || '',
      description: v.description || '',
      terms_and_conditions: v.terms_and_conditions || '',
      applicable_to: v.applicable_to || 'all',
    })
    setShowModal(true)
  }

  const closeModal = () => {
    setShowModal(false)
    setEditingId(null)
    setEditingVoucher(null)
    setForm(EMPTY_FORM)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const payload = {
      ...form,
      discount_value: parseFloat(form.discount_value),
      maximum_discount_amount:
        form.discount_type === 'percentage' && form.maximum_discount_amount !== ''
          ? parseFloat(form.maximum_discount_amount)
          : null,
      min_order_value: parseFloat(form.min_order_value) || 0,
      budget: form.budget !== '' ? parseFloat(form.budget) : null,
      max_uses: parseInt(form.max_uses, 10),
      guest_id: form.guest_id || null,
      description: form.description || null,
      terms_and_conditions: form.terms_and_conditions || null,
    }
    // For percentage with no cap, omit the field so backend stores NULL.
    if (payload.maximum_discount_amount === null) {
      delete payload.maximum_discount_amount
    }
    if (editingId) {
      // Don't send code on update — it isn't editable.
      delete payload.code
      updateMut.mutate({ id: editingId, data: payload })
    } else {
      createMut.mutate(payload)
    }
  }

  const handleDelete = (id, code) => {
    if (!window.confirm(`Delete voucher "${code}"?`)) return
    deleteMut.mutate(id)
  }

  const isSaving = createMut.isPending || updateMut.isPending
  const syncLocked = useMemo(
    () => editingVoucher?.liteapi_sync_status === 'synced',
    [editingVoucher]
  )

  return (
    <>
      <Helmet>
        <title>{t('sidebar.vouchers')} — Admin</title>
      </Helmet>
      <div className="p-6 max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="font-heading text-2xl font-bold">{t('sidebar.vouchers')}</h1>
            <p className="text-sm text-gray-500">Manage promo codes, budget pools, and view usage analytics.</p>
          </div>
          {tab === 'vouchers' && (
            <button
              onClick={openCreate}
              className="flex items-center gap-2 bg-primary text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              <Plus className="w-4 h-4" aria-hidden="true" /> {t('actions.addVoucher')}
            </button>
          )}
        </div>

        <div className="border-b mb-4 flex gap-1">
          <button
            onClick={() => setTab('vouchers')}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === 'vouchers'
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Vouchers
          </button>
          <button
            onClick={() => setTab('history')}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === 'history'
                ? 'border-primary text-primary'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Usage History
          </button>
        </div>

        {tab === 'vouchers' && (
          <div className="bg-white rounded-xl border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">{t('table.code')} / {t('table.name')}</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">{t('table.discount')}</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">{t('table.uses')}</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">Budget</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">{t('table.validFrom')} / {t('table.validTo')}</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">{t('table.status')}</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">LiteAPI</th>
                  <th className="text-left px-4 py-3 font-medium text-gray-600">{t('table.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  Array.from({ length: 5 }, (_, i) => (
                    <tr key={i} className="border-b animate-pulse">
                      {Array.from({ length: 8 }, (_, j) => (
                        <td key={j} className="px-4 py-3">
                          <div className="h-4 bg-gray-100 rounded w-20" />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : items.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="text-center py-16 text-gray-400">
                      <Tag className="w-8 h-8 mx-auto mb-2 opacity-30" aria-hidden="true" />
                      <p>{t('empty.noVouchers')}</p>
                    </td>
                  </tr>
                ) : (
                  items.map((v) => (
                    <tr key={v.id} className="border-b hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-mono font-bold text-primary">{v.code}</p>
                        <p className="text-xs text-gray-500">{v.name}</p>
                        {v.guest_id && (
                          <span className="inline-block mt-1 text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 rounded">
                            Guest-locked
                          </span>
                        )}
                        {v.applicable_to !== 'all' && (
                          <span className="inline-block mt-1 ml-1 text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded capitalize">
                            {v.applicable_to}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {v.discount_type === 'percentage'
                          ? <span className="font-semibold">{v.discount_value}%</span>
                          : <span className="font-semibold">{formatCurrency(v.discount_value)}</span>}
                        {v.maximum_discount_amount != null && (
                          <p className="text-xs text-gray-400">cap {formatCurrency(v.maximum_discount_amount)}</p>
                        )}
                        {v.min_order_value > 0 && (
                          <p className="text-xs text-gray-400">min. {formatCurrency(v.min_order_value)}</p>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className={v.used_count >= v.max_uses ? 'text-error' : 'text-gray-700'}>
                          {v.used_count}
                        </span>
                        <span className="text-gray-400"> / {v.max_uses}</span>
                      </td>
                      <td className="px-4 py-3 text-xs">
                        {v.budget != null ? (
                          <>
                            <p className="text-gray-700">{formatCurrency(v.budget_used)} / {formatCurrency(v.budget)}</p>
                            <p className="text-gray-400">left {formatCurrency(v.budget_remaining ?? 0)}</p>
                          </>
                        ) : (
                          <span className="text-gray-400">∞</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-gray-500">
                        <p>{formatDate(v.valid_from)}</p>
                        <p>→ {formatDate(v.valid_to)}</p>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`text-xs px-2 py-1 rounded-full font-medium capitalize ${STATUS_BADGE[v.status] || 'bg-gray-100'}`}>
                          {v.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <SyncBadge status={v.liteapi_sync_status} error={v.liteapi_sync_error} />
                        {(v.liteapi_sync_status === 'not_synced' ||
                          v.liteapi_sync_status === 'failed') && (
                          <button
                            onClick={() => syncMut.mutate(v.id)}
                            disabled={syncMut.isPending}
                            className="mt-1 text-[10px] text-primary hover:underline flex items-center gap-1 disabled:opacity-50"
                            aria-label="Sync to LiteAPI"
                          >
                            <RefreshCw className="w-3 h-3" aria-hidden="true" />
                            {v.liteapi_sync_status === 'failed' ? 'Retry' : 'Sync now'}
                          </button>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => setDrawerVoucher(v)}
                            className="p-1.5 rounded hover:bg-gray-100 text-gray-600 transition-colors"
                            aria-label="View usage history"
                            title="View usage history"
                          >
                            <Eye className="w-4 h-4" aria-hidden="true" />
                          </button>
                          <button
                            onClick={() => openEdit(v)}
                            className="p-1.5 rounded hover:bg-primary/10 text-primary transition-colors"
                            aria-label={t('actions.edit')}
                          >
                            <Pencil className="w-4 h-4" aria-hidden="true" />
                          </button>
                          <button
                            onClick={() => handleDelete(v.id, v.code)}
                            className="p-1.5 rounded hover:bg-error/10 text-error transition-colors"
                            aria-label={t('actions.delete')}
                          >
                            <Trash2 className="w-4 h-4" aria-hidden="true" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>

            {meta.total_pages > 1 && (
              <div className="flex items-center justify-between px-4 py-3 border-t">
                <p className="text-sm text-gray-500">
                  {meta.total} voucher{meta.total !== 1 ? 's' : ''}
                </p>
                <div className="flex gap-2">
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="px-3 py-1.5 border rounded text-sm disabled:opacity-40 hover:bg-gray-50"
                  >
                    Previous
                  </button>
                  <span className="px-3 py-1.5 text-sm text-gray-500">
                    {page} / {meta.total_pages}
                  </span>
                  <button
                    disabled={page >= meta.total_pages}
                    onClick={() => setPage((p) => p + 1)}
                    className="px-3 py-1.5 border rounded text-sm disabled:opacity-40 hover:bg-gray-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {tab === 'history' && <UsageHistoryTab />}
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onKeyDown={(e) => e.key === 'Escape' && closeModal()}>
          <div role="dialog" aria-modal="true" aria-labelledby="voucher-modal-title"
            className="bg-white rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-5 border-b flex items-center justify-between">
              <h2 id="voucher-modal-title" className="font-heading font-bold text-lg">
                {editingId ? t('actions.editVoucher') : t('actions.newVoucher')}
              </h2>
              <button onClick={closeModal} aria-label={t('actions.cancel')} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              {syncLocked && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-800">
                  This voucher is synced to LiteAPI. Discount value/type and currency are locked. Unsync first to change them.
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.code')} *</label>
                  <input
                    required
                    disabled={!!editingId}
                    value={form.code}
                    onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
                    placeholder="SUMMER20"
                    className="w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:bg-gray-50 disabled:text-gray-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.name')} *</label>
                  <input
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="Summer 20% Off"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.discountType')}</label>
                  <select
                    disabled={syncLocked}
                    value={form.discount_type}
                    onChange={(e) => setForm({ ...form, discount_type: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:bg-gray-50"
                  >
                    <option value="percentage">{t('form.percentage')} (%)</option>
                    <option value="fixed">{t('form.fixed')} ($)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {t('form.discountValue')} {form.discount_type === 'percentage' ? '(%)' : '($)'}
                  </label>
                  <input
                    required
                    disabled={syncLocked}
                    type="number"
                    min={0.01}
                    step={0.01}
                    max={form.discount_type === 'percentage' ? 100 : undefined}
                    value={form.discount_value}
                    onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:bg-gray-50"
                  />
                </div>
                {form.discount_type === 'percentage' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Max discount cap ($)
                    </label>
                    <input
                      type="number"
                      min={0.01}
                      step={0.01}
                      value={form.maximum_discount_amount}
                      onChange={(e) => setForm({ ...form, maximum_discount_amount: e.target.value })}
                      placeholder="optional"
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    />
                  </div>
                )}
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Currency</label>
                  <select
                    disabled={syncLocked}
                    value={form.currency}
                    onChange={(e) => setForm({ ...form, currency: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:bg-gray-50"
                  >
                    {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.minOrderValue')} ($)</label>
                  <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={form.min_order_value}
                    onChange={(e) => setForm({ ...form, min_order_value: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.maxUses')}</label>
                  <input
                    required
                    type="number"
                    min={1}
                    value={form.max_uses}
                    onChange={(e) => setForm({ ...form, max_uses: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Budget pool ($)</label>
                  <input
                    type="number"
                    min={0.01}
                    step={0.01}
                    value={form.budget}
                    onChange={(e) => setForm({ ...form, budget: e.target.value })}
                    placeholder="optional (unlimited if empty)"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                  {editingId && editingVoucher?.budget != null && (
                    <p className="text-xs text-gray-400 mt-1">
                      used {formatCurrency(editingVoucher.budget_used)} of {formatCurrency(editingVoucher.budget)}
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Applies to</label>
                  <select
                    disabled={syncLocked}
                    value={form.applicable_to}
                    onChange={(e) => setForm({ ...form, applicable_to: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:bg-gray-50"
                  >
                    {APPLICABLE_TO.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                  {form.applicable_to !== 'all' && form.applicable_to !== 'hotel' && (
                    <p className="text-xs text-amber-600 mt-1">Tour/Flight vouchers cannot sync to LiteAPI.</p>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.validFrom')} *</label>
                  <input
                    required
                    type="date"
                    value={form.valid_from}
                    onChange={(e) => setForm({ ...form, valid_from: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.validTo')} *</label>
                  <input
                    required
                    type="date"
                    value={form.valid_to}
                    min={form.valid_from}
                    onChange={(e) => setForm({ ...form, valid_to: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Guest user ID (optional)
                </label>
                <input
                  type="text"
                  value={form.guest_id}
                  onChange={(e) => setForm({ ...form, guest_id: e.target.value })}
                  placeholder="UUID — leave empty for any customer"
                  className="w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
                <p className="text-xs text-gray-400 mt-1">
                  Reserve this voucher for one specific user (refund, VIP gift). Guest-locked vouchers are not synced to LiteAPI.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  rows={2}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Terms &amp; conditions</label>
                <textarea
                  value={form.terms_and_conditions}
                  onChange={(e) => setForm({ ...form, terms_and_conditions: e.target.value })}
                  rows={2}
                  className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              {editingId && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.status')}</label>
                  <select
                    value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    <option value="active">{t('status.active')}</option>
                    <option value="disabled">{t('status.disabled')}</option>
                    <option value="expired">{t('status.expired')}</option>
                  </select>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="flex-1 border rounded-lg py-2.5 text-sm font-medium hover:bg-gray-50 transition-colors"
                >
                  {t('actions.cancel')}
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="flex-1 bg-primary text-white rounded-lg py-2.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {isSaving ? t('actions.saving') : editingId ? t('actions.save') : t('actions.addVoucher')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {drawerVoucher && (
        <VoucherUsageDrawer voucher={drawerVoucher} onClose={() => setDrawerVoucher(null)} />
      )}
    </>
  )
}

function UsageHistoryTab() {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({
    date_from: '',
    date_to: '',
    user_email: '',
    voucher_code: '',
  })
  const [draft, setDraft] = useState(filters)

  const { data, isLoading, error } = useQuery({
    queryKey: ['admin-voucher-usages', page, filters],
    queryFn: () =>
      vouchersApi.listAllUsages({
        page,
        per_page: 20,
        ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v)),
      }),
    select: (res) => res.data,
  })

  if (error?.response?.status === 403) {
    return (
      <div className="bg-white rounded-xl border p-8 text-center text-gray-500">
        Aggregated usage history is admin-only. Use the per-voucher "View usage" button in the Vouchers tab.
      </div>
    )
  }

  const items = data?.items || []
  const meta = data?.meta || {}

  const apply = (e) => {
    e.preventDefault()
    setPage(1)
    setFilters(draft)
  }

  return (
    <div className="bg-white rounded-xl border overflow-hidden">
      <form onSubmit={apply} className="px-4 py-3 border-b bg-gray-50 grid grid-cols-5 gap-2">
        <input
          type="date"
          value={draft.date_from}
          onChange={(e) => setDraft({ ...draft, date_from: e.target.value })}
          className="border rounded px-2 py-1.5 text-xs"
          aria-label="Date from"
        />
        <input
          type="date"
          value={draft.date_to}
          onChange={(e) => setDraft({ ...draft, date_to: e.target.value })}
          className="border rounded px-2 py-1.5 text-xs"
          aria-label="Date to"
        />
        <input
          type="email"
          value={draft.user_email}
          placeholder="user@email"
          onChange={(e) => setDraft({ ...draft, user_email: e.target.value })}
          className="border rounded px-2 py-1.5 text-xs"
        />
        <input
          type="text"
          value={draft.voucher_code}
          placeholder="voucher code"
          onChange={(e) => setDraft({ ...draft, voucher_code: e.target.value })}
          className="border rounded px-2 py-1.5 text-xs font-mono"
        />
        <button type="submit" className="bg-primary text-white rounded text-xs px-3 py-1.5">Filter</button>
      </form>

      <div className="px-4 py-2 border-b text-xs text-gray-500 flex gap-6">
        <span>Total uses: <strong className="text-gray-800">{meta.total ?? 0}</strong></span>
        <span>
          Total discount:{' '}
          <strong className="text-gray-800">
            {meta.total_discount_amount != null
              ? formatCurrency(meta.total_discount_amount)
              : '—'}
          </strong>
        </span>
      </div>

      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b">
          <tr>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Voucher</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">User</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Booking</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Discount</th>
            <th className="text-left px-4 py-3 font-medium text-gray-600">Used at</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            Array.from({ length: 5 }, (_, i) => (
              <tr key={i} className="border-b animate-pulse">
                {Array.from({ length: 5 }, (_, j) => (
                  <td key={j} className="px-4 py-3">
                    <div className="h-4 bg-gray-100 rounded w-24" />
                  </td>
                ))}
              </tr>
            ))
          ) : items.length === 0 ? (
            <tr>
              <td colSpan={5} className="text-center py-16 text-gray-400">No usage records</td>
            </tr>
          ) : (
            items.map((u) => (
              <tr key={u.id} className="border-b hover:bg-gray-50">
                <td className="px-4 py-3">
                  <p className="font-mono text-primary font-bold">{u.voucher_code}</p>
                  <p className="text-xs text-gray-500">{u.voucher_name}</p>
                </td>
                <td className="px-4 py-3 text-xs">
                  <p>{u.user_email}</p>
                  {u.user_full_name && <p className="text-gray-400">{u.user_full_name}</p>}
                </td>
                <td className="px-4 py-3 text-xs">
                  <p className="font-mono">{u.booking_id.slice(0, 8)}…</p>
                  <p className="text-gray-400 capitalize">{u.booking_status}</p>
                </td>
                <td className="px-4 py-3 font-medium text-success">
                  −{formatCurrency(u.discount_amount)}
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {formatDate(u.used_at, 'MMM dd, yyyy HH:mm')}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {meta.total_pages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t">
          <p className="text-sm text-gray-500">{meta.total} record{meta.total !== 1 ? 's' : ''}</p>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1.5 border rounded text-sm disabled:opacity-40"
            >
              Previous
            </button>
            <span className="px-3 py-1.5 text-sm text-gray-500">{page} / {meta.total_pages}</span>
            <button
              disabled={page >= meta.total_pages}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1.5 border rounded text-sm disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
