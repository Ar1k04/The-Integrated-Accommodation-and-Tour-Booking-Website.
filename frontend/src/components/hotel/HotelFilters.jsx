import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Star, ChevronDown, ChevronUp } from 'lucide-react'
import { useFacilities } from '@/hooks/useFacilities'
import { AMENITIES, HOTEL_TYPES, LITEAPI_ID_TO_SLUG } from '@/utils/constants'

export default function HotelFilters({ filters, onChange }) {
  const { t } = useTranslation('hotels')
  const [expanded, setExpanded] = useState({ price: true, stars: true, rating: true, types: true, amenities: false })
  const { facilities, isLoading: facilitiesLoading } = useFacilities()

  const toggle = (key) => setExpanded((p) => ({ ...p, [key]: !p[key] }))
  const update = (key, value) => onChange({ ...filters, [key]: value })

  // When API data is ready use it; otherwise fall back to the static slug list
  const displayList = facilities.length > 0
    ? facilities.map((f) => {
        const slug = LITEAPI_ID_TO_SLUG[f.id]
        return { slug, label: t(`amenities.${slug}`, f.name) }
      })
    : AMENITIES.map((slug) => ({
        slug,
        label: t(`amenities.${slug}`, slug.replace(/_/g, ' ')),
      }))

  const selectedCount = (filters.amenities || []).length

  return (
    <div className="space-y-4">
      {/* Price Range */}
      <FilterSection title={t('search.priceRange', 'Price per night')} expanded={expanded.price} onToggle={() => toggle('price')}>
        <div className="flex items-center gap-2">
          <input type="number" placeholder="Min" value={filters.min_price || ''}
            onChange={(e) => update('min_price', e.target.value || null)}
            className="w-full border rounded-lg px-3 py-2 text-sm" />
          <span className="text-gray-400">—</span>
          <input type="number" placeholder="Max" value={filters.max_price || ''}
            onChange={(e) => update('max_price', e.target.value || null)}
            className="w-full border rounded-lg px-3 py-2 text-sm" />
        </div>
      </FilterSection>

      {/* Star Rating */}
      <FilterSection title={t('search.starRating', 'Star Rating')} expanded={expanded.stars} onToggle={() => toggle('stars')}>
        <div className="space-y-2">
          {[5, 4, 3, 2, 1].map((s) => (
            <label key={s} className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox"
                checked={filters.star_rating === s}
                onChange={() => update('star_rating', filters.star_rating === s ? null : s)}
                className="rounded border-gray-300" />
              <div className="flex items-center gap-0.5">
                {Array.from({ length: s }, (_, i) => (
                  <Star key={i} className="w-4 h-4 fill-warning text-warning" />
                ))}
              </div>
            </label>
          ))}
        </div>
      </FilterSection>

      {/* Review Score */}
      <FilterSection title="Review Score" expanded={expanded.rating} onToggle={() => toggle('rating')}>
        <div className="flex flex-wrap gap-2">
          {[{ label: 'Any', value: null }, { label: '6+', value: 6 }, { label: '7+', value: 7 }, { label: '8+', value: 8 }, { label: '9+', value: 9 }].map(
            ({ label, value }) => (
              <button key={label}
                onClick={() => update('min_rating', value)}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                  filters.min_rating === value ? 'bg-primary text-white border-primary' : 'hover:border-primary'
                }`}>
                {label}
              </button>
            )
          )}
        </div>
      </FilterSection>

      {/* Property Type */}
      <FilterSection title={t('search.propertyType', 'Property type')} expanded={expanded.types} onToggle={() => toggle('types')}>
        <div className="space-y-2">
          {HOTEL_TYPES.map(({ slug }) => (
            <label key={slug} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={(filters.hotel_types || []).includes(slug)}
                onChange={() => {
                  const curr = filters.hotel_types || []
                  update('hotel_types', curr.includes(slug) ? curr.filter((x) => x !== slug) : [...curr, slug])
                }}
                className="rounded border-gray-300"
              />
              <span className="text-sm">{t(`hotelTypes.${slug}`, slug.replace(/_/g, ' '))}</span>
            </label>
          ))}
        </div>
      </FilterSection>

      {/* Facilities */}
      <FilterSection title={t('search.amenities', 'Facilities')} expanded={expanded.amenities} onToggle={() => toggle('amenities')}>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {facilitiesLoading && facilities.length === 0
            ? Array.from({ length: 6 }, (_, i) => (
                <div key={i} className="h-5 bg-gray-100 rounded animate-pulse" />
              ))
            : displayList.map(({ slug, label }) => (
                <label key={slug} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={(filters.amenities || []).includes(slug)}
                    onChange={() => {
                      const curr = filters.amenities || []
                      update('amenities', curr.includes(slug) ? curr.filter((x) => x !== slug) : [...curr, slug])
                    }}
                    className="rounded border-gray-300"
                  />
                  <span className="text-sm">{label}</span>
                </label>
              ))
          }
        </div>
        {selectedCount >= 2 && (
          <p className="text-xs text-primary mt-2 font-medium">
            {t('amenities.matchAll', 'Showing hotels with all selected facilities')}
          </p>
        )}
      </FilterSection>
    </div>
  )
}

function FilterSection({ title, expanded, onToggle, children }) {
  return (
    <div className="bg-white rounded-xl p-4 shadow-sm">
      <button onClick={onToggle} className="flex items-center justify-between w-full text-left">
        <h3 className="font-semibold text-sm text-gray-900">{title}</h3>
        {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
      </button>
      {expanded && <div className="mt-3">{children}</div>}
    </div>
  )
}
