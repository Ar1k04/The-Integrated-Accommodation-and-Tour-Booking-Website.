import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plane, MapPin, X } from 'lucide-react'
import { flightsApi } from '@/api/flightsApi'

/**
 * AirportSearchInput — autocomplete input for IATA airport selection.
 *
 * Props:
 *   value   { iata, label } | null  — current selection
 *   onChange(option)               — fires with the chosen { iata, label, city, country }
 *   label   string                 — field label
 *   placeholder string
 *   disabled bool
 */
export default function AirportSearchInput({
  value,
  onChange,
  label,
  placeholder = 'City or IATA code',
  disabled = false,
}) {
  const [query, setQuery] = useState(value?.label || '')
  const [debounced, setDebounced] = useState('')
  const [showSuggest, setShowSuggest] = useState(false)
  const wrapperRef = useRef(null)

  // Mirror external value changes back into the local input (render-phase setState
  // avoids the cascading effect-render that useEffect-based syncing causes).
  const [trackedLabel, setTrackedLabel] = useState(value?.label || '')
  if ((value?.label || '') !== trackedLabel) {
    setTrackedLabel(value?.label || '')
    setQuery(value?.label || '')
  }

  useEffect(() => {
    const t = setTimeout(() => setDebounced(query.trim()), 250)
    return () => clearTimeout(t)
  }, [query])

  const { data, isFetching } = useQuery({
    queryKey: ['flight-airports', debounced],
    queryFn: () => flightsApi.searchAirports(debounced, 10),
    enabled: debounced.length >= 1 && showSuggest,
    staleTime: 5 * 60_000,
    select: (res) => res.data?.data || [],
  })

  useEffect(() => {
    const handler = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setShowSuggest(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const handlePick = (airport) => {
    const option = {
      iata: airport.iata,
      label: `${airport.city} (${airport.iata})`,
      city: airport.city,
      name: airport.name,
      country: airport.country,
    }
    onChange?.(option)
    setQuery(option.label)
    setShowSuggest(false)
  }

  const handleClear = () => {
    onChange?.(null)
    setQuery('')
    setShowSuggest(true)
  }

  return (
    <div ref={wrapperRef} className="relative">
      {label && (
        <label className="block text-xs font-medium text-gray-500 mb-1">{label}</label>
      )}
      <div className="relative">
        <Plane className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setShowSuggest(true) }}
          onFocus={() => setShowSuggest(true)}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete="off"
          className="w-full border rounded-lg pl-9 pr-9 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:bg-gray-100"
        />
        {query && !disabled && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-gray-600"
            aria-label="Clear"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {showSuggest && debounced.length >= 1 && (
        <div className="absolute z-30 left-0 right-0 mt-1 bg-white border rounded-lg shadow-lg max-h-72 overflow-y-auto">
          {isFetching && (
            <p className="px-3 py-2 text-xs text-gray-400">Searching…</p>
          )}
          {!isFetching && (!data || data.length === 0) && (
            <p className="px-3 py-2 text-xs text-gray-400">No airports found</p>
          )}
          {data?.map((ap) => (
            <button
              key={ap.iata}
              type="button"
              onClick={() => handlePick(ap)}
              className="w-full text-left px-3 py-2 hover:bg-primary/5 flex items-center gap-2 border-b last:border-b-0"
            >
              <MapPin className="w-4 h-4 text-gray-400 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  <span className="font-mono text-primary mr-2">{ap.iata}</span>
                  {ap.city}
                </p>
                <p className="text-xs text-gray-400 truncate">
                  {ap.name} · {ap.country}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
