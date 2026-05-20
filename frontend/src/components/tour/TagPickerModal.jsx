import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { X, Search } from 'lucide-react'
import { toursApi } from '@/api/toursApi'
import { getViatorTagLabel } from '@/utils/viatorTags'

export default function TagPickerModal({ open, selectedTagIds, onApply, onClose }) {
  const { t, i18n } = useTranslation(['tours', 'common'])
  const [draft, setDraft] = useState(selectedTagIds || [])
  const [search, setSearch] = useState('')
  // Reset draft when the modal transitions from closed → open. Render-phase
  // setState (React 19 pattern) avoids effect-driven cascading renders.
  const [wasOpen, setWasOpen] = useState(open)
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) setDraft(selectedTagIds || [])
  }

  const { data, isLoading } = useQuery({
    queryKey: ['viator-tags'],
    queryFn: () => toursApi.getViatorTags().then((r) => r.data?.tags || []),
    staleTime: Infinity,
    enabled: open,
  })

  const tags = useMemo(() => data || [], [data])
  const tagById = useMemo(() => {
    const m = new Map()
    for (const t of tags) m.set(t.tag_id, t)
    return m
  }, [tags])

  // Group children under parent_tag_id; tags without a known parent become top-level.
  const grouped = useMemo(() => {
    const top = []
    const childrenOf = new Map()
    for (const t of tags) {
      if (t.parent_tag_id && tagById.has(t.parent_tag_id)) {
        const arr = childrenOf.get(t.parent_tag_id) || []
        arr.push(t)
        childrenOf.set(t.parent_tag_id, arr)
      } else {
        top.push(t)
      }
    }
    return { top, childrenOf }
  }, [tags, tagById])

  const visibleGroups = useMemo(() => {
    const q = search.trim().toLowerCase()
    const matches = (tag) => {
      if (!q) return true
      const localizedName = getViatorTagLabel(tag, t, i18n.language).toLowerCase()
      return localizedName.includes(q) || String(tag.name || '').toLowerCase().includes(q)
    }
    return grouped.top
      .map((parent) => {
        const children = grouped.childrenOf.get(parent.tag_id) || []
        const matched = children.filter(matches)
        const parentMatches = matches(parent)
        if (!parentMatches && matched.length === 0) return null
        return { parent, children: q ? matched : children, parentMatches }
      })
      .filter(Boolean)
  }, [grouped, search, t, i18n.language])

  const toggle = (id) => {
    setDraft((curr) => (curr.includes(id) ? curr.filter((x) => x !== id) : [...curr, id]))
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-4 border-b">
          <h3 className="font-heading font-bold text-lg">{t('tours:page.filters.tourType')}</h3>
          <button onClick={onClose} aria-label={t('common:common.close', 'Close')}>
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        <div className="p-4 border-b">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t('tours:page.filters.searchTags')}
              className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {isLoading && (
            <div className="text-center text-sm text-gray-400 py-8">{t('common:common.loading')}</div>
          )}
          {!isLoading && visibleGroups.length === 0 && (
            <div className="text-center text-sm text-gray-400 py-8">{t('tours:page.noResults')}</div>
          )}
          {visibleGroups.map(({ parent, children }) => (
            <div key={parent.tag_id}>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={draft.includes(parent.tag_id)}
                  onChange={() => toggle(parent.tag_id)}
                  className="rounded border-gray-300"
                />
                <span className="font-semibold text-sm text-gray-900">{getViatorTagLabel(parent, t, i18n.language)}</span>
              </label>
              {children.length > 0 && (
                <div className="mt-2 ml-6 grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                  {children.map((child) => (
                    <label key={child.tag_id} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={draft.includes(child.tag_id)}
                        onChange={() => toggle(child.tag_id)}
                        className="rounded border-gray-300"
                      />
                      <span className="text-sm text-gray-700">{getViatorTagLabel(child, t, i18n.language)}</span>
                    </label>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between p-4 border-t bg-gray-50 rounded-b-2xl">
          <button
            onClick={() => setDraft([])}
            className="text-sm text-gray-500 hover:text-gray-700"
          >
            {t('common:common.clearFilters')}
          </button>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium rounded-lg border hover:bg-gray-50"
            >
              {t('common:common.cancel', 'Cancel')}
            </button>
            <button
              onClick={() => { onApply(draft); onClose() }}
              className="px-4 py-2 text-sm font-semibold rounded-lg bg-primary text-white hover:bg-primary-dark"
            >
              {t('tours:page.filters.applyTags', { count: draft.length })}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
