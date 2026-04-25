import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { vouchersApi } from '@/api/vouchersApi'
import { formatDate, formatCurrency } from '@/utils/formatters'
import { Plus, Pencil, Trash2, Tag, CheckCircle, XCircle } from 'lucide-react'

const STATUS_BADGE = {
  active: 'bg-success/10 text-success',
  expired: 'bg-warning/10 text-warning',
  disabled: 'bg-gray-100 text-gray-500',
}

const EMPTY_FORM = {
  code: '',
  name: '',
  discount_type: 'percentage',
  discount_value: '',
  min_order_value: '0',
  max_uses: '100',
  valid_from: '',
  valid_to: '',
  status: 'active',
}

export default function ManageVouchers() {
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)

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

  const deleteMut = useMutation({
    mutationFn: (id) => vouchersApi.delete(id),
    onSuccess: () => {
      toast.success('Voucher deleted')
      qc.invalidateQueries({ queryKey: ['admin-vouchers'] })
    },
    onError: () => toast.error('Failed to delete'),
  })

  const openCreate = () => {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setShowModal(true)
  }

  const openEdit = (v) => {
    setEditingId(v.id)
    setForm({
      code: v.code,
      name: v.name,
      discount_type: v.discount_type,
      discount_value: String(v.discount_value),
      min_order_value: String(v.min_order_value),
      max_uses: String(v.max_uses),
      valid_from: v.valid_from,
      valid_to: v.valid_to,
      status: v.status,
    })
    setShowModal(true)
  }

  const closeModal = () => {
    setShowModal(false)
    setEditingId(null)
    setForm(EMPTY_FORM)
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const payload = {
      ...form,
      discount_value: parseFloat(form.discount_value),
      min_order_value: parseFloat(form.min_order_value) || 0,
      max_uses: parseInt(form.max_uses, 10),
    }
    if (editingId) {
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

  return (
    <>
      <Helmet>
        <title>Manage Vouchers — Admin</title>
      </Helmet>
      <div className="p-6 max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="font-heading text-2xl font-bold">Vouchers</h1>
            <p className="text-sm text-gray-500">Create and manage discount vouchers</p>
          </div>
          <button
            onClick={openCreate}
            className="flex items-center gap-2 bg-primary text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" /> Create Voucher
          </button>
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Code / Name</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Discount</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Usage</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Valid Period</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                Array.from({ length: 5 }, (_, i) => (
                  <tr key={i} className="border-b animate-pulse">
                    {Array.from({ length: 6 }, (_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-gray-100 rounded w-24" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-16 text-gray-400">
                    <Tag className="w-8 h-8 mx-auto mb-2 opacity-30" />
                    <p>No vouchers yet</p>
                  </td>
                </tr>
              ) : (
                items.map((v) => (
                  <tr key={v.id} className="border-b hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3">
                      <p className="font-mono font-bold text-primary">{v.code}</p>
                      <p className="text-xs text-gray-500">{v.name}</p>
                    </td>
                    <td className="px-4 py-3">
                      {v.discount_type === 'percentage'
                        ? <span className="font-semibold">{v.discount_value}%</span>
                        : <span className="font-semibold">{formatCurrency(v.discount_value)}</span>}
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
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => openEdit(v)}
                          className="p-1.5 rounded hover:bg-primary/10 text-primary transition-colors"
                          title="Edit"
                        >
                          <Pencil className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDelete(v.id, v.code)}
                          className="p-1.5 rounded hover:bg-error/10 text-error transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>

          {/* Pagination */}
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
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-5 border-b flex items-center justify-between">
              <h2 className="font-heading font-bold text-lg">
                {editingId ? 'Edit Voucher' : 'Create Voucher'}
              </h2>
              <button onClick={closeModal} className="text-gray-400 hover:text-gray-600 text-xl leading-none">&times;</button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Code *</label>
                  <input
                    required
                    value={form.code}
                    onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
                    placeholder="SUMMER20"
                    className="w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                  <input
                    required
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="Summer 20% Off"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Discount Type</label>
                  <select
                    value={form.discount_type}
                    onChange={(e) => setForm({ ...form, discount_type: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    <option value="percentage">Percentage (%)</option>
                    <option value="fixed">Fixed ($)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Discount Value {form.discount_type === 'percentage' ? '(%)' : '($)'}
                  </label>
                  <input
                    required
                    type="number"
                    min={0.01}
                    step={0.01}
                    max={form.discount_type === 'percentage' ? 100 : undefined}
                    value={form.discount_value}
                    onChange={(e) => setForm({ ...form, discount_value: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Min. Order ($)</label>
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">Max Uses</label>
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
                  <label className="block text-sm font-medium text-gray-700 mb-1">Valid From *</label>
                  <input
                    required
                    type="date"
                    value={form.valid_from}
                    onChange={(e) => setForm({ ...form, valid_from: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Valid To *</label>
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

              {editingId && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
                  <select
                    value={form.status}
                    onChange={(e) => setForm({ ...form, status: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    <option value="active">Active</option>
                    <option value="disabled">Disabled</option>
                    <option value="expired">Expired</option>
                  </select>
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={closeModal}
                  className="flex-1 border rounded-lg py-2.5 text-sm font-medium hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSaving}
                  className="flex-1 bg-primary text-white rounded-lg py-2.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                >
                  {isSaving ? 'Saving...' : editingId ? 'Save Changes' : 'Create Voucher'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  )
}
