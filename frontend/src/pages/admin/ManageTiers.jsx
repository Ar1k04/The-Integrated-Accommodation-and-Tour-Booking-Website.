import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { useEscapeKey } from '@/hooks/useEscapeKey'
import { adminApi } from '@/api/adminApi'
import { toast } from 'sonner'
import Skeleton from '@/components/common/Skeleton'
import { Link } from 'react-router-dom'
import { Plus, Pencil, Trash2, X, Award, RefreshCw } from 'lucide-react'

export default function ManageTiers() {
  const qc = useQueryClient()
  const { t } = useTranslation('admin')
  const [modal, setModal] = useState(null) // tier object | 'new' | null

  const { data, isLoading } = useQuery({
    queryKey: ['admin-tiers'],
    queryFn: () => adminApi.listTiers(),
    select: (res) => res.data,
  })

  const invalidate = () => qc.invalidateQueries({ queryKey: ['admin-tiers'] })

  const saveMut = useMutation({
    mutationFn: ({ id, body }) => (id ? adminApi.updateTier(id, body) : adminApi.createTier(body)),
    onSuccess: () => { toast.success(t('tiers.saved')); setModal(null); invalidate() },
    onError: (err) => toast.error(err.response?.data?.detail || t('tiers.saveFailed')),
  })
  const deleteMut = useMutation({
    mutationFn: (id) => adminApi.deleteTier(id),
    onSuccess: () => { toast.success(t('tiers.deleted')); invalidate() },
    onError: () => toast.error(t('tiers.deleteFailed')),
  })
  const recomputeMut = useMutation({
    mutationFn: () => adminApi.recomputeTiers(),
    onSuccess: (res) => { toast.success(t('tiers.recomputed', { count: res.data?.data?.recomputed ?? 0 })); invalidate() },
    onError: () => toast.error(t('tiers.recomputeFailed')),
  })

  const tiers = data || []

  return (
    <>
      <Helmet><title>{t('tiers.title')} — Admin</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-5xl mx-auto px-4 py-8">
          <div className="mb-6 flex items-start justify-between gap-4">
            <div>
              <Link to="/admin" className="text-sm text-primary hover:underline">{t('actions.backToDashboard')}</Link>
              <h1 className="font-heading text-2xl font-bold text-gray-900 flex items-center gap-2">
                <Award className="w-6 h-6 text-primary" /> {t('tiers.title')}
              </h1>
              <p className="text-sm text-gray-500 mt-1">{t('tiers.subtitle')}</p>
            </div>
            <div className="flex gap-2 shrink-0">
              <button onClick={() => recomputeMut.mutate()} disabled={recomputeMut.isPending}
                className="inline-flex items-center gap-1.5 border px-3 py-2 rounded-lg text-sm font-medium hover:bg-gray-50 disabled:opacity-50">
                <RefreshCw className="w-4 h-4" /> {t('tiers.recompute')}
              </button>
              <button onClick={() => setModal('new')}
                className="inline-flex items-center gap-1.5 bg-primary hover:bg-primary-dark text-white px-3 py-2 rounded-lg text-sm font-semibold">
                <Plus className="w-4 h-4" /> {t('tiers.add')}
              </button>
            </div>
          </div>

          <div className="bg-white rounded-xl border p-5">
            {isLoading ? (
              <div className="space-y-3">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-3 font-medium">{t('tiers.name')}</th>
                      <th className="pb-3 font-medium">{t('tiers.minPoints')}</th>
                      <th className="pb-3 font-medium">{t('tiers.maxPoints')}</th>
                      <th className="pb-3 font-medium">{t('tiers.discount')}</th>
                      <th className="pb-3 font-medium">{t('tiers.benefits')}</th>
                      <th className="pb-3 font-medium text-right">{t('table.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tiers.map((tier) => (
                      <tr key={tier.id} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="py-3 font-medium">{tier.name}</td>
                        <td className="py-3">{tier.min_points}</td>
                        <td className="py-3">{tier.max_points || '—'}</td>
                        <td className="py-3">{tier.discount_percent}%</td>
                        <td className="py-3 text-gray-500 max-w-xs truncate">{tier.benefits || '—'}</td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => setModal(tier)} className="p-1.5 hover:bg-gray-100 rounded" aria-label={t('actions.edit')}>
                              <Pencil className="w-4 h-4 text-gray-500" />
                            </button>
                            <button onClick={() => { if (confirm(t('tiers.confirmDelete'))) deleteMut.mutate(tier.id) }}
                              className="p-1.5 hover:bg-red-50 rounded" aria-label={t('actions.delete')}>
                              <Trash2 className="w-4 h-4 text-error" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {tiers.length === 0 && (
                      <tr><td colSpan={6} className="py-12 text-center text-gray-400">{t('tiers.empty')}</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {modal && (
        <TierModal tier={modal === 'new' ? null : modal} onClose={() => setModal(null)}
          onSave={(body) => saveMut.mutate({ id: modal === 'new' ? null : modal.id, body })}
          saving={saveMut.isPending} />
      )}
    </>
  )
}

function TierModal({ tier, onClose, onSave, saving }) {
  const { t } = useTranslation('admin')
  useEscapeKey(onClose)
  const [form, setForm] = useState({
    name: tier?.name || '',
    min_points: tier?.min_points ?? 0,
    max_points: tier?.max_points ?? 0,
    discount_percent: tier?.discount_percent ?? 0,
    benefits: tier?.benefits || '',
  })

  const submit = (e) => {
    e.preventDefault()
    if (!form.name.trim()) { toast.error(t('tiers.nameRequired')); return }
    onSave({
      name: form.name.trim(),
      min_points: Number(form.min_points) || 0,
      max_points: Number(form.max_points) || 0,
      discount_percent: Number(form.discount_percent) || 0,
      benefits: form.benefits.trim() || null,
    })
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="tier-modal-title"
        className="bg-white rounded-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 id="tier-modal-title" className="font-heading font-bold text-lg">
            {tier ? t('tiers.editTitle') : t('tiers.addTitle')}
          </h2>
          <button onClick={onClose} aria-label={t('actions.cancel')}><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('tiers.name')}</label>
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm" placeholder="Gold" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('tiers.minPoints')}</label>
              <input type="number" min="0" value={form.min_points} onChange={(e) => setForm({ ...form, min_points: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('tiers.maxPoints')}</label>
              <input type="number" min="0" value={form.max_points} onChange={(e) => setForm({ ...form, max_points: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm" />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('tiers.discount')} (%)</label>
            <input type="number" min="0" max="100" step="0.5" value={form.discount_percent}
              onChange={(e) => setForm({ ...form, discount_percent: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('tiers.benefits')}</label>
            <textarea value={form.benefits} onChange={(e) => setForm({ ...form, benefits: e.target.value })}
              rows={2} className="w-full border rounded-lg px-4 py-2.5 text-sm" />
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
