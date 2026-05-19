import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { MapPin } from 'lucide-react'
import FilterSection from '@/components/common/FilterSection'
import TagPickerModal from './TagPickerModal'
import { toursApi } from '@/api/toursApi'
import { searchCities } from '@/api/nominatimApi'
import {
  POPULAR_VIATOR_TAGS,
  VIATOR_FLAGS,
  VIATOR_DURATION_PRESETS,
  VIATOR_RATING_PRESETS,
} from '@/utils/constants'

const durationsEqual = (filters, p) =>
  (filters.duration_min ?? null) === (p.min ?? null)
  && (filters.duration_max ?? null) === (p.max ?? null)

export default function TourFilters({ filters, onChange, onClear }) {
  const { t } = useTranslation(['tours', 'common'])
  const [expanded, setExpanded] = useState({
    destination: true, price: true, tags: true, flags: true,
    rating: true, duration: true, dates: false,
  })
  const [tagModalOpen, setTagModalOpen] = useState(false)

  const toggle = (key) => setExpanded((p) => ({ ...p, [key]: !p[key] }))
  const update = (patch) => onChange({ ...filters, ...patch })

  // ── Destination autocomplete ─────────────────────────────────────────────
  const [cityInput, setCityInput] = useState(filters.city || '')
  const [debouncedCity, setDebouncedCity] = useState(filters.city || '')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const cityInputRef = useRef(null)

  // Mirror external resets of filters.city back into the local input (render-phase
  // setState — modern React pattern, avoids cascading effect renders).
  const [trackedCity, setTrackedCity] = useState(filters.city || '')
  if ((filters.city || '') !== trackedCity) {
    setTrackedCity(filters.city || '')
    setCityInput(filters.city || '')
  }

  useEffect(() => {
    const id = setTimeout(() => setDebouncedCity(cityInput), 300)
    return () => clearTimeout(id)
  }, [cityInput])

  useEffect(() => {
    const handler = (e) => {
      if (cityInputRef.current && !cityInputRef.current.contains(e.target)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const { data: citySuggestions = [], isFetching } = useQuery({
    queryKey: ['tour-city-suggestions', debouncedCity],
    queryFn: () => searchCities(debouncedCity),
    enabled: debouncedCity.length >= 2,
    staleTime: 60_000,
  })

  // ── Prefetch tag list once (cheap, used by quick-pick label lookups) ─────
  const { data: tagData } = useQuery({
    queryKey: ['viator-tags'],
    queryFn: () => toursApi.getViatorTags().then((r) => r.data?.tags || []),
    staleTime: Infinity,
  })
  const tagById = new Map((tagData || []).map((t) => [t.tag_id, t]))

  const toggleArrayItem = (key, value) => {
    const curr = filters[key] || []
    update({ [key]: curr.includes(value) ? curr.filter((v) => v !== value) : [...curr, value] })
  }

  const setDurationPreset = (preset) => {
    if (durationsEqual(filters, preset)) {
      update({ duration_min: null, duration_max: null })
    } else {
      update({ duration_min: preset.min, duration_max: preset.max })
    }
  }

  return (
    <div className="space-y-4">
      <FilterSection title={t('tours:page.destination')} expanded={expanded.destination} onToggle={() => toggle('destination')}>
        <div className="relative" ref={cityInputRef}>
          <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            value={cityInput}
            onChange={(e) => {
              setCityInput(e.target.value)
              setShowSuggestions(true)
              if (!e.target.value) update({ city: '' })
            }}
            onFocus={() => cityInput.length >= 2 && setShowSuggestions(true)}
            placeholder={t('tours:page.cityOrCountry')}
            className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          {showSuggestions && (isFetching || citySuggestions.length > 0) && (
            <ul className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border rounded-lg shadow-lg overflow-hidden max-h-56 overflow-y-auto">
              {isFetching && citySuggestions.length === 0 && (
                <li className="px-3 py-2 text-sm text-gray-400">{t('common:common.loading')}</li>
              )}
              {citySuggestions.map((s, i) => (
                <li
                  key={i}
                  onMouseDown={() => {
                    update({ city: s.city })
                    setCityInput(s.city)
                    setShowSuggestions(false)
                  }}
                  className="flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-primary/5"
                >
                  <MapPin className="w-3.5 h-3.5 text-primary shrink-0" />
                  <span className="font-medium">{s.city}</span>
                  {s.state && <span className="text-gray-400 truncate">{s.state}, {s.country}</span>}
                  {!s.state && s.country && <span className="text-gray-400 truncate">{s.country}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </FilterSection>

      <FilterSection title={t('tours:page.priceRange')} expanded={expanded.price} onToggle={() => toggle('price')}>
        <div className="flex items-center gap-2">
          <input
            type="number"
            placeholder={t('common:common.min')}
            value={filters.min_price || ''}
            onChange={(e) => update({ min_price: e.target.value ? Number(e.target.value) : null })}
            className="w-full border rounded-lg px-3 py-2 text-sm"
          />
          <span className="text-gray-400">—</span>
          <input
            type="number"
            placeholder={t('common:common.max')}
            value={filters.max_price || ''}
            onChange={(e) => update({ max_price: e.target.value ? Number(e.target.value) : null })}
            className="w-full border rounded-lg px-3 py-2 text-sm"
          />
        </div>
      </FilterSection>

      <FilterSection title={t('tours:page.filters.tourType')} expanded={expanded.tags} onToggle={() => toggle('tags')}>
        <div className="flex flex-wrap gap-2">
          {POPULAR_VIATOR_TAGS.map((tag) => {
            const active = (filters.tags || []).includes(tag.id)
            const liveName = tagById.get(tag.id)?.name || tag.label
            return (
              <button
                key={tag.id}
                onClick={() => toggleArrayItem('tags', tag.id)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  active ? 'bg-primary text-white border-primary' : 'hover:border-primary'
                }`}
              >
                {liveName}
              </button>
            )
          })}
          {/* Show extra selected tags that aren't in the popular list, so users see all active picks. */}
          {(filters.tags || [])
            .filter((id) => !POPULAR_VIATOR_TAGS.some((t) => t.id === id))
            .map((id) => (
              <button
                key={id}
                onClick={() => toggleArrayItem('tags', id)}
                className="px-3 py-1.5 rounded-full text-xs font-medium border bg-primary text-white border-primary"
              >
                {tagById.get(id)?.name || `#${id}`}
              </button>
            ))}
        </div>
        <button
          onClick={() => setTagModalOpen(true)}
          className="mt-3 text-sm font-medium text-primary hover:underline"
        >
          {t('tours:page.filters.moreCategories')} →
        </button>
      </FilterSection>

      <FilterSection title={t('tours:page.filters.flags')} expanded={expanded.flags} onToggle={() => toggle('flags')}>
        <div className="space-y-2">
          {VIATOR_FLAGS.map((flag) => (
            <label key={flag} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={(filters.flags || []).includes(flag)}
                onChange={() => toggleArrayItem('flags', flag)}
                className="rounded border-gray-300"
              />
              <span className="text-sm">{t(`tours:page.filters.flag_${flag}`)}</span>
            </label>
          ))}
        </div>
      </FilterSection>

      <FilterSection title={t('tours:page.filters.rating')} expanded={expanded.rating} onToggle={() => toggle('rating')}>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => update({ rating_min: null })}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              filters.rating_min == null ? 'bg-primary text-white border-primary' : 'hover:border-primary'
            }`}
          >
            {t('tours:page.filters.ratingAny')}
          </button>
          {VIATOR_RATING_PRESETS.map((r) => (
            <button
              key={r}
              onClick={() => update({ rating_min: filters.rating_min === r ? null : r })}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                filters.rating_min === r ? 'bg-primary text-white border-primary' : 'hover:border-primary'
              }`}
            >
              {r}★+
            </button>
          ))}
        </div>
      </FilterSection>

      <FilterSection title={t('tours:page.filters.duration')} expanded={expanded.duration} onToggle={() => toggle('duration')}>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => update({ duration_min: null, duration_max: null })}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
              filters.duration_min == null && filters.duration_max == null
                ? 'bg-primary text-white border-primary' : 'hover:border-primary'
            }`}
          >
            {t('tours:page.filters.ratingAny')}
          </button>
          {VIATOR_DURATION_PRESETS.map((preset) => (
            <button
              key={preset.id}
              onClick={() => setDurationPreset(preset)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                durationsEqual(filters, preset) ? 'bg-primary text-white border-primary' : 'hover:border-primary'
              }`}
            >
              {t(`tours:page.filters.duration_${preset.id}`)}
            </button>
          ))}
        </div>
      </FilterSection>

      <FilterSection title={t('tours:page.filters.dateRange')} expanded={expanded.dates} onToggle={() => toggle('dates')}>
        <div className="space-y-2">
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('tours:page.filters.startDate')}</label>
            <input
              type="date"
              value={filters.start_date || ''}
              onChange={(e) => update({ start_date: e.target.value || '' })}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">{t('tours:page.filters.endDate')}</label>
            <input
              type="date"
              value={filters.end_date || ''}
              onChange={(e) => update({ end_date: e.target.value || '' })}
              className="w-full border rounded-lg px-3 py-2 text-sm"
            />
          </div>
        </div>
      </FilterSection>

      <button
        onClick={onClear}
        className="w-full text-center text-sm text-primary hover:underline pt-1"
      >
        {t('tours:page.clearFilters')}
      </button>

      <TagPickerModal
        open={tagModalOpen}
        selectedTagIds={filters.tags || []}
        onApply={(ids) => update({ tags: ids })}
        onClose={() => setTagModalOpen(false)}
      />
    </div>
  )
}
