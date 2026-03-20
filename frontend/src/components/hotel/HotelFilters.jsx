import { useState } from 'react'
import { AMENITIES } from '@/utils/constants'
import { Star, ChevronDown, ChevronUp } from 'lucide-react'

export default function HotelFilters({ filters, onChange }) {
  const [expanded, setExpanded] = useState({ price: true, stars: true, rating: true, amenities: false })

  const toggle = (key) => setExpanded((p) => ({ ...p, [key]: !p[key] }))

  const update = (key, value) => onChange({ ...filters, [key]: value })

  return (
    <div className="space-y-4">
      {/* Price Range */}
      <FilterSection title="Price per night" expanded={expanded.price} onToggle={() => toggle('price')}>
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
      <FilterSection title="Star Rating" expanded={expanded.stars} onToggle={() => toggle('stars')}>
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

      {/* Amenities */}
      <FilterSection title="Amenities" expanded={expanded.amenities} onToggle={() => toggle('amenities')}>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {AMENITIES.map((a) => (
            <label key={a} className="flex items-center gap-2 cursor-pointer capitalize">
              <input type="checkbox"
                checked={(filters.amenities || []).includes(a)}
                onChange={() => {
                  const curr = filters.amenities || []
                  update('amenities', curr.includes(a) ? curr.filter((x) => x !== a) : [...curr, a])
                }}
                className="rounded border-gray-300" />
              <span className="text-sm">{a.replace('_', ' ')}</span>
            </label>
          ))}
        </div>
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
