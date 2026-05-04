import { useState, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useInfiniteQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { hotelsApi } from '@/api/hotelsApi'
import HotelCard from '@/components/hotel/HotelCard'
import HotelFilters from '@/components/hotel/HotelFilters'
import { HotelCardSkeleton } from '@/components/common/Skeleton'
import SearchBar from '@/components/common/SearchBar'
import { useInfiniteScroll } from '@/hooks/useInfiniteScroll'
import { SlidersHorizontal, ArrowUpDown, X } from 'lucide-react'

const SORT_OPTIONS = [
  { label: 'Recommended', value: 'created_at' },
  { label: 'Price: Low to High', value: 'base_price:asc' },
  { label: 'Price: High to Low', value: 'base_price:desc' },
  { label: 'Rating', value: 'avg_rating:desc' },
  { label: 'Star Rating', value: 'star_rating:desc' },
]

// Separated so that changing city/dates/guests fully remounts this component
// (via the key prop in SearchResultsPage), clearing stale results instantly.
function HotelResults({ city, checkIn, checkOut, guests }) {
  const [showFilters, setShowFilters] = useState(false)
  const [sort, setSort] = useState('created_at')
  const [filters, setFilters] = useState({
    min_price: null,
    max_price: null,
    star_rating: null,
    min_rating: null,
    amenities: [],
  })

  const [sortBy, sortOrder] = sort.includes(':') ? sort.split(':') : [sort, 'desc']

  const queryParams = useMemo(() => ({
    city: city || undefined,
    check_in: checkIn || undefined,
    check_out: checkOut || undefined,
    guests: guests || undefined,
    min_price: filters.min_price || undefined,
    max_price: filters.max_price || undefined,
    star_rating: filters.star_rating || undefined,
    amenities: filters.amenities?.length ? filters.amenities.join(',') : undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
    per_page: 10,
  }), [city, checkIn, checkOut, guests, filters, sortBy, sortOrder])

  const {
    data, fetchNextPage, hasNextPage, isFetchingNextPage, isLoading,
  } = useInfiniteQuery({
    queryKey: ['hotels-search', queryParams],
    queryFn: ({ pageParam = 1 }) => hotelsApi.list({ ...queryParams, page: pageParam }),
    getNextPageParam: (lastPage) => {
      const meta = lastPage.data?.meta
      if (meta && meta.page < meta.total_pages) return meta.page + 1
      return undefined
    },
  })

  const allHotels = data?.pages.flatMap((p) => p.data?.items || []) || []
  const total = data?.pages[0]?.data?.meta?.total || 0

  const loadMoreRef = useInfiniteScroll(() => {
    if (hasNextPage && !isFetchingNextPage) fetchNextPage()
  }, { enabled: hasNextPage })

  return (
    <div className="flex gap-6">
      {/* Filters Sidebar */}
      <div className={`${showFilters ? 'fixed inset-0 z-50 bg-white p-4 overflow-y-auto md:static md:bg-transparent' : 'hidden'} md:block w-full md:w-64 shrink-0`}>
        <div className="flex items-center justify-between mb-4 md:hidden">
          <h2 className="font-bold text-lg">Filters</h2>
          <button onClick={() => setShowFilters(false)}><X className="w-5 h-5" /></button>
        </div>
        <HotelFilters filters={filters} onChange={setFilters} />
      </div>

      {/* Results */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-4">
          <p className="text-sm text-gray-500">
            {isLoading ? 'Searching…' : `${total} hotel${total !== 1 ? 's' : ''} ${city ? `in ${city}` : 'found'}`}
          </p>
          <button onClick={() => setShowFilters(!showFilters)}
            className="md:hidden flex items-center gap-2 text-sm font-medium text-primary">
            <SlidersHorizontal className="w-4 h-4" /> Filters
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

        <div className="space-y-4">
          {isLoading
            ? Array.from({ length: 4 }, (_, i) => <HotelCardSkeleton key={i} />)
            : allHotels.map((hotel) => <HotelCard key={hotel.id || hotel.liteapi_hotel_id} hotel={hotel} />)
          }
          {!isLoading && allHotels.length === 0 && (
            <div className="text-center py-20">
              <p className="text-gray-400 text-lg mb-2">No hotels found</p>
              <p className="text-gray-400 text-sm">Try adjusting your search or filters.</p>
            </div>
          )}
          {isFetchingNextPage && <HotelCardSkeleton />}
          <div ref={loadMoreRef} />
        </div>
      </div>
    </div>
  )
}

export default function SearchResultsPage() {
  const [params] = useSearchParams()

  const city = params.get('city') || ''
  const checkIn = params.get('check_in') || ''
  const checkOut = params.get('check_out') || ''
  const guests = params.get('guests') || ''

  // Key forces HotelResults to fully remount on every new search,
  // wiping stale data and resetting filters/sort/scroll position.
  const searchKey = `${city}|${checkIn}|${checkOut}|${guests}`

  return (
    <>
      <Helmet>
        <title>{city ? `Hotels in ${city}` : 'Search Hotels'} — TravelBooking</title>
        <meta name="description" content={`Search and compare ${city ? `hotels in ${city}` : 'hotels worldwide'}. Best prices guaranteed.`} />
      </Helmet>

      <div className="bg-primary py-4">
        <div className="max-w-7xl mx-auto px-4">
          <SearchBar variant="compact" />
        </div>
      </div>

      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <h1 className="font-heading text-xl font-bold text-gray-900 mb-6">
            {city ? `Hotels in ${city}` : 'Search Hotels'}
          </h1>
          <HotelResults
            key={searchKey}
            city={city}
            checkIn={checkIn}
            checkOut={checkOut}
            guests={guests}
          />
        </div>
      </div>
    </>
  )
}
