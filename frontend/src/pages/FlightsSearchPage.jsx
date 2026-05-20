import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { format, addDays } from 'date-fns'
import {
  PlaneTakeoff, ArrowRight, ArrowLeftRight, Filter, X, SlidersHorizontal,
} from 'lucide-react'

import { flightsApi } from '@/api/flightsApi'
import FlightOfferCard from '@/components/flight/FlightOfferCard'
import FlightFilters from '@/components/flight/FlightFilters'
import AirportSearchInput from '@/components/flight/AirportSearchInput'
import Skeleton from '@/components/common/Skeleton'

const EMPTY_FILTERS = {
  max_price: null,
  max_connections: null,
  airlines: [],
  departure_windows: [],
  max_duration_hours: null,
}

const SORT_OPTIONS = [
  { value: 'price:asc', key: 'cheapest', backend: { sort_by: 'price', sort_order: 'asc' } },
  { value: 'duration:asc', key: 'fastest', backend: { sort_by: 'duration', sort_order: 'asc' } },
  { value: 'departure_time:asc', key: 'earliest', backend: { sort_by: 'departure_time', sort_order: 'asc' } },
]

function getSliceDurationMinutes(slice) {
  const segs = slice?.segments || []
  if (segs.length === 0) return 0
  const first = segs[0]
  const last = segs[segs.length - 1]
  try {
    return Math.max(0, Math.floor((new Date(last.arrival_at) - new Date(first.departure_at)) / 60000))
  } catch { return 0 }
}

function inTimeWindow(iso, windows) {
  if (!windows?.length) return true
  try {
    const h = new Date(iso).getHours()
    return windows.some((w) => {
      if (w === 'early') return h >= 0 && h < 6
      if (w === 'morning') return h >= 6 && h < 12
      if (w === 'afternoon') return h >= 12 && h < 18
      if (w === 'evening') return h >= 18 && h <= 23
      return true
    })
  } catch { return true }
}

