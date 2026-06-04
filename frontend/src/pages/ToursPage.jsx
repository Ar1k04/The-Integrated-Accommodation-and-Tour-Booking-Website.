import { useState, useMemo, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { toursApi } from '@/api/toursApi'
import TourCard from '@/components/tour/TourCard'
import TourFilters from '@/components/tour/TourFilters'
import { TourCardSkeleton } from '@/components/common/Skeleton'
import Pagination from '@/components/common/Pagination'
import { SlidersHorizontal, ArrowUpDown, X, MapPin, Search } from 'lucide-react'

const EMPTY_FILTERS = {
  min_price: null,
  max_price: null,
  city: '',
  tags: [],
  flags: [],
  rating_min: null,
  duration_min: null,
  duration_max: null,
  start_date: '',
  end_date: '',
}

export default function ToursPage() {
  const [params] = useSearchParams()
  const { t } = useTranslation(['tours', 'common'])
  const [showFilters, setShowFilters] = useState(false)
  const [sort, setSort] = useState('created_at')
  const [searchText, setSearchText] = useState(params.get('q') || '')
  const [submittedSearch, setSubmittedSearch] = useState(params.get('q') || '')
  // Travel dates seed from the main-page tour search bar (?start_date/&end_date);
  // left empty when the search bar had no dates picked.
  const [filters, setFilters] = useState({
    ...EMPTY_FILTERS,
    city: params.get('city') || '',
    start_date: params.get('start_date') || '',
    end_date: params.get('end_date') || '',
  })
  const [page, setPage] = useState(1)

  const SORT_OPTIONS = [
    { label: t('common:sort.recommended'), value: 'created_at' },
    { label: t('common:sort.priceLowHigh'), value: 'price_per_person:asc' },
    { label: t('common:sort.priceHighLow'), value: 'price_per_person:desc' },
    { label: t('common:sort.rating'), value: 'avg_rating:desc' },
    { label: t('common:sort.duration'), value: 'duration_days:asc' },
  ]

  const [sortBy, sortOrder] = sort.includes(':') ? sort.split(':') : [sort, 'desc']

  // Hero search bar Nominatim
  const [debouncedHero, setDebouncedHero] = useState('')
  const [showHeroSuggestions, setShowHeroSuggestions] = useState(false)
  const heroInputRef = useRef(null)

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedHero(searchText), 300)
    return () => clearTimeout(timer)
  }, [searchText])

  const { data: heroSuggestions = [], isFetching: isFetchingHero } = useQuery({
    queryKey: ['tour-hero-viator-destinations', debouncedHero],
    queryFn: () =>
      toursApi
        .searchViatorDestinations(debouncedHero, 10)
        .then((r) => r.data?.destinations || []),
    enabled: debouncedHero.length >= 2,
    staleTime: 5 * 60_000,
  })

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (heroInputRef.current && !heroInputRef.current.contains(e.target)) {
        setShowHeroSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const isFirstRender = useRef(true)
  const queryParams = useMemo(() => ({
    q: submittedSearch || undefined,
    city: filters.city || undefined,
    min_price: filters.min_price || undefined,
    max_price: filters.max_price || undefined,
    tags: filters.tags?.length ? filters.tags : undefined,
    flags: filters.flags?.length ? filters.flags : undefined,
    rating_min: filters.rating_min ?? undefined,
    duration_min: filters.duration_min ?? undefined,
    duration_max: filters.duration_max ?? undefined,
    start_date: filters.start_date || undefined,
    end_date: filters.end_date || undefined,
    sort_by: sortBy,
    sort_order: sortOrder,
    per_page: 30,
  }), [submittedSearch, filters, sortBy, sortOrder])

  // Reset to page 1 whenever filters/sort/search change.
  useEffect(() => {
    setPage(1)
    if (isFirstRender.current) { isFirstRender.current = false; return }
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [queryParams])

  const handleSearch = () => {
    if (searchText) {
      setFilters((f) => ({ ...f, city: '' }))
    }
    setSubmittedSearch(searchText)
  }

  const handleCityFilterChange = (city) => {
    setFilters((f) => ({ ...f, city }))
    setSearchText('')
    setSubmittedSearch('')
  }

  const resetAll = () => {
    setFilters({ ...EMPTY_FILTERS })
    setSearchText('')
    setSubmittedSearch('')
  }

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['tours-search', queryParams, page],
    queryFn: () => toursApi.list({ ...queryParams, page }),
    placeholderData: keepPreviousData,
  })

  const tours = data?.data?.items || []
  const meta = data?.data?.meta
  const total = meta?.total || 0
  const totalPages = meta?.total_pages || 1

  const handlePageChange = (next) => {
    if (next < 1 || next > totalPages || next === page) return
    setPage(next)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  return (
    <>
      <Helmet>
        <title>Explore Tours — TravelBooking</title>
        <meta name="description" content="Discover amazing tours and activities around the world. Adventure, cultural, beach, city tours and more." />
        <meta property="og:title" content="Explore Tours — TravelBooking" />
      </Helmet>

      <div className="bg-gradient-to-r from-primary to-primary-dark text-white py-12 md:py-16">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <h1 className="font-heading text-3xl md:text-4xl font-bold mb-3">{t('tours:page.exploreTitle')}</h1>
          <p className="text-white/80 max-w-xl mx-auto mb-8">{t('tours:page.exploreSubtitle')}</p>
          <div className="max-w-xl mx-auto flex gap-2">
            <div className="flex-1 relative" ref={heroInputRef}>
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-white/60 z-10" />
              <input
                value={searchText}
                onChange={(e) => { setSearchText(e.target.value); setShowHeroSuggestions(true) }}
                onFocus={() => searchText.length >= 2 && setShowHeroSuggestions(true)}
                onKeyDown={(e) => { if (e.key === 'Enter') { setShowHeroSuggestions(false); handleSearch() } }}
                placeholder={t('tours:page.searchPlaceholder')}
                className="w-full pl-10 pr-4 py-3 rounded-lg bg-white/15 text-white placeholder-white/60 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              />
              {showHeroSuggestions && (isFetchingHero || heroSuggestions.length > 0) && (
                <ul className="absolute z-50 top-full left-0 right-0 mt-1 bg-white rounded-lg shadow-xl border overflow-hidden max-h-60 overflow-y-auto text-left">
                  {isFetchingHero && heroSuggestions.length === 0 && (
                    <li className="px-4 py-2.5 text-sm text-gray-400">{t('common:common.loading')}</li>
                  )}
                  {heroSuggestions.map((s) => (
                    <li
                      key={s.destination_id}
                      onMouseDown={() => {
                        handleCityFilterChange(s.name)
                        setSearchText(s.name)
                        setShowHeroSuggestions(false)
                      }}
                      className="flex items-center gap-2 px-4 py-2.5 text-sm text-gray-800 cursor-pointer hover:bg-primary/5"
                    >
                      <MapPin className="w-4 h-4 text-primary shrink-0" />
                      <span className="font-medium">{s.name}</span>
                      {s.type && (
                        <span className="text-gray-400 text-xs uppercase tracking-wide">{s.type}</span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <button
              onClick={() => { setShowHeroSuggestions(false); handleSearch() }}
              className="bg-accent hover:bg-accent-dark text-white font-semibold px-5 py-3 rounded-lg text-sm transition-colors flex items-center gap-2 shrink-0"
            >
              <Search className="w-4 h-4" />
              {t('common:common.search')}
            </button>
          </div>
        </div>
      </div>

      <div className="bg-surface min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-heading text-xl font-bold text-gray-900">
              {t('tours:page.toursFound', { count: total })}
            </h2>
            <button onClick={() => setShowFilters(!showFilters)}
              className="md:hidden flex items-center gap-2 text-sm font-medium text-primary">
              <SlidersHorizontal className="w-4 h-4" /> {t('tours:page.filters.title')}
            </button>
          </div>

          <div className="flex gap-6">
            <div className={`${showFilters ? 'fixed inset-0 z-50 bg-white p-4 overflow-y-auto md:static md:bg-transparent' : 'hidden'} md:block w-full md:w-64 shrink-0`}>
              <div className="flex items-center justify-between mb-4 md:hidden">
                <h2 className="font-bold text-lg">{t('tours:page.filters.title')}</h2>
                <button onClick={() => setShowFilters(false)}><X className="w-5 h-5" /></button>
              </div>
              <TourFilters filters={filters} onChange={setFilters} onClear={resetAll} />
            </div>

            <div className="flex-1 min-w-0">
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

              <div className={`grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5 ${isFetching && !isLoading ? 'opacity-60 transition-opacity' : ''}`}>
                {isLoading
                  ? Array.from({ length: 30 }, (_, i) => <TourCardSkeleton key={i} />)
                  : tours.map((tour) => (
                      <TourCard
                        key={tour.viator_product_code || String(tour.id)}
                        tour={tour}
                      />
                    ))
                }
              </div>
              {!isLoading && tours.length === 0 && (
                <div className="text-center py-20">
                  <p className="text-gray-400 text-lg mb-2">{t('tours:page.noResults')}</p>
                  <p className="text-gray-400 text-sm">{t('tours:page.tryAdjusting')}</p>
                </div>
              )}
              {!isLoading && totalPages > 1 && (
                <Pagination
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={handlePageChange}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
