import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { roomsApi } from '@/api/roomsApi'
import { hotelsApi } from '@/api/hotelsApi'
import { useAuth } from '@/hooks/useAuth'
import { toast } from 'sonner'
import Skeleton from '@/components/common/Skeleton'
import { formatCurrency } from '@/utils/formatters'
import { Link } from 'react-router-dom'
import { ROOM_TYPES } from '@/utils/constants'
import {
  Plus, Search, Pencil, Trash2, ChevronLeft, ChevronRight, X,
} from 'lucide-react'

export default function ManageRooms() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const ownerId = user?.role === 'superadmin' ? undefined : user?.id
  const [selectedHotel, setSelectedHotel] = useState('')
  const [page, setPage] = useState(1)
  const [modal, setModal] = useState(null)

  const { data: hotelsData } = useQuery({
    queryKey: ['all-hotels-list', user?.role, user?.id],
    queryFn: () => {
      const params = { per_page: 100 }
      if (ownerId) params.owner_id = ownerId
      return hotelsApi.list(params)
    },
    select: (res) => res.data?.items || [],
    enabled: !!user?.id,
  })

  const { data, isLoading } = useQuery({
    queryKey: ['admin-rooms', selectedHotel, page],
    queryFn: () => selectedHotel
      ? roomsApi.listByHotel(selectedHotel, { page, per_page: 10 })
      : Promise.resolve({ data: { items: [], meta: {} } }),
    select: (res) => res.data,
    enabled: !!selectedHotel,
  })

  const deleteMut = useMutation({
    mutationFn: (id) => roomsApi.delete(id),
    onSuccess: () => { toast.success('Room deleted'); qc.invalidateQueries({ queryKey: ['admin-rooms'] }) },
    onError: () => toast.error('Failed to delete'),
  })

  const saveMut = useMutation({
    mutationFn: ({ id, data }) => id ? roomsApi.update(id, data) : roomsApi.create(selectedHotel, data),
    onSuccess: () => { toast.success('Saved'); setModal(null); qc.invalidateQueries({ queryKey: ['admin-rooms'] }) },
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
      // Fallback for unexpected error shapes (FastAPI often returns an array/object)
      toast.error('Failed to save')
    },
  })

  const rooms = data?.items || []
  const meta = data?.meta || {}

  return (
    <>
      <Helmet><title>Manage Rooms — Admin</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
            <div>
              <Link to="/admin" className="text-sm text-primary hover:underline">&larr; Dashboard</Link>
              <h1 className="font-heading text-2xl font-bold text-gray-900">Manage Rooms</h1>
            </div>
            <button onClick={() => { if (!selectedHotel) { toast.error('Select a hotel first'); return }; setModal({ name: '', room_type: 'double', price_per_night: 1, total_quantity: 1, max_guests: 2 }) }}
              className="bg-primary hover:bg-primary-dark text-white font-semibold px-4 py-2 rounded-lg text-sm flex items-center gap-2">
              <Plus className="w-4 h-4" /> Add Room
            </button>
          </div>

          <div className="bg-white rounded-xl border p-5">
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">Select Hotel</label>
              <select value={selectedHotel} onChange={(e) => { setSelectedHotel(e.target.value); setPage(1) }}
                className="w-full max-w-md border rounded-lg px-4 py-2.5 text-sm">
                <option value="">— Choose a hotel —</option>
                {hotelsData?.map((h) => <option key={h.id} value={h.id}>{h.name} ({h.city})</option>)}
              </select>
            </div>

            {!selectedHotel ? (
              <div className="py-16 text-center text-gray-400">Select a hotel to view its rooms</div>
            ) : isLoading ? (
              <div className="space-y-3">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-3 font-medium">Room</th>
                      <th className="pb-3 font-medium">Type</th>
                      <th className="pb-3 font-medium">Price/Night</th>
                      <th className="pb-3 font-medium">Qty</th>
                      <th className="pb-3 font-medium">Max Guests</th>
                      <th className="pb-3 font-medium text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rooms.map((r) => (
                      <tr key={r.id} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="py-3 font-medium">{r.name}</td>
                        <td className="py-3 capitalize">{r.room_type}</td>
                        <td className="py-3">{formatCurrency(r.price_per_night)}</td>
                        <td className="py-3">{r.total_quantity}</td>
                        <td className="py-3">{r.max_guests}</td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => setModal(r)} className="p-1.5 hover:bg-gray-100 rounded" aria-label="Edit room">
                              <Pencil className="w-4 h-4 text-gray-500" />
                            </button>
                            <button onClick={() => { if (confirm('Delete this room?')) deleteMut.mutate(r.id) }}
                              className="p-1.5 hover:bg-red-50 rounded" aria-label="Delete room">
                              <Trash2 className="w-4 h-4 text-error" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {rooms.length === 0 && (
                      <tr><td colSpan={6} className="py-12 text-center text-gray-400">No rooms found</td></tr>
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
        <RoomModal room={modal} onClose={() => setModal(null)} onSave={(data) => saveMut.mutate({ id: modal.id, data })} saving={saveMut.isPending} />
      )}
    </>
  )
}

function RoomModal({ room, onClose, onSave, saving }) {
  const [form, setForm] = useState({
    name: room.name || '',
    room_type: room.room_type || 'double',
    price_per_night: room.price_per_night || 0,
    total_quantity: room.total_quantity || 1,
    max_guests: room.max_guests || 2,
    description: room.description || '',
  })

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-xl w-full max-w-lg p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-heading font-bold text-lg">{room.id ? 'Edit Room' : 'New Room'}</h2>
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
              <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
              <select value={form.room_type} onChange={(e) => setForm({ ...form, room_type: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm">
                {ROOM_TYPES.map((t) => <option key={t} value={t} className="capitalize">{t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Price/Night</label>
              <input type="number" value={form.price_per_night} onChange={(e) => setForm({ ...form, price_per_night: Number(e.target.value) })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Quantity</label>
              <input type="number" value={form.total_quantity} onChange={(e) => setForm({ ...form, total_quantity: Number(e.target.value) })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Max Guests</label>
              <input type="number" value={form.max_guests} onChange={(e) => setForm({ ...form, max_guests: Number(e.target.value) })}
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
