import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { toursApi } from '@/api/toursApi'
import { useAuth } from '@/hooks/useAuth'
import { toast } from 'sonner'
import Skeleton from '@/components/common/Skeleton'
import { formatCurrency } from '@/utils/formatters'
import { Link } from 'react-router-dom'
import { TOUR_CATEGORIES } from '@/utils/constants'
import {
  Plus, Search, Pencil, Trash2, ChevronLeft, ChevronRight, X, Clock,
} from 'lucide-react'

export default function ManageTours() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)
  const ownerId = user?.role === 'superadmin' ? undefined : user?.id

  const { data, isLoading } = useQuery({
    queryKey: ['admin-tours', page, search, user?.role, user?.id],
    queryFn: () => {
      const params = { page, per_page: 10, q: search || undefined }
      if (ownerId) params.owner_id = ownerId
      return toursApi.list(params)
    },
    select: (res) => res.data,
    enabled: !!user?.id,
  })

  const deleteMut = useMutation({
    mutationFn: (id) => toursApi.delete(id),
    onSuccess: () => { toast.success('Tour deleted'); qc.invalidateQueries({ queryKey: ['admin-tours'] }) },
    onError: () => toast.error('Failed to delete'),
  })

  const saveMut = useMutation({
    mutationFn: ({ id, data }) => id ? toursApi.update(id, data) : toursApi.create(data),
    onSuccess: () => { toast.success('Saved'); setModal(null); qc.invalidateQueries({ queryKey: ['admin-tours'] }) },
    onError: (err) => {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        toast.error(detail.map((e) => e.msg).join(', '))
        return
      }
      if (typeof detail === 'string') {
        toast.error(detail)
        return
      }
      toast.error('Failed to save')
    },
  })

  const tours = data?.items || []
  const meta = data?.meta || {}

  return (
    <>
      <Helmet><title>Manage Tours — Admin</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
            <div>
              <Link to="/admin" className="text-sm text-primary hover:underline">&larr; Dashboard</Link>
              <h1 className="font-heading text-2xl font-bold text-gray-900">Manage Tours</h1>
            </div>
            <button onClick={() => setModal({ name: '', city: '', country: '', category: 'adventure', duration_days: 1, max_participants: 20, price_per_person: 1, description: '' })}
              className="bg-primary hover:bg-primary-dark text-white font-semibold px-4 py-2 rounded-lg text-sm flex items-center gap-2">
              <Plus className="w-4 h-4" /> Add Tour
            </button>
          </div>

          <div className="bg-white rounded-xl border p-5">
            <div className="mb-4 relative max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }}
                placeholder="Search tours..." className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm" />
            </div>

            {isLoading ? (
              <div className="space-y-3">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-3 font-medium">Tour</th>
                      <th className="pb-3 font-medium">Location</th>
                      <th className="pb-3 font-medium">Category</th>
                      <th className="pb-3 font-medium">Duration</th>
                      <th className="pb-3 font-medium">Price</th>
                      <th className="pb-3 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tours.map((t) => (
                      <tr key={t.id} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="py-3 font-medium">{t.name}</td>
                        <td className="py-3 text-gray-500">{t.city}, {t.country}</td>
                        <td className="py-3 capitalize">{t.category}</td>
                        <td className="py-3 flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{t.duration_days}d</td>
                        <td className="py-3">{formatCurrency(t.price_per_person)}</td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => setModal(t)} className="p-1.5 hover:bg-gray-100 rounded" aria-label="Edit tour">
                              <Pencil className="w-4 h-4 text-gray-500" />
                            </button>
                            <button onClick={() => { if (confirm('Delete this tour?')) deleteMut.mutate(t.id) }}
                              className="p-1.5 hover:bg-red-50 rounded" aria-label="Delete tour">
                              <Trash2 className="w-4 h-4 text-error" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {tours.length === 0 && (
                      <tr><td colSpan={6} className="py-12 text-center text-gray-400">No tours found</td></tr>
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

      {modal && (
        <TourModal tour={modal} onClose={() => setModal(null)} onSave={(data) => saveMut.mutate({ id: modal.id, data })} saving={saveMut.isPending} />
      )}
    </>
  )
}

function TourModal({ tour, onClose, onSave, saving }) {
  const [form, setForm] = useState({
    name: tour.name || '',
    city: tour.city || '',
    country: tour.country || '',
    category: tour.category || 'adventure',
    duration_days: tour.duration_days || 1,
    max_participants: tour.max_participants || 20,
    price_per_person: tour.price_per_person || 0,
    description: tour.description || '',
  })

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-heading font-bold text-lg">{tour.id ? 'Edit Tour' : 'New Tour'}</h2>
          <button onClick={onClose}><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); onSave(form) }} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required
              className="w-full border rounded-lg px-4 py-2.5 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
              <input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} required
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Country</label>
              <input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} required
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Category</label>
              <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm">
                {TOUR_CATEGORIES.map((c) => <option key={c} value={c} className="capitalize">{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Duration (days)</label>
              <input type="number" min={1} value={form.duration_days} onChange={(e) => setForm({ ...form, duration_days: Number(e.target.value) })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Participants</label>
              <input type="number" min={1} value={form.max_participants} onChange={(e) => setForm({ ...form, max_participants: Number(e.target.value) })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Price/Person</label>
              <input type="number" value={form.price_per_person} onChange={(e) => setForm({ ...form, price_per_person: Number(e.target.value) })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm resize-none h-20" />
          </div>
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 border py-2.5 rounded-lg text-sm font-medium">Cancel</button>
            <button type="submit" disabled={saving}
              className="flex-1 bg-primary hover:bg-primary-dark text-white py-2.5 rounded-lg text-sm font-semibold disabled:opacity-50">
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
