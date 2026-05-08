import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { useEscapeKey } from '@/hooks/useEscapeKey'
import { adminApi } from '@/api/adminApi'
import { toast } from 'sonner'
import Skeleton from '@/components/common/Skeleton'
import { formatDate } from '@/utils/formatters'
import { Link } from 'react-router-dom'
import {
  Search, Pencil, Trash2, ChevronLeft, ChevronRight, X, Shield, ShieldOff,
} from 'lucide-react'

export default function ManageUsers() {
  const qc = useQueryClient()
  const { t } = useTranslation('admin')
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(null)

  const { data, isLoading } = useQuery({
    queryKey: ['admin-users', page, search],
    queryFn: () => adminApi.listUsers({ page, per_page: 10, q: search || undefined }),
    select: (res) => res.data,
  })

  const deleteMut = useMutation({
    mutationFn: (id) => adminApi.deleteUser(id),
    onSuccess: () => { toast.success('User deleted'); qc.invalidateQueries({ queryKey: ['admin-users'] }) },
    onError: () => toast.error('Failed to delete'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => adminApi.updateUser(id, data),
    onSuccess: () => { toast.success('User updated'); setModal(null); qc.invalidateQueries({ queryKey: ['admin-users'] }) },
    onError: (err) => toast.error(err.response?.data?.detail || 'Failed to update'),
  })

  const users = data?.items || []
  const meta = data?.meta || {}

  return (
    <>
      <Helmet><title>{t('dashboard.manageUsers')} — Admin</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-8">
          <div className="mb-6">
            <Link to="/admin" className="text-sm text-primary hover:underline">{t('actions.backToDashboard')}</Link>
            <h1 className="font-heading text-2xl font-bold text-gray-900">{t('dashboard.manageUsers')}</h1>
          </div>

          <div className="bg-white rounded-xl border p-5">
            <div className="mb-4 relative max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" aria-hidden="true" />
              <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }}
                placeholder={t('filter.searchUsers')} aria-label={t('filter.searchUsers')}
                className="w-full pl-10 pr-4 py-2 border rounded-lg text-sm" />
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
                      <th className="pb-3 font-medium">{t('table.role')}</th>
                      <th className="pb-3 font-medium">{t('table.points')}</th>
                      <th className="pb-3 font-medium">{t('table.joined')}</th>
                      <th className="pb-3 font-medium text-right">{t('table.actions')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map((u) => (
                      <tr key={u.id} className="border-b last:border-0 hover:bg-gray-50">
                        <td className="py-3">
                          <div className="flex items-center gap-2">
                            <div className="w-8 h-8 rounded-full bg-primary/10 text-primary text-xs font-bold flex items-center justify-center">
                              {u.full_name?.[0]?.toUpperCase() || 'U'}
                            </div>
                            <span className="font-medium">{u.full_name}</span>
                          </div>
                        </td>
                        <td className="py-3 text-gray-500">{u.email}</td>
                        <td className="py-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                            u.role === 'admin' ? 'bg-purple-100 text-purple-700' :
                            u.role === 'partner' ? 'bg-blue-100 text-blue-700' :
                            'bg-gray-100 text-gray-600'
                          }`}>
                            {u.role !== 'user' ? <Shield className="w-3 h-3" /> : <ShieldOff className="w-3 h-3" />}
                            {u.role}
                          </span>
                        </td>
                        <td className="py-3">{u.loyalty_points || 0}</td>
                        <td className="py-3 text-gray-500">{formatDate(u.created_at)}</td>
                        <td className="py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => setModal(u)} className="p-1.5 hover:bg-gray-100 rounded" aria-label="Edit user">
                              <Pencil className="w-4 h-4 text-gray-500" />
                            </button>
                            <button onClick={() => { if (confirm('Delete this user?')) deleteMut.mutate(u.id) }}
                              className="p-1.5 hover:bg-red-50 rounded" aria-label="Delete user">
                              <Trash2 className="w-4 h-4 text-error" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {users.length === 0 && (
                      <tr><td colSpan={6} className="py-12 text-center text-gray-400">{t('empty.noUsers')}</td></tr>
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
        <UserModal user={modal} onClose={() => setModal(null)}
          onSave={(data) => updateMut.mutate({ id: modal.id, data })} saving={updateMut.isPending} />
      )}
    </>
  )
}

function UserModal({ user, onClose, onSave, saving }) {
  const { t } = useTranslation('admin')
  useEscapeKey(onClose)
  const [form, setForm] = useState({
    full_name: user.full_name || '',
    email: user.email || '',
    role: user.role || 'user',
    is_active: user.is_active !== false,
  })

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="user-modal-title"
        className="bg-white rounded-xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 id="user-modal-title" className="font-heading font-bold text-lg">{t('actions.editUser')}</h2>
          <button onClick={onClose} aria-label={t('actions.cancel')}><X className="w-5 h-5" aria-hidden="true" /></button>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); onSave(form) }} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.fullName')}</label>
            <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.email')}</label>
            <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.role')}</label>
              <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm">
                <option value="user">User</option>
                <option value="partner">Partner</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">{t('form.status')}</label>
              <select value={form.is_active ? 'active' : 'inactive'}
                onChange={(e) => setForm({ ...form, is_active: e.target.value === 'active' })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm">
                <option value="active">{t('status.active')}</option>
                <option value="inactive">{t('status.inactive')}</option>
              </select>
            </div>
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
