import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { useEscapeKey } from '@/hooks/useEscapeKey'
import { hotelsApi } from '@/api/hotelsApi'
import { useAuth } from '@/hooks/useAuth'
import { toast } from 'sonner'
import Skeleton from '@/components/common/Skeleton'
import { formatCurrency, formatDate } from '@/utils/formatters'
import { CURRENCIES, DEFAULT_CURRENCY } from '@/utils/constants'
import { Link } from 'react-router-dom'
import {
  Plus, Search, Pencil, Trash2, Star, ChevronLeft, ChevronRight, X, Upload,
} from 'lucide-react'

export default function ManageHotels() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const { t } = useTranslation('admin')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)
  const ownerId = user?.role === 'admin' ? undefined : user?.id

  const { data, isLoading } = useQuery({
    queryKey: ['admin-hotels', page, search, user?.role, user?.id],
    queryFn: () => {
      const params = { page, per_page: 10, search: search || undefined }
      if (ownerId) params.owner_id = ownerId
      return hotelsApi.list(params)
    },
    select: (res) => res.data,
    enabled: !!user?.id,
  })

  const deleteMut = useMutation({
    mutationFn: (id) => hotelsApi.delete(id),
    onSuccess: () => { toast.success('Hotel deleted'); qc.invalidateQueries({ queryKey: ['admin-hotels'] }) },
    onError: () => toast.error('Failed to delete'),
  })

  const saveMut = useMutation({
    mutationFn: async ({ id, data, files, imageOrder }) => {
      const res = id ? await hotelsApi.update(id, data) : await hotelsApi.create(data)
      const hotelId = res.data?.id || id
      if (files?.length && hotelId) {
        const fd = new FormData()
        files.forEach((f) => fd.append('files', f))
        const uploadRes = await hotelsApi.uploadImages(hotelId, fd)
        const allUrls = uploadRes.data?.images || []
        const newUrls = allUrls.slice(-(files.length))
        let newIdx = 0
        const finalImages = imageOrder.map((item) =>
          item.type === 'existing' ? item.url : newUrls[newIdx++]
        )
        await hotelsApi.update(hotelId, { images: finalImages })
        return uploadRes
      }
      return res
    },
    onSuccess: () => { toast.success('Saved'); setModal(null); qc.invalidateQueries({ queryKey: ['admin-hotels'] }) },
    onError: (err) => {
      const detail = err.response?.data?.detail
      if (Array.isArray(detail)) {
        toast.error(detail.map((e) => e.msg).join(', '))
      } else {
        toast.error(typeof detail === 'string' ? detail : 'Failed to save')
      }
    },
  })

  const hotels = data?.items || []
  const meta = data?.meta || {}

  return (
    <>
      <Helmet><title>{t('dashboard.manageHotels')} — Admin</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
            <div>
              <Link to="/admin" className="text-sm text-primary hover:underline">{t('actions.backToDashboard')}</Link>
              <h1 className="font-heading text-2xl font-bold text-gray-900">{t('dashboard.manageHotels')}</h1>
            </div>
            <button onClick={() => setModal({ name: '', city: '', country: '', star_rating: 3, description: '' })}
              className="bg-primary hover:bg-primary-dark text-white font-semibold px-4 py-2 rounded-lg text-sm flex items-center gap-2">
              <Plus className="w-4 h-4" aria-hidden="true" /> {t('actions.addHotel')}
            </button>
          </div>

          <div className="bg-white rounded-xl border p-5">
            <div className="mb-4 relative max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" aria-hidden="true" />
              <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }}
                placeholder={t('filter.searchHotels')} aria-label={t('filter.searchHotels')}
                className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm" />
            </div>

            {isLoading ? (
              <div className="space-y-3">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-3 font-medium">{t('table.hotel')}</th>
                      <th className="pb-3 font-medium">{t('table.location')}</th>
                      <th className="pb-3 font-medium">{t('table.stars')}</th>
                      <th className="pb-3 font-medium">{t('table.from')}</th>
                      <th className="pb-3 font-medium">{t('table.rating')}</th>
                      <th className="pb-3 font-medium text-right">{t('table.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {hotels.map((h) => (
                      <tr key={h.id} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="py-3 font-medium">{h.name}</td>
                        <td className="py-3 text-gray-500">{h.city}, {h.country}</td>
                        <td className="py-3">
                          <div className="flex items-center gap-1">
                            <Star className="w-3.5 h-3.5 fill-warning text-warning" />{h.star_rating}
                          </div>
                        </td>
                        <td className="py-3">
                          {h.min_room_price != null ? formatCurrency(h.min_room_price, h.currency) : '—'}
                        </td>
                        <td className="py-3">{h.avg_rating?.toFixed(1) || '—'}</td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => setModal(h)} className="p-1.5 hover:bg-gray-100 rounded" aria-label="Edit hotel">
                              <Pencil className="w-4 h-4 text-gray-500" />
                            </button>
                            <button onClick={() => { if (confirm('Delete this hotel?')) deleteMut.mutate(h.id) }}
                              className="p-1.5 hover:bg-red-50 rounded" aria-label="Delete hotel">
                              <Trash2 className="w-4 h-4 text-error" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {hotels.length === 0 && (
                      <tr><td colSpan={6} className="py-12 text-center text-gray-400">{t('empty.noHotels')}</td></tr>
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
        <HotelModal hotel={modal} onClose={() => setModal(null)}
          onSave={(data, files, imageOrder) => saveMut.mutate({ id: modal.id, data, files, imageOrder })}
          saving={saveMut.isPending} />
      )}
    </>
  )
}

function slugify(text) {
  return text.toLowerCase().trim().replace(/[^\w\s-]/g, '').replace(/[\s_]+/g, '-').replace(/-+/g, '-')
}

function HotelModal({ hotel, onClose, onSave, saving }) {
  const { t } = useTranslation('admin')
  useEscapeKey(onClose)
  const [form, setForm] = useState({
    name: hotel.name || '',
    city: hotel.city || '',
    country: hotel.country || '',
    star_rating: hotel.star_rating || 3,
    currency: hotel.currency || DEFAULT_CURRENCY,
    description: hotel.description || '',
    address: hotel.address || '',
    property_type: hotel.property_type || 'hotel',
  })

  const [images, setImages] = useState(() =>
    (hotel.images || []).map((url) => ({ type: 'existing', url }))
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
    if (!hotel.id) payload.slug = slugify(form.name)
    payload.images = images.filter((img) => img.type === 'existing').map((img) => img.url)
    const newFiles = images.filter((img) => img.type === 'new').map((img) => img.file)
    const imageOrder = images.map((img) => ({ type: img.type, url: img.url }))
    onSave(payload, newFiles, imageOrder)
  }

  const modalTitle = hotel.id ? t('actions.editHotel') : t('actions.newHotel')

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="hotel-modal-title"
        className="bg-white rounded-xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 id="hotel-modal-title" className="font-heading font-bold text-lg">{modalTitle}</h2>
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
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.city')}</label>
              <input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} required
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.country')}</label>
              <input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} required
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.address')}</label>
            <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.starRating')}</label>
              <select value={form.star_rating} onChange={(e) => setForm({ ...form, star_rating: Number(e.target.value) })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm">
                {[1, 2, 3, 4, 5].map((s) => <option key={s} value={s}>{s} ★</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.propertyType')}</label>
              <select value={form.property_type} onChange={(e) => setForm({ ...form, property_type: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm">
                {['hotel', 'resort', 'apartment', 'villa', 'hostel'].map((pt) => (
                  <option key={pt} value={pt} className="capitalize">{pt}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.currency')}</label>
              <select value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm">
                {CURRENCIES.map((c) => (
                  <option key={c.code} value={c.code}>{c.symbol} {c.code} — {c.name}</option>
                ))}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.description')}</label>
            <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm resize-none h-20" />
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