export default function FlightsSearchPage() {
  const { t } = useTranslation(['flights', 'common'])
  const navigate = useNavigate()
  const today = format(new Date(), 'yyyy-MM-dd')

  // ── Search form state ───────────────────────────────────────────────────
  const [tripType, setTripType] = useState('one-way')
  const [origin, setOrigin] = useState({ iata: 'HAN', label: 'Hanoi (HAN)', city: 'Hanoi' })
  const [destination, setDestination] = useState({ iata: 'SGN', label: 'Ho Chi Minh City (SGN)', city: 'Ho Chi Minh City' })
  const [departDate, setDepartDate] = useState(format(addDays(new Date(), 7), 'yyyy-MM-dd'))
  const [returnDate, setReturnDate] = useState(format(addDays(new Date(), 14), 'yyyy-MM-dd'))
  const [passengers, setPassengers] = useState(1)
  const [cabinClass, setCabinClass] = useState('economy')

  // ── Result-list state ───────────────────────────────────────────────────
  const [submittedQuery, setSubmittedQuery] = useState(null)
  const [filters, setFilters] = useState({ ...EMPTY_FILTERS })
  const [sort, setSort] = useState('price:asc')
  const [mobileFiltersOpen, setMobileFiltersOpen] = useState(false)

  const handleSwap = () => {
    setOrigin(destination)
    setDestination(origin)
  }

  const validateForm = () => {
    if (!origin?.iata || !destination?.iata) {
      toast.error(t('flights:page.selectAirportFirst')); return false
    }
    if (origin.iata === destination.iata) {
      toast.error(t('flights:page.sameAirport')); return false
    }
    if (!departDate) { toast.error(t('flights:page.selectDate')); return false }
    if (tripType === 'round-trip' && !returnDate) {
      toast.error(t('flights:page.selectReturnDate')); return false
    }
    if (tripType === 'round-trip' && returnDate <= departDate) {
      toast.error(t('flights:page.returnAfterDeparture')); return false
    }
    return true
  }

  // Reset filters whenever a fresh search is submitted
  const handleSearch = () => {
    if (!validateForm()) return
    setFilters({ ...EMPTY_FILTERS })
    setSubmittedQuery({
      origin: origin.iata,
      destination: destination.iata,
      depart_date: departDate,
      return_date: tripType === 'round-trip' ? returnDate : undefined,
      passengers,
      cabin_class: cabinClass,
    })
  }

  // ── Build backend params (filters that the API can prefilter) ──────────
  const backendParams = useMemo(() => {
    if (!submittedQuery) return null
    const sortBackend = SORT_OPTIONS.find((o) => o.value === sort)?.backend
      || { sort_by: 'price', sort_order: 'asc' }
    return {
      ...submittedQuery,
      max_connections: filters.max_connections ?? undefined,
      max_price: filters.max_price ?? undefined,
      airlines: filters.airlines?.length ? filters.airlines : undefined,
      ...sortBackend,
    }
  }, [submittedQuery, filters.max_connections, filters.max_price, filters.airlines, sort])

  const { data: searchData, isFetching, isError } = useQuery({
    queryKey: ['flights-search', backendParams],
    queryFn: () => flightsApi.search(backendParams),
    enabled: !!backendParams,
    select: (res) => res.data?.data || [],
    staleTime: 5 * 60_000,
  })

  useEffect(() => {
    if (isError) toast.error(t('flights:page.searchUnavailable'))
  }, [isError, t])

  // ── Frontend-only filters (time window + duration) ──────────────────────
  const offers = useMemo(() => searchData || [], [searchData])

  const filteredOffers = useMemo(() => {
    return offers.filter((o) => {
      const firstSlice = o.slices?.[0]
      if (!firstSlice) return false
      const firstDep = firstSlice.segments?.[0]?.departure_at
      if (filters.departure_windows?.length && !inTimeWindow(firstDep, filters.departure_windows)) {
        return false
      }
      if (filters.max_duration_hours) {
        const totalMin = (o.slices || []).reduce(
          (acc, sl) => acc + getSliceDurationMinutes(sl), 0,
        )
        if (totalMin / 60 > filters.max_duration_hours) return false
      }
      return true
    })
  }, [offers, filters.departure_windows, filters.max_duration_hours])

  // ── Airlines list for sidebar (derived from current result set) ────────
  const availableAirlines = useMemo(() => {
    const map = new Map()
    for (const o of offers) {
      if (o.airline_iata && !map.has(o.airline_iata)) {
        map.set(o.airline_iata, { iata: o.airline_iata, name: o.airline_name || o.airline_iata })
      }
    }
    return Array.from(map.values())
  }, [offers])

  const handleSelectOffer = (offer) => {
    navigate(`/flights/offers/${offer.duffel_offer_id}?pax=${passengers}`)
  }

  return (
    <>
      <Helmet>
        <title>{t('flights:page.title')}</title>
      </Helmet>

      {/* Hero */}
      <div className="bg-primary text-white py-10">
        <div className="max-w-6xl mx-auto px-4">
          <h1 className="font-heading text-3xl font-bold mb-1 flex items-center gap-3">
            <PlaneTakeoff className="w-8 h-8" /> {t('flights:page.heading')}
          </h1>
          <p className="text-white/70 text-sm">{t('flights:page.subtitle')}</p>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Search form */}
        <div className="bg-white rounded-2xl border shadow-sm p-6 mb-8 space-y-4">
          {/* Trip type */}
          <div className="flex gap-2 text-sm">
            {['one-way', 'round-trip'].map((mode) => (
              <button
                key={mode}
                onClick={() => setTripType(mode)}
                className={`px-4 py-1.5 rounded-full font-medium transition-colors ${
                  tripType === mode
                    ? 'bg-primary text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {mode === 'one-way'
                  ? t('flights:page.tripType.oneWay')
                  : t('flights:page.tripType.roundTrip')}
              </button>
            ))}
          </div>

          {/* Airports */}
          <div className="grid grid-cols-1 sm:grid-cols-[1fr,auto,1fr] gap-3 items-end">
            <AirportSearchInput
              label={t('flights:page.from')}
              value={origin}
              onChange={setOrigin}
              placeholder="HAN, Hanoi…"
            />
            <button
              onClick={handleSwap}
              type="button"
              className="p-2 rounded-full hover:bg-gray-100 transition-colors self-end mb-0.5 text-gray-500"
              title={t('flights:page.swap')}
              aria-label={t('flights:page.swap')}
            >
              <ArrowLeftRight className="w-4 h-4" />
            </button>
            <AirportSearchInput
              label={t('flights:page.to')}
              value={destination}
              onChange={setDestination}
              placeholder="SGN, Saigon…"
            />
          </div>

          {/* Dates, pax, cabin */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                {t('flights:page.depart')}
              </label>
              <input
                type="date"
                value={departDate}
                min={today}
                onChange={(e) => setDepartDate(e.target.value)}
                className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            {tripType === 'round-trip' && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  {t('flights:page.return')}
                </label>
                <input
                  type="date"
                  value={returnDate}
                  min={departDate || today}
                  onChange={(e) => setReturnDate(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            )}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                {t('flights:page.passengers')}
              </label>
              <input
                type="number"
                value={passengers}
                min={1}
                max={9}
                onChange={(e) => setPassengers(Math.max(1, parseInt(e.target.value) || 1))}
                className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">
                {t('flights:page.cabinClass')}
              </label>
              <select
                value={cabinClass}
                onChange={(e) => setCabinClass(e.target.value)}
                className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="economy">{t('flights:page.cabin.economy')}</option>
                <option value="premium_economy">{t('flights:page.cabin.premium_economy')}</option>
                <option value="business">{t('flights:page.cabin.business')}</option>
                <option value="first">{t('flights:page.cabin.first')}</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleSearch}
            disabled={isFetching}
            className="w-full bg-primary hover:bg-primary/90 disabled:bg-gray-300 text-white font-bold py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
          >
            <PlaneTakeoff className="w-5 h-5" />
            {isFetching ? t('flights:page.searching') : t('flights:page.search')}
          </button>
        </div>

        {/* Results section */}
        {submittedQuery && (
          <div className="grid grid-cols-1 md:grid-cols-[260px,1fr] gap-6">
            {/* Filters sidebar (desktop) */}
            <aside className="hidden md:block">
              <FlightFilters
                filters={filters}
                onChange={setFilters}
                onClear={() => setFilters({ ...EMPTY_FILTERS })}
                availableAirlines={availableAirlines}
              />
            </aside>

            <div>
              {/* Sort + mobile filter trigger */}
              <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
                <div className="text-sm text-gray-500">
                  {!isFetching && offers.length > 0 && (
                    <span>
                      {t('flights:page.found', { count: filteredOffers.length })}
                      <span className="text-gray-300 mx-2">·</span>
                      <strong>{submittedQuery.origin}</strong>
                      <ArrowRight className="w-3 h-3 inline mx-1" />
                      <strong>{submittedQuery.destination}</strong>
                    </span>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setMobileFiltersOpen(true)}
                    className="md:hidden flex items-center gap-1.5 text-sm border rounded-lg px-3 py-1.5 hover:bg-gray-50"
                  >
                    <SlidersHorizontal className="w-4 h-4" /> {t('flights:page.filtersTitle')}
                  </button>
                  <div className="flex gap-1 bg-gray-100 rounded-full p-1 text-xs">
                    {SORT_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        onClick={() => setSort(opt.value)}
                        className={`px-3 py-1 rounded-full font-medium transition-colors ${
                          sort === opt.value
                            ? 'bg-white text-gray-900 shadow-sm'
                            : 'text-gray-500 hover:text-gray-700'
                        }`}
                      >
                        {t(`flights:sort.${opt.key}`)}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Active filter chips */}
              {(filters.max_connections === 0 || filters.airlines?.length > 0
                || filters.max_price || filters.departure_windows?.length > 0
                || filters.max_duration_hours) && (
                <div className="flex items-center gap-2 mb-4 flex-wrap">
                  {filters.max_connections === 0 && (
                    <Chip onClear={() => setFilters((f) => ({ ...f, max_connections: null }))}>
                      {t('flights:filters.stopsDirect')}
                    </Chip>
                  )}
                  {filters.airlines?.map((iata) => (
                    <Chip
                      key={iata}
                      onClear={() => setFilters((f) => ({
                        ...f, airlines: f.airlines.filter((a) => a !== iata),
                      }))}
                    >
                      {iata}
                    </Chip>
                  ))}
                  {filters.max_price && (
                    <Chip onClear={() => setFilters((f) => ({ ...f, max_price: null }))}>
                      ≤ {filters.max_price}
                    </Chip>
                  )}
                  {filters.max_duration_hours && (
                    <Chip onClear={() => setFilters((f) => ({ ...f, max_duration_hours: null }))}>
                      ≤ {filters.max_duration_hours}h
                    </Chip>
                  )}
                  {filters.departure_windows?.map((w) => (
                    <Chip
                      key={w}
                      onClear={() => setFilters((f) => ({
                        ...f, departure_windows: f.departure_windows.filter((x) => x !== w),
                      }))}
                    >
                      {t(`flights:filters.tw_${w === 'early' ? 'earlyMorning' : w}`)}
                    </Chip>
                  ))}
                </div>
              )}

              {/* Results / skeleton / empty */}
              {isFetching && (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
                </div>
              )}

              {!isFetching && filteredOffers.length === 0 && (
                <div className="text-center py-16 text-gray-400">
                  <PlaneTakeoff className="w-12 h-12 mx-auto mb-3 opacity-30" />
                  <p className="font-medium">{t('flights:page.noResults')}</p>
                  <p className="text-sm mt-1">{t('flights:page.noResultsHint')}</p>
                </div>
              )}

              {!isFetching && filteredOffers.length > 0 && (
                <div className="space-y-3">
                  {filteredOffers.map((offer) => (
                    <FlightOfferCard
                      key={offer.duffel_offer_id}
                      offer={offer}
                      onSelect={handleSelectOffer}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Mobile filters drawer */}
      {mobileFiltersOpen && (
        <div className="md:hidden fixed inset-0 z-50 bg-black/40 flex items-end" onClick={() => setMobileFiltersOpen(false)}>
          <div className="bg-white w-full rounded-t-2xl max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 bg-white border-b px-4 py-3 flex items-center justify-between">
              <h3 className="font-heading font-bold">{t('flights:page.filtersTitle')}</h3>
              <button onClick={() => setMobileFiltersOpen(false)} className="p-1.5 hover:bg-gray-100 rounded-full">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-4">
              <FlightFilters
                filters={filters}
                onChange={setFilters}
                onClear={() => setFilters({ ...EMPTY_FILTERS })}
                availableAirlines={availableAirlines}
              />
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function Chip({ children, onClear }) {
  return (
    <span className="inline-flex items-center gap-1 bg-primary/10 text-primary text-xs font-medium px-2.5 py-1 rounded-full">
      {children}
      <button onClick={onClear} className="hover:bg-primary/20 rounded-full p-0.5" aria-label="Remove">
        <X className="w-3 h-3" />
      </button>
    </span>
  )
}
