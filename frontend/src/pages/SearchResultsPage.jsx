import { useState, useMemo, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { hotelsApi } from '@/api/hotelsApi'
import HotelCard from '@/components/hotel/HotelCard'
import HotelFilters from '@/components/hotel/HotelFilters'
import HotelsMapPanel from '@/components/hotel/HotelsMapPanel'
import HotelsMapModal from '@/components/hotel/HotelsMapModal'
import { HotelCardSkeleton } from '@/components/common/Skeleton'
import SearchBar from '@/components/common/SearchBar'
import Pagination from '@/components/common/Pagination'
import { SlidersHorizontal, ArrowUpDown, X } from 'lucide-react'

// Separated so that changing city/dates/guests fully remounts this component
// (via the key prop in SearchResultsPage), clearing stale results instantly.
function HotelResults({ city, cityDisplay, country, latitude, longitude, radiusKm, checkIn, checkOut, guests, childAges }) {
  const { t } = useTranslation(['hotels', 'common'])
  const [showFilters, setShowFilters] = useState(false)
  const [sort, setSort] = useState('created_at')
  const [mapOpen, setMapOpen] = useState(false)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({
    min_price: null,
    max_price: null,
    star_rating: null,
    min_rating: null,
    amenities: [],
    hotel_types: [],
  })

  const SORT_OPTIONS = [
    { label: t('common:sort.recommended'), value: 'created_at' },
    { label: t('common:sort.priceLowHigh'), value: 'base_price:asc' },
    { label: t('common:sort.priceHighLow'), value: 'base_price:desc' },
    { label: t('common:sort.rating'), value: 'avg_rating:desc' },
    { label: t('common:sort.starRating'), value: 'star_rating:desc' },
  ]

  const [sortBy, sortOrder] = sort.includes(':') ? sort.split(':') : [sort, 'desc']

  const queryParams = useMemo(() => ({
    city: city || undefined,
    country: country || undefined,
    latitude: latitude || undefined,
    longitude: longitude || undefined,
    radius_km: radiusKm || undefined,
    check_in: checkIn || undefined,
    check_out: checkOut || undefined,
    guests: guests || undefined,
    child_ages: childAges || undefined,
    min_price: filters.min_price || undefined,
    max_price: filters.max_price || undefined,
    star_rating: filters.star_rating || undefined,
    amenities: filters.amenities?.length ? filters.amenities.join(',') : undefined,
    hotel_types: filters.hotel_types?.length ? filters.hotel_types.join(',') : undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
    per_page: 20,
  }), [city, country, latitude, longitude, radiusKm, checkIn, checkOut, guests, childAges, filters, sortBy, sortOrder])

  // Reset to page 1 whenever filters, sort, or the underlying search change.
  useEffect(() => { setPage(1) }, [queryParams])

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['hotels-search', queryParams, page],
    queryFn: () => hotelsApi.list({ ...queryParams, page }),
    placeholderData: keepPreviousData,
  })

  const hotels = data?.data?.items || []
  const meta = data?.data?.meta
  const total = meta?.total || 0
  const totalPages = meta?.total_pages || 1

  const handlePageChange = (next) => {
    if (next < 1 || next > totalPages || next === page) return
    setPage(next)
    if (typeof window !== 'undefined') {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    }
  }

  const resultLabel = isLoading
    ? t('hotels:search.searching')
    : city
      ? t('hotels:search.hotelsInCity', { count: total, city: cityDisplay || city })
      : t('hotels:search.hotelsFound', { count: total })

  return (
    <>
    <div className="flex gap-6">
      {/* Filters Sidebar (with mini map preview on top) */}
      <div className={`${showFilters ? 'fixed inset-0 z-50 bg-white p-4 overflow-y-auto md:static md:bg-transparent' : 'hidden'} md:block w-full md:w-64 shrink-0 space-y-4`}>
        {!isLoading && hotels.length > 0 && (
          <div className="rounded-xl overflow-hidden border border-gray-200 shadow-sm bg-white">
            <HotelsMapPanel
              hotels={hotels}
              preview
              onExpand={() => setMapOpen(true)}
            />
          </div>
        )}
        <div className="flex items-center justify-between mb-4 md:hidden">
          <h2 className="font-bold text-lg">{t('hotels:search.filters')}</h2>
          <button onClick={() => setShowFilters(false)}><X className="w-5 h-5" /></button>
        </div>
        <HotelFilters filters={filters} onChange={setFilters} />
      </div>

      {/* Results */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-gray-500">{resultLabel}</p>
          <button onClick={() => setShowFilters(!showFilters)}
            className="md:hidden flex items-center gap-2 text-sm font-medium text-primary">
            <SlidersHorizontal className="w-4 h-4" /> {t('hotels:search.filters')}
          </button>
        </div>

        <div className="flex items-center gap-2 mb-4 overflow-x-auto pb-2">
          <ArrowUpDown className="w-4 h-4 text-gray-400 shrink-0" />
          {SORT_OPTIONS.map((opt) => (
            <button key={opt.value} onClick={() => setSort(opt.value)}
              className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                sort === opt.value ? 'bg-primary text-white border-primary' : 'hover:border-gray-400'
              }`}>
              {opt.label}
            </button>
          ))}
        </div>

        <div className={`space-y-4 ${isFetching && !isLoading ? 'opacity-60 transition-opacity' : ''}`}>
          {isLoading
            ? Array.from({ length: 4 }, (_, i) => <HotelCardSkeleton key={i} />)
            : hotels.map((hotel) => <HotelCard key={hotel.id || hotel.liteapi_hotel_id} hotel={hotel} />)
          }
          {!isLoading && hotels.length === 0 && (
            <div className="text-center py-20">
              <p className="text-gray-400 text-lg mb-2">{t('hotels:search.noResults')}</p>
              <p className="text-gray-400 text-sm">{t('hotels:search.tryAdjusting')}</p>
            </div>
          )}
        </div>

        {!isLoading && totalPages > 1 && (
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={handlePageChange}
          />
        )}
      </div>
    </div>
    <HotelsMapModal
      open={mapOpen}
      onClose={() => setMapOpen(false)}
      hotels={hotels}
      title={city ? `Hotels in ${cityDisplay || city}` : 'All hotels'}
    />
    </>
  )
}

export default function SearchResultsPage() {
  const [params] = useSearchParams()

  const city = params.get('city') || ''
  const country = params.get('country') || ''
  const latitude = params.get('latitude') || ''
  const longitude = params.get('longitude') || ''
  const radiusKm = params.get('radius_km') || ''
  const checkIn = params.get('check_in') || ''
  const checkOut = params.get('check_out') || ''
  const guests = params.get('guests') || ''
  const childAges = params.get('child_ages') || ''

  // Friendly country name from ISO-2 (e.g. "US" → "United States") via the
  // browser's standard Intl.DisplayNames API, localized to the user's UI lang.
  // Falls back to the bare code if the API or value is unavailable.
  const countryDisplay = (() => {
    if (!country) return ''
    try {
      const locale = (typeof navigator !== 'undefined' && navigator.language) || 'en'
      return new Intl.DisplayNames([locale], { type: 'region' }).of(country) || country
    } catch {
      return country
    }
  })()
  const cityDisplay = city && countryDisplay ? `${city}, ${countryDisplay}` : city

  // Key forces HotelResults to fully remount on every new search,
  // wiping stale data and resetting filters/sort/scroll position.
  const searchKey = `${city}|${country}|${latitude}|${longitude}|${checkIn}|${checkOut}|${guests}|${childAges}`

  return (
    <>
      <Helmet>
        <title>{city ? `Hotels in ${cityDisplay}` : 'Search Hotels'} — TravelBooking</title>
        <meta name="description" content={`Search and compare ${city ? `hotels in ${cityDisplay}` : 'hotels worldwide'}. Best prices guaranteed.`} />
      </Helmet>

      <div className="bg-primary py-4">
        <div className="max-w-7xl mx-auto px-4">
          <SearchBar variant="compact" />
        </div>
      </div>

      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="font-heading text-xl font-bold text-gray-900 mb-6">
            {city ? `Hotels in ${cityDisplay}` : 'Search Hotels'}
          </h1>
          <HotelResults
            key={searchKey}
            city={city}
            cityDisplay={cityDisplay}
            country={country}
            latitude={latitude}
            longitude={longitude}
            radiusKm={radiusKm}
            checkIn={checkIn}
            checkOut={checkOut}
            guests={guests}
            childAges={childAges}
          />
        </div>
      </div>
    </>
  )
}
