import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { useEscapeKey } from '@/hooks/useEscapeKey'
import { toursApi } from '@/api/toursApi'
import { useAuth } from '@/hooks/useAuth'
import { toast } from 'sonner'
import Skeleton from '@/components/common/Skeleton'
import { formatCurrency } from '@/utils/formatters'
import { Link } from 'react-router-dom'
import { TOUR_CATEGORIES, PARTNER_TOUR_FLAGS } from '@/utils/constants'
import {
  Plus, Search, Pencil, Trash2, ChevronLeft, ChevronRight, X, Clock, Upload,
} from 'lucide-react'

export default function ManageTours() {
  const qc = useQueryClient()
  const { user } = useAuth()
  const { t } = useTranslation('admin')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)
  const ownerId = user?.role === 'admin' ? undefined : user?.id

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
    mutationFn: async ({ id, data, files, imageOrder }) => {
      const res = id ? await toursApi.update(id, data) : await toursApi.create(data)
      const tourId = res.data?.id || id
      if (files?.length && tourId) {
        const fd = new FormData()
        files.forEach((f) => fd.append('files', f))
        const uploadRes = await toursApi.uploadImages(tourId, fd)
        const allUrls = uploadRes.data?.images || []
        const newUrls = allUrls.slice(-(files.length))
        let newIdx = 0
        const finalImages = imageOrder.map((item) =>
          item.type === 'existing' ? item.url : newUrls[newIdx++]
        )
        await toursApi.update(tourId, { images: finalImages })
        return uploadRes
      }
      return res
    },
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
      <Helmet><title>{t('dashboard.manageTours')} — Admin</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
            <div>
              <Link to="/admin" className="text-sm text-primary hover:underline">{t('actions.backToDashboard')}</Link>
              <h1 className="font-heading text-2xl font-bold text-gray-900">{t('dashboard.manageTours')}</h1>
            </div>
            <button onClick={() => setModal({})}
              className="bg-primary hover:bg-primary-dark text-white font-semibold px-4 py-2 rounded-lg text-sm flex items-center gap-2">
              <Plus className="w-4 h-4" aria-hidden="true" /> {t('actions.addTour')}
            </button>
          </div>

          <div className="bg-white rounded-xl border p-5">
            <div className="mb-4 relative max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" aria-hidden="true" />
              <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }}
                placeholder={t('filter.searchTours')} aria-label={t('filter.searchTours')}
                className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm" />
            </div>

            {isLoading ? (
              <div className="space-y-3">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-3 font-medium">{t('table.tourName')}</th>
                      <th className="pb-3 font-medium">{t('table.location')}</th>
                      <th className="pb-3 font-medium">{t('table.category')}</th>
                      <th className="pb-3 font-medium">{t('table.duration')}</th>
                      <th className="pb-3 font-medium">{t('table.pricePerPerson')}</th>
                      <th className="pb-3 font-medium text-right">{t('table.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tours.map((tr) => (
                      <tr key={tr.id} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="py-3 font-medium">{tr.name}</td>
                        <td className="py-3 text-gray-500">{tr.city}, {tr.country}</td>
                        <td className="py-3 capitalize">{tr.category}</td>
                        <td className="py-3 flex items-center gap-1"><Clock className="w-3.5 h-3.5" />{tr.duration_days}d</td>
                        <td className="py-3">{formatCurrency(tr.price_per_person)}</td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => setModal(tr)} className="p-1.5 hover:bg-gray-100 rounded" aria-label="Edit tour">
                              <Pencil className="w-4 h-4 text-gray-500" />
                            </button>
                            <button onClick={() => { if (confirm('Delete this tour?')) deleteMut.mutate(tr.id) }}
                              className="p-1.5 hover:bg-red-50 rounded" aria-label="Delete tour">
                              <Trash2 className="w-4 h-4 text-error" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {tours.length === 0 && (
                      <tr><td colSpan={6} className="py-12 text-center text-gray-400">{t('empty.noTours')}</td></tr>
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
        <TourModal tour={modal} onClose={() => setModal(null)}
          onSave={(data, files, imageOrder) => saveMut.mutate({ id: modal.id, data, files, imageOrder })}
          saving={saveMut.isPending} />
      )}
    </>
  )
}

// ── Repeatable simple-string list (highlights / includes / excludes / images) ──
function StringListEditor({ label, items, onChange, placeholder, addLabel }) {
  const rows = items.length ? items : ['']
  const update = (i, v) => { const next = [...rows]; next[i] = v; onChange(next) }
  const remove = (i) => onChange(rows.filter((_, idx) => idx !== i))
  const add = () => onChange([...rows, ''])
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <div className="space-y-2">
        {rows.map((val, i) => (
          <div key={i} className="flex gap-2">
            <input value={val} onChange={(e) => update(i, e.target.value)} placeholder={placeholder}
              className="flex-1 border rounded-lg px-3 py-2 text-sm" />
            <button type="button" onClick={() => remove(i)} className="p-2 text-gray-400 hover:text-error" aria-label="Remove">
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
      <button type="button" onClick={add} className="mt-2 text-sm text-primary hover:underline flex items-center gap-1">
        <Plus className="w-3.5 h-3.5" /> {addLabel}
      </button>
    </div>
  )
}

// ── Itinerary editor ({title, description} rows) ───────────────────────────────
function ItineraryEditor({ items, onChange, t }) {
  const rows = items
  const update = (i, key, v) => { const next = rows.map((r, idx) => idx === i ? { ...r, [key]: v } : r); onChange(next) }
  const remove = (i) => onChange(rows.filter((_, idx) => idx !== i))
  const add = () => onChange([...rows, { title: '', description: '' }])
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.itinerary')}</label>
      <div className="space-y-3">
        {rows.map((day, i) => (
          <div key={i} className="border rounded-lg p-3 space-y-2 bg-gray-50">
            <div className="flex items-center gap-2">
              <span className="bg-primary text-white text-xs font-bold w-6 h-6 rounded-full flex items-center justify-center shrink-0">{i + 1}</span>
              <input value={day.title || ''} onChange={(e) => update(i, 'title', e.target.value)} placeholder={t('form.dayTitle')}
                className="flex-1 border rounded-lg px-3 py-2 text-sm" />
              <button type="button" onClick={() => remove(i)} className="p-1.5 text-gray-400 hover:text-error" aria-label="Remove day">
                <X className="w-4 h-4" />
              </button>
            </div>
            <textarea value={day.description || ''} onChange={(e) => update(i, 'description', e.target.value)} placeholder={t('form.dayDescription')}
              className="w-full border rounded-lg px-3 py-2 text-sm resize-none h-16" />
          </div>
        ))}
      </div>
      <button type="button" onClick={add} className="mt-2 text-sm text-primary hover:underline flex items-center gap-1">
        <Plus className="w-3.5 h-3.5" /> {t('actions.addDay')}
      </button>
    </div>
  )
}

// Standard Viator age-band names — picked from a dropdown (no free typing).
const AGE_BAND_NAMES = ['ADULT', 'YOUTH', 'CHILD', 'INFANT', 'SENIOR']

// ── Age-band + pricing editor (mirrors Viator pricingInfo.ageBands; ADULT req.) ─
function AgeBandEditor({ bands, onChange, t }) {
  const update = (i, key, v) => { const next = bands.map((b, idx) => idx === i ? { ...b, [key]: v } : b); onChange(next) }
  const remove = (i) => onChange(bands.filter((_, idx) => idx !== i))
  const add = () => onChange([...bands, { age_band: 'CHILD', start_age: 0, end_age: 17, price: '' }])
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.ageBands')}</label>
      <p className="text-xs text-gray-500 mb-2">{t('form.ageBandHelp')}</p>
      <div className="space-y-2">
        <div className="grid grid-cols-[1fr_70px_70px_90px_32px] gap-2 text-xs text-gray-400 px-1">
          <span>{t('form.bandName')}</span><span>{t('form.startAge')}</span><span>{t('form.endAge')}</span><span>{t('form.bandPrice')}</span><span />
        </div>
        {bands.map((b, i) => {
          const isAdult = String(b.age_band || '').toUpperCase() === 'ADULT'
          return (
            <div key={i} className="grid grid-cols-[1fr_70px_70px_90px_32px] gap-2 items-center">
              <select value={b.age_band || ''} onChange={(e) => update(i, 'age_band', e.target.value)} disabled={isAdult}
                className="border rounded-lg px-2 py-2 text-sm bg-white disabled:bg-gray-100 disabled:text-gray-500">
                {AGE_BAND_NAMES.map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
              <input type="number" min={0} max={120} value={b.start_age} onChange={(e) => update(i, 'start_age', e.target.value)}
                className="border rounded-lg px-2 py-2 text-sm" />
              <input type="number" min={0} max={120} value={b.end_age} onChange={(e) => update(i, 'end_age', e.target.value)}
                className="border rounded-lg px-2 py-2 text-sm" />
              <input type="number" min={0} step="0.01" value={b.price} onChange={(e) => update(i, 'price', e.target.value)} placeholder="0.00"
                className="border rounded-lg px-2 py-2 text-sm" />
              <button type="button" onClick={() => remove(i)} disabled={isAdult}
                className="p-1.5 text-gray-400 hover:text-error disabled:opacity-20 disabled:cursor-not-allowed" aria-label="Remove band">
                <X className="w-4 h-4" />
              </button>
            </div>
          )
        })}
      </div>
      <button type="button" onClick={add} className="mt-2 text-sm text-primary hover:underline flex items-center gap-1">
        <Plus className="w-3.5 h-3.5" /> {t('actions.addBand')}
      </button>
    </div>
  )
}

const DEFAULT_BANDS = [{ age_band: 'ADULT', start_age: 18, end_age: 99, price: '' }]

function TourModal({ tour, onClose, onSave, saving }) {
  const { t } = useTranslation('admin')
  useEscapeKey(onClose)
  const [form, setForm] = useState({
    name: tour.name || '',
    city: tour.city || '',
    country: tour.country || '',
    category: tour.category || TOUR_CATEGORIES[0],
    duration_days: tour.duration_days || 1,
    // Run-time split into hours + minutes for the form; recombined on save.
    duration_hours: Math.floor((tour.duration_minutes || 0) / 60),
    duration_mins: (tour.duration_minutes || 0) % 60,
    max_participants: tour.max_participants || 20,
    description: tour.description || '',
    flags: tour.flags || [],
    highlights: tour.highlights || [],
    itinerary: tour.itinerary || [],
    includes: tour.includes || [],
    excludes: tour.excludes || [],
    age_bands: (tour.age_bands && tour.age_bands.length)
      ? tour.age_bands.map((b) => ({
          age_band: b.age_band, start_age: b.start_age, end_age: b.end_age,
          price: b.price ?? '',
        }))
      : DEFAULT_BANDS,
  })

  // Images: hotel-style manager — existing URLs + newly-picked files (uploaded
  // to Cloudinary on save). First item = thumbnail.
  const [images, setImages] = useState(() =>
    (tour.images || []).map((url) => ({ type: 'existing', url }))
  )
  const [dragActive, setDragActive] = useState(false)

  const addFiles = (fileList) => {
    const selected = Array.from(fileList || []).filter((f) => f.type.startsWith('image/'))
    const newItems = selected.map((f) => ({ type: 'new', file: f, preview: URL.createObjectURL(f) }))
    setImages((prev) => [...prev, ...newItems])
  }
  const handleFiles = (e) => { addFiles(e.target.files); e.target.value = '' }
  const handleDrop = (e) => { e.preventDefault(); setDragActive(false); addFiles(e.dataTransfer.files) }
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

  const modalTitle = tour.id ? t('actions.editTour') : t('actions.newTour')

  const set = (patch) => setForm((f) => ({ ...f, ...patch }))

  const handleSubmit = (e) => {
    e.preventDefault()
    const cleanStrings = (arr) => arr.map((s) => (s || '').trim()).filter(Boolean)
    const bands = form.age_bands.map((b) => ({
      age_band: String(b.age_band || '').trim().toUpperCase(),
      start_age: Number(b.start_age) || 0,
      end_age: Number(b.end_age) || 0,
      price: Number(b.price) || 0,
    }))
    const adult = bands.find((b) => b.age_band === 'ADULT')
    if (!adult || adult.price <= 0) {
      toast.error(t('form.adultBandRequired'))
      return
    }
    for (const b of bands) {
      if (b.start_age > b.end_age) { toast.error(t('form.ageRangeInvalid', { band: b.age_band })); return }
    }
    const durationMinutes =
      (Number(form.duration_hours) || 0) * 60 + (Number(form.duration_mins) || 0)
    const payload = {
      name: form.name,
      city: form.city,
      country: form.country,
      category: form.category,
      duration_days: Number(form.duration_days),
      duration_minutes: durationMinutes > 0 ? durationMinutes : undefined,
      max_participants: Number(form.max_participants),
      price_per_person: adult.price, // canonical base = ADULT band price
      description: form.description || undefined,
      flags: form.flags,
      highlights: cleanStrings(form.highlights),
      itinerary: form.itinerary
        .filter((d) => (d.title || '').trim() || (d.description || '').trim())
        .map((d) => ({ title: (d.title || '').trim(), description: (d.description || '').trim() })),
      includes: cleanStrings(form.includes),
      excludes: cleanStrings(form.excludes),
      images: images.filter((img) => img.type === 'existing').map((img) => img.url),
      age_bands: bands,
    }
    const newFiles = images.filter((img) => img.type === 'new').map((img) => img.file)
    const imageOrder = images.map((img) => ({ type: img.type, url: img.url }))
    onSave(payload, newFiles, imageOrder)
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="tour-modal-title"
        className="bg-white rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 id="tour-modal-title" className="font-heading font-bold text-lg">{modalTitle}</h2>
          <button onClick={onClose} aria-label={t('actions.cancel')}><X className="w-5 h-5" aria-hidden="true" /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.name')}</label>
            <input value={form.name} onChange={(e) => set({ name: e.target.value })} required
              className="w-full border rounded-lg px-4 py-2.5 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.city')}</label>
              <input value={form.city} onChange={(e) => set({ city: e.target.value })} required
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.country')}</label>
              <input value={form.country} onChange={(e) => set({ country: e.target.value })} required
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.tourType')}</label>
              <select value={form.category} onChange={(e) => set({ category: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm">
                {TOUR_CATEGORIES.map((c) => <option key={c} value={c} className="capitalize">{c}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.durationDays')}</label>
              <input type="number" min={1} value={form.duration_days} onChange={(e) => set({ duration_days: Number(e.target.value) })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.maxParticipants')}</label>
              <input type="number" min={1} value={form.max_participants} onChange={(e) => set({ max_participants: Number(e.target.value) })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.duration')}</label>
            <p className="text-xs text-gray-500 mb-2">{t('form.durationHint')}</p>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2">
                <input type="number" min={0} value={form.duration_hours}
                  onChange={(e) => set({ duration_hours: Math.max(0, Number(e.target.value)) })}
                  className="w-20 border rounded-lg px-3 py-2.5 text-sm" />
                <span className="text-sm text-gray-600">{t('form.hours')}</span>
              </div>
              <div className="flex items-center gap-2">
                <input type="number" min={0} max={59} value={form.duration_mins}
                  onChange={(e) => set({ duration_mins: Math.min(59, Math.max(0, Number(e.target.value))) })}
                  className="w-20 border rounded-lg px-3 py-2.5 text-sm" />
                <span className="text-sm text-gray-600">{t('form.minutes')}</span>
              </div>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.features')}</label>
            <p className="text-xs text-gray-500 mb-2">{t('form.featuresHint')}</p>
            <div className="grid grid-cols-2 gap-2">
              {PARTNER_TOUR_FLAGS.map((flag) => {
                const active = (form.flags || []).includes(flag)
                return (
                  <label key={flag} className="flex items-center gap-2 cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={active}
                      onChange={() =>
                        set({
                          flags: active
                            ? form.flags.filter((f) => f !== flag)
                            : [...(form.flags || []), flag],
                        })
                      }
                      className="rounded border-gray-300"
                    />
                    {t(`form.flag_${flag}`)}
                  </label>
                )
              })}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.description')}</label>
            <textarea value={form.description} onChange={(e) => set({ description: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm resize-none h-20" />
          </div>

          <hr />
          <AgeBandEditor bands={form.age_bands} onChange={(v) => set({ age_bands: v })} t={t} />

          <hr />
          <StringListEditor label={t('form.highlights')} items={form.highlights} onChange={(v) => set({ highlights: v })}
            placeholder={t('form.highlightPlaceholder')} addLabel={t('actions.addHighlight')} />
          <ItineraryEditor items={form.itinerary} onChange={(v) => set({ itinerary: v })} t={t} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <StringListEditor label={t('form.includes')} items={form.includes} onChange={(v) => set({ includes: v })}
              placeholder={t('form.includePlaceholder')} addLabel={t('actions.addItem')} />
            <StringListEditor label={t('form.excludes')} items={form.excludes} onChange={(v) => set({ excludes: v })}
              placeholder={t('form.excludePlaceholder')} addLabel={t('actions.addItem')} />
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
            <label
              onDragOver={(e) => { e.preventDefault(); setDragActive(true) }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
              className={`flex flex-col items-center justify-center gap-1 border-2 border-dashed rounded-lg py-6 cursor-pointer transition-colors ${dragActive ? 'border-primary bg-primary/5' : 'border-gray-300 hover:border-primary hover:bg-primary/5'}`}>
              <Upload className="w-5 h-5 text-gray-400" aria-hidden="true" />
              <span className="text-sm text-gray-500">{t('form.dropImages')}</span>
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
