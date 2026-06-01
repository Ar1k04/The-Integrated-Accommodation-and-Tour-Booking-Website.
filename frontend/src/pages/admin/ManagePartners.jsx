import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { adminApi } from '@/api/adminApi'
import { toast } from 'sonner'
import Skeleton from '@/components/common/Skeleton'
import { formatDate } from '@/utils/formatters'
import { Link } from 'react-router-dom'
import { Check, Ban, ChevronLeft, ChevronRight, UserCheck } from 'lucide-react'

const STATUS_TABS = ['pending', 'approved', 'rejected']
const STATUS_STYLES = {
  pending: 'bg-amber-100 text-amber-700',
  approved: 'bg-emerald-100 text-emerald-700',
  rejected: 'bg-red-100 text-red-700',
}

export default function ManagePartners() {
  const qc = useQueryClient()
  const { t } = useTranslation('admin')
  const [status, setStatus] = useState('pending')
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ['admin-partners', status, page],
    queryFn: () => adminApi.listPartners({ status, page, per_page: 10 }),
    select: (res) => res.data,
  })

  const statusMut = useMutation({
    mutationFn: ({ id, partner_status }) => adminApi.updatePartnerStatus(id, partner_status),
    onSuccess: (_res, vars) => {
      toast.success(vars.partner_status === 'approved' ? t('partners.approved') : t('partners.rejected'))
      qc.invalidateQueries({ queryKey: ['admin-partners'] })
    },
    onError: () => toast.error(t('partners.actionFailed')),
  })

  const partners = data?.items || []
  const meta = data?.meta || {}

  return (
    <>
      <Helmet><title>{t('partners.title')} — Admin</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="mb-6">
            <Link to="/admin" className="text-sm text-primary hover:underline">{t('actions.backToDashboard')}</Link>
            <h1 className="font-heading text-2xl font-bold text-gray-900 flex items-center gap-2">
              <UserCheck className="w-6 h-6 text-primary" /> {t('partners.title')}
            </h1>
            <p className="text-sm text-gray-500 mt-1">{t('partners.subtitle')}</p>
          </div>

          <div className="bg-white rounded-xl border p-5">
            <div className="flex gap-2 mb-4 border-b">
              {STATUS_TABS.map((s) => (
                <button key={s} onClick={() => { setStatus(s); setPage(1) }}
                  className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                    status === s ? 'border-primary text-primary' : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}>
                  {t(`partners.status.${s}`)}
                </button>
              ))}
            </div>

            {isLoading ? (
              <div className="space-y-3">{Array.from({ length: 5 }, (_, i) => <Skeleton key={i} className="h-12 rounded-lg" />)}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 border-b">
                      <th className="pb-3 font-medium">{t('table.name')}</th>
                      <th className="pb-3 font-medium">{t('table.email')}</th>
                      <th className="pb-3 font-medium">{t('table.status')}</th>
                      <th className="pb-3 font-medium">{t('table.joined')}</th>
                      <th className="pb-3 font-medium text-right">{t('table.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {partners.map((p) => (
                      <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 text-xs font-bold flex items-center justify-center">
                              {p.full_name?.[0]?.toUpperCase() || 'P'}
                            </div>
                            <span className="font-medium">{p.full_name}</span>
                          </div>
                        </td>
                        <td className="py-3 text-gray-500">{p.email}</td>
                        <td className="py-3">
                          <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[p.partner_status] || 'bg-gray-100 text-gray-600'}`}>
                            {t(`partners.status.${p.partner_status || 'pending'}`)}
                          </span>
                        </td>
                        <td className="py-3 text-gray-500">{formatDate(p.created_at)}</td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            {p.partner_status !== 'approved' && (
                              <button onClick={() => statusMut.mutate({ id: p.id, partner_status: 'approved' })}
                                disabled={statusMut.isPending}
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50">
                                <Check className="w-3.5 h-3.5" /> {t('partners.approve')}
                              </button>
                            )}
                            {p.partner_status !== 'rejected' && (
                              <button onClick={() => statusMut.mutate({ id: p.id, partner_status: 'rejected' })}
                                disabled={statusMut.isPending}
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-red-200 text-error hover:bg-red-50 disabled:opacity-50">
                                <Ban className="w-3.5 h-3.5" /> {t('partners.reject')}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                    {partners.length === 0 && (
                      <tr><td colSpan={5} className="py-12 text-center text-gray-400">{t('partners.empty')}</td></tr>
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
