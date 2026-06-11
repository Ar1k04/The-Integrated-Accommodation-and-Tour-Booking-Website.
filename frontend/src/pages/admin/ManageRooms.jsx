import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { useEscapeKey } from '@/hooks/useEscapeKey'
import { roomsApi } from '@/api/roomsApi'
import { hotelsApi } from '@/api/hotelsApi'
import { useAuth } from '@/hooks/useAuth'
import { toast } from 'sonner'
import Skeleton from '@/components/common/Skeleton'
import { formatCurrency } from '@/utils/formatters'
import { Link } from 'react-router-dom'
import { ROOM_TYPES, CURRENCIES, DEFAULT_CURRENCY } from '@/utils/constants'
import {
  Plus, Search, Pencil, Trash2, ChevronLeft, ChevronRight, X, Upload,
} from 'lucide-react'

export default function ManageRooms() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const { t } = useTranslation('admin')
  const ownerId = user?.role === 'admin' ? undefined : user?.id
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
    mutationFn: async ({ id, data, files, imageOrder }) => {
      const res = id ? await roomsApi.update(id, data) : await roomsApi.create(selectedHotel, data)
      const roomId = res.data?.id || id
      if (files?.length && roomId) {
        const fd = new FormData()
        files.forEach((f) => fd.append('files', f))
        const uploadRes = await roomsApi.uploadImages(roomId, fd)
        const allUrls = uploadRes.data?.images || []
        const newUrls = allUrls.slice(-(files.length))
        let newIdx = 0
        const finalImages = imageOrder.map((item) =>
          item.type === 'existing' ? item.url : newUrls[newIdx++]
        )
        await roomsApi.update(roomId, { images: finalImages })
        return uploadRes
      }
      return res
    },
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
      <Helmet><title>{t('dashboard.manageRooms')} — Admin</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
            <div>
              <Link to="/admin" className="text-sm text-primary hover:underline">{t('actions.backToDashboard')}</Link>
              <h1 className="font-heading text-2xl font-bold text-gray-900">{t('dashboard.manageRooms')}</h1>
            </div>
            <button onClick={() => { if (!selectedHotel) { toast.error(t('empty.selectHotelFirst')); return }; setModal({ name: '', room_type: 'double', price_per_night: 1, total_quantity: 1, max_guests: 2 }) }}
              className="bg-primary hover:bg-primary-dark text-white font-semibold px-4 py-2 rounded-lg text-sm flex items-center gap-2">
              <Plus className="w-4 h-4" aria-hidden="true" /> {t('actions.addRoom')}
            </button>
          </div>

          <div className="bg-white rounded-xl border p-5">
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.selectHotel')}</label>
              <select value={selectedHotel} onChange={(e) => { setSelectedHotel(e.target.value); setPage(1) }}
                aria-label={t('form.selectHotel')}
                className="w-full max-w-md border rounded-lg px-4 py-2.5 text-sm">
                <option value="">{t('form.selectHotelPrompt')}</option>
                {hotelsData?.map((h) => <option key={h.id} value={h.id}>{h.name} ({h.city})</option>)}
              </select>
            </div>

            {!selectedHotel ? (
              <div className="py-16 text-center text-gray-400">{t('empty.selectHotelFirst')}</div>
            ) : isLoading ? (
              <div className="space-y-3">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-3 font-medium">{t('table.roomName')}</th>
                      <th className="pb-3 font-medium">{t('table.type')}</th>
                      <th className="pb-3 font-medium">{t('table.pricePerNight')}</th>
                      <th className="pb-3 font-medium">{t('table.quantity')}</th>
                      <th className="pb-3 font-medium">{t('table.maxGuests')}</th>
                      <th className="pb-3 font-medium text-right">{t('table.actions')}</th>
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
                      <tr><td colSpan={6} className="py-12 text-center text-gray-400">{t('empty.noRoomsGeneral')}</td></tr>
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
        <RoomModal
          room={modal}
          hotelCurrency={hotelsData?.find((h) => h.id === selectedHotel)?.currency || DEFAULT_CURRENCY}
          onClose={() => setModal(null)}
          onSave={(data, files, imageOrder) => saveMut.mutate({ id: modal.id, data, files, imageOrder })}
          saving={saveMut.isPending}
        />
      )}
    </>
  )
}

