import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import FilterSection from '@/components/common/FilterSection'

const TIME_WINDOWS = [
  { id: 'early', label: 'tw_earlyMorning', from: 0, to: 6 },
  { id: 'morning', label: 'tw_morning', from: 6, to: 12 },
  { id: 'afternoon', label: 'tw_afternoon', from: 12, to: 18 },
  { id: 'evening', label: 'tw_evening', from: 18, to: 24 },
]

const STOPS_OPTIONS = [
  { value: null, key: 'stopsAny' },
  { value: 0, key: 'stopsDirect' },
  { value: 1, key: 'stopsOneMax' },
]

/**
 * FlightFilters — sidebar filters for flights search.
 *
 * Props:
 *   filters: { max_price, max_connections, airlines[], departure_windows[], max_duration_hours }
 *   onChange(filters): merges into filter state
 *   onClear()
 *   availableAirlines: [{ iata, name }]  — collected from current result set
 */
export default function FlightFilters({ filters, onChange, onClear, availableAirlines = [] }) {
  const { t } = useTranslation(['flights', 'common'])
  const [expanded, setExpanded] = useState({
    stops: true, price: true, airlines: true, departureTime: true, duration: false,
  })

  const toggle = (k) => setExpanded((p) => ({ ...p, [k]: !p[k] }))
  const update = (patch) => onChange({ ...filters, ...patch })

  const toggleArr = (key, value) => {
    const cur = filters[key] || []
    update({ [key]: cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value] })
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between px-1">
        <h3 className="font-heading font-bold text-base">{t('flights:filters.title', 'Filters')}</h3>
        <button
          onClick={onClear}
          className="text-xs text-primary hover:underline font-medium"
        >
          {t('flights:filters.clear')}
        </button>
      </div>

      {/* Stops */}
      <FilterSection
        title={t('flights:filters.stops')}
        expanded={expanded.stops}
        onToggle={() => toggle('stops')}
      >
        <div className="space-y-1.5">
          {STOPS_OPTIONS.map((opt) => (
            <label key={String(opt.value)} className="flex items-center gap-2 cursor-pointer">
              <input
                type="radio"
                name="stops"
                checked={(filters.max_connections ?? null) === opt.value}
                onChange={() => update({ max_connections: opt.value })}
                className="text-primary focus:ring-primary/30"
              />
              <span className="text-sm text-gray-700">{t(`flights:filters.${opt.key}`)}</span>
            </label>
          ))}
        </div>
      </FilterSection>

      {/* Price */}
      <FilterSection
        title={t('flights:filters.price')}
        expanded={expanded.price}
        onToggle={() => toggle('price')}
      >
        <div className="space-y-2">
          <label className="block text-xs text-gray-500">
            {t('flights:filters.maxPrice', 'Max price')}
          </label>
          <input
            type="number"
            min={0}
            value={filters.max_price ?? ''}
            onChange={(e) => {
              const v = e.target.value
              update({ max_price: v === '' ? null : Number(v) })
            }}
            placeholder="e.g. 500"
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
      </FilterSection>

      {/* Airlines */}
      {availableAirlines.length > 0 && (
        <FilterSection
          title={t('flights:filters.airlines')}
          expanded={expanded.airlines}
          onToggle={() => toggle('airlines')}
        >
          <div className="space-y-1.5 max-h-56 overflow-y-auto">
            {availableAirlines.map((al) => (
              <label key={al.iata} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={(filters.airlines || []).includes(al.iata)}
                  onChange={() => toggleArr('airlines', al.iata)}
                  className="text-primary focus:ring-primary/30"
                />
                <span className="text-sm text-gray-700 flex-1 truncate">
                  <span className="font-mono text-xs text-primary mr-2">{al.iata}</span>
                  {al.name}
                </span>
              </label>
            ))}
          </div>
        </FilterSection>
      )}

      {/* Departure time windows */}
      <FilterSection
        title={t('flights:filters.departureTime')}
        expanded={expanded.departureTime}
        onToggle={() => toggle('departureTime')}
      >
        <div className="grid grid-cols-2 gap-2">
          {TIME_WINDOWS.map((w) => {
            const active = (filters.departure_windows || []).includes(w.id)
            return (
              <button
                key={w.id}
                type="button"
                onClick={() => toggleArr('departure_windows', w.id)}
                className={`text-xs px-2 py-2 rounded-lg border transition-colors text-left ${
                  active
                    ? 'bg-primary text-white border-primary'
                    : 'bg-white text-gray-700 border-gray-200 hover:border-primary'
                }`}
              >
                {t(`flights:filters.${w.label}`)}
              </button>
            )
          })}
        </div>
      </FilterSection>

      {/* Max duration */}
      <FilterSection
        title={t('flights:filters.duration')}
        expanded={expanded.duration}
        onToggle={() => toggle('duration')}
      >
        <div className="space-y-2">
          <label className="block text-xs text-gray-500">
            {t('flights:filters.maxDurationHours', 'Max duration (hours)')}
          </label>
          <input
            type="number"
            min={1}
            max={48}
            value={filters.max_duration_hours ?? ''}
            onChange={(e) => {
              const v = e.target.value
              update({ max_duration_hours: v === '' ? null : Number(v) })
            }}
            placeholder="e.g. 8"
            className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
      </FilterSection>
    </div>
  )
}