function RoomModal({ room, hotelCurrency, onClose, onSave, saving }) {
  const { t } = useTranslation('admin')
  useEscapeKey(onClose)
  const currencyInfo = CURRENCIES.find((c) => c.code === hotelCurrency) || CURRENCIES[0]
  const defaultTiers = [
    { min_age: 0, max_age: 5, discount_percent: 100 },
    { min_age: 6, max_age: 12, discount_percent: 50 },
    { min_age: 13, max_age: 17, discount_percent: 25 },
  ]
  const [form, setForm] = useState({
    name: room.name || '',
    room_type: room.room_type || 'double',
    price_per_night: room.price_per_night || 0,
    total_quantity: room.total_quantity || 1,
    max_guests: room.max_guests || 2,
    description: room.description || '',
    child_age_tiers: room.child_age_tiers || null,
    refundable: room.refundable ?? true,
    free_cancellation_days: room.free_cancellation_days ?? 1,
    cancellation_fee_percent: room.cancellation_fee_percent ?? 20,
  })
  const customTiers = form.child_age_tiers !== null
  const tiers = form.child_age_tiers || defaultTiers
  const setTier = (idx, patch) => {
    const next = tiers.map((t, i) => (i === idx ? { ...t, ...patch } : t))
    setForm({ ...form, child_age_tiers: next })
  }

  const [images, setImages] = useState(() =>
    (room.images || []).map((url) => ({ type: 'existing', url }))
  )

  const handleFiles = (e) => {
    const selected = Array.from(e.target.files || [])
    const newItems = selected.map((f) => ({ type: 'new', file: f, preview: URL.createObjectURL(f) }))
    setImages((prev) => [...prev, ...newItems])
  }

  const removeImage = (idx) => {
    setImages((prev) => {
      const item = prev[idx]
      if (item.type === 'new') URL.revokeObjectURL(item.preview)
      return prev.filter((_, i) => i !== idx)
    })
  }

  const setAsThumbnail = (idx) => {
    if (idx === 0) return
    setImages((prev) => {
      const reordered = [...prev]
      const [moved] = reordered.splice(idx, 1)
      reordered.unshift(moved)
      return reordered
    })
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    const payload = { ...form }
    payload.images = images.filter((img) => img.type === 'existing').map((img) => img.url)
    const newFiles = images.filter((img) => img.type === 'new').map((img) => img.file)
    const imageOrder = images.map((img) => ({ type: img.type, url: img.url }))
    onSave(payload, newFiles, imageOrder)
  }

  const modalTitle = room.id ? t('actions.editRoom') : t('actions.newRoom')

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="room-modal-title"
        className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 id="room-modal-title" className="font-heading font-bold text-lg">{modalTitle}</h2>
          <button onClick={onClose} aria-label={t('actions.cancel')}><X className="w-5 h-5" aria-hidden="true" /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.name')}</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required
              className="w-full border rounded-lg px-4 py-2.5 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.roomType')}</label>
              <select value={form.room_type} onChange={(e) => setForm({ ...form, room_type: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm">
                {ROOM_TYPES.map((rt) => <option key={rt} value={rt} className="capitalize">{rt}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('form.pricePerNight')} <span className="text-gray-400 font-normal">({currencyInfo.code})</span>
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm pointer-events-none">
                  {currencyInfo.symbol}
                </span>
                <input type="number" min="0" step="0.01" value={form.price_per_night}
                  onChange={(e) => setForm({ ...form, price_per_night: Number(e.target.value) })}
                  className="w-full border rounded-lg pl-8 pr-4 py-2.5 text-sm" />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.totalQuantity')}</label>
              <input type="number" value={form.total_quantity} onChange={(e) => setForm({ ...form, total_quantity: Number(e.target.value) })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.maxGuests')}</label>
              <input type="number" value={form.max_guests} onChange={(e) => setForm({ ...form, max_guests: Number(e.target.value) })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.description')}</label>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm resize-none h-20" />
          </div>

          <div className="border rounded-lg p-3 bg-gray-50">
            <label className="flex items-center gap-2 text-sm font-medium text-gray-800">
              <input
                type="checkbox"
                checked={customTiers}
                onChange={(e) => setForm({
                  ...form,
                  child_age_tiers: e.target.checked ? defaultTiers : null,
                })}
              />
              Custom child pricing
            </label>
            <p className="text-xs text-gray-500 mt-1">
              Default: 0–5 free, 6–12 half price, 13–17 25% off.
            </p>
            {customTiers && (
              <div className="space-y-2 mt-3">
                {tiers.map((tier, idx) => (
                  <div key={idx} className="grid grid-cols-3 gap-2 items-center text-xs">
                    <div>
                      <label className="text-gray-500 block mb-0.5">Min age</label>
                      <input
                        type="number" min={0} max={17}
                        value={tier.min_age}
                        onChange={(e) => setTier(idx, { min_age: Number(e.target.value) })}
                        className="w-full border rounded px-2 py-1 text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-gray-500 block mb-0.5">Max age</label>
                      <input
                        type="number" min={0} max={17}
                        value={tier.max_age}
                        onChange={(e) => setTier(idx, { max_age: Number(e.target.value) })}
                        className="w-full border rounded px-2 py-1 text-sm"
                      />
                    </div>
                    <div>
                      <label className="text-gray-500 block mb-0.5">Discount %</label>
                      <input
                        type="number" min={0} max={100}
                        value={tier.discount_percent}
                        onChange={(e) => setTier(idx, { discount_percent: Number(e.target.value) })}
                        className="w-full border rounded px-2 py-1 text-sm"
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="border rounded-lg p-3 bg-gray-50">
            <label className="flex items-center gap-2 text-sm font-medium text-gray-800">
              <input
                type="checkbox"
                checked={form.refundable}
                onChange={(e) => setForm({ ...form, refundable: e.target.checked })}
              />
              {t('form.refundable')}
            </label>
            <p className="text-xs text-gray-500 mt-1">{t('form.refundableHint')}</p>
            {form.refundable && (
              <div className="grid grid-cols-2 gap-2 mt-3">
                <div>
                  <label className="text-gray-500 block mb-0.5 text-xs">{t('form.freeCancelDays')}</label>
                  <input
                    type="number" min={0}
                    value={form.free_cancellation_days}
                    onChange={(e) => setForm({ ...form, free_cancellation_days: Number(e.target.value) })}
                    className="w-full border rounded px-2 py-1 text-sm"
                  />
                </div>
                <div>
                  <label className="text-gray-500 block mb-0.5 text-xs">{t('form.cancelFeePercent')}</label>
                  <input
                    type="number" min={0} max={100}
                    value={form.cancellation_fee_percent}
                    onChange={(e) => setForm({ ...form, cancellation_fee_percent: Number(e.target.value) })}
                    className="w-full border rounded px-2 py-1 text-sm"
                  />
                </div>
              </div>
            )}
          </div>

          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">{t('form.images')}</label>
              {images.length > 1 && (
                <span className="text-xs text-gray-400">{t('actions.setAsThumbnail')}</span>
              )}
            </div>
            {images.length > 0 && (
              <div className="grid grid-cols-4 gap-2 mb-3">
                {images.map((item, idx) => {
                  const isThumbnail = idx === 0
                  const src = item.type === 'existing' ? item.url : item.preview
                  return (
                    <div key={`${item.type}-${idx}`}
                      className={`relative group aspect-square rounded-lg overflow-hidden cursor-pointer transition-all ${isThumbnail ? 'ring-2 ring-primary ring-offset-1' : 'border hover:ring-1 hover:ring-gray-300'}`}
                      onClick={() => setAsThumbnail(idx)}>
                      <img src={src} alt="" className="w-full h-full object-cover" />
                      {isThumbnail && (
                        <span className="absolute top-1 left-1 bg-primary text-white text-[10px] font-semibold px-1.5 py-0.5 rounded">
                          {t('actions.thumbnail')}
                        </span>
                      )}
                      {!isThumbnail && (
                        <span className="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                          <span className="text-white text-[10px] font-medium">{t('actions.setAsThumbnail')}</span>
                        </span>
                      )}
                      <button type="button"
                        onClick={(e) => { e.stopPropagation(); removeImage(idx) }}
                        className="absolute top-1 right-1 bg-black/60 text-white rounded-full p-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        <X className="w-3 h-3" />
                      </button>
                      {item.type === 'new' && (
                        <span className="absolute bottom-0 inset-x-0 bg-accent/80 text-white text-[10px] text-center py-0.5">New</span>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
            <label className="flex items-center justify-center gap-2 border-2 border-dashed border-gray-300 rounded-lg py-4 cursor-pointer hover:border-primary hover:bg-primary/5 transition-colors">
              <Upload className="w-4 h-4 text-gray-400" aria-hidden="true" />
              <span className="text-sm text-gray-500">{t('actions.uploadImages')}</span>
              <input type="file" multiple accept="image/*" onChange={handleFiles} className="hidden" aria-label={t('actions.uploadImages')} />
            </label>
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 border py-2.5 rounded-lg text-sm font-medium">{t('actions.cancel')}</button>
            <button type="submit" disabled={saving}
              className="flex-1 bg-primary hover:bg-primary-dark text-white py-2.5 rounded-lg text-sm font-semibold disabled:opacity-50">
              {saving ? t('actions.saving') : t('actions.save')}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
