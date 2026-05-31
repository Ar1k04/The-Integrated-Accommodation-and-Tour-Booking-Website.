import { useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { toursApi } from '@/api/toursApi'
import { reviewsApi } from '@/api/reviewsApi'
import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import ImageGallery from '@/components/hotel/ImageGallery'
import OccupancySelector from '@/components/common/OccupancySelector'
import ReviewCard from '@/components/review/ReviewCard'
import ReviewForm from '@/components/review/ReviewForm'
import Pagination from '@/components/common/Pagination'
import Breadcrumb from '@/components/common/Breadcrumb'
import Skeleton from '@/components/common/Skeleton'
import { format, addDays } from 'date-fns'
import { toast } from 'sonner'
import {
  MapPin, Clock, Users, Star, Calendar, CheckCircle, X as XIcon,
  AlertCircle, ChevronDown, ChevronUp,
} from 'lucide-react'

// Default child pricing tiers (mirror backend DEFAULT_CHILD_AGE_TIERS). Only
// used for the right-hand price *preview* of tours WITHOUT age bands (legacy
// partner tours / Viator). Tours with age bands preview off their own band
// prices; the exact subtotal always comes from the backend at booking time.
const CHILD_TIERS = [
  { min: 0, max: 5, discount: 1.0 },
  { min: 6, max: 12, discount: 0.5 },
  { min: 13, max: 17, discount: 0.25 },
]
function childTierMultiplier(age) {
  for (const tier of CHILD_TIERS) {
    if (age >= tier.min && age <= tier.max) return 1 - tier.discount
  }
  return 1
}

const isAdultBand = (b) => String(b?.age_band || '').toUpperCase() === 'ADULT'

function adultBandPrice(tour) {
  const adult = (tour?.age_bands || []).find(isAdultBand)
  if (adult && adult.price != null) return adult.price
  return tour?.price_per_person || 0
}

// Per-person preview price for one child age. Returns null when the tour
// publishes age bands but the age matches none (caller shows a warning).
function childPreviewPrice(tour, age) {
  const childBands = (tour?.age_bands || []).filter((b) => !isAdultBand(b))
  if (childBands.length) {
    const sorted = [...childBands].sort((a, b) => a.start_age - b.start_age)
    for (const b of sorted) {
      if (age >= b.start_age && age <= b.end_age) return b.price != null ? b.price : adultBandPrice(tour)
    }
    return null
  }
  return adultBandPrice(tour) * childTierMultiplier(age)
}

export default function TourDetailPage() {
  const { id, code } = useParams()
  const isViator = Boolean(code)
  const tourKey = code || id
  const detailHref = isViator ? `/tours/viator/${code}` : `/tours/${id}`

  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const setBookingData = useBookingStore((s) => s.setBookingData)
  const { t } = useTranslation(['common', 'tours'])
  const fmt = useFormatCurrency()

  const today = format(new Date(), 'yyyy-MM-dd')
  const [tourDate, setTourDate] = useState(searchParams.get('tour_date') || format(addDays(new Date(), 7), 'yyyy-MM-dd'))
  const [adults, setAdults] = useState(parseInt(searchParams.get('adults') || searchParams.get('guests') || '1'))
  const [childAges, setChildAges] = useState(() => {
    const raw = searchParams.get('child_ages') || ''
    return raw
      ? raw.split(',').map((s) => parseInt(s, 10)).filter((n) => !Number.isNaN(n) && n >= 0 && n <= 17)
      : []
  })
  const participants = adults + childAges.length
  const childAgesParam = childAges.join(',')
  const [showAvailability, setShowAvailability] = useState(false)
  const [expandedDay, setExpandedDay] = useState(0)
  const [reviewPage, setReviewPage] = useState(1)
  const REVIEWS_PER_PAGE = 5

  const { data: tour, isLoading } = useQuery({
    queryKey: ['tour', isViator ? 'viator' : 'local', tourKey],
    queryFn: () => (isViator ? toursApi.getViator(code) : toursApi.get(id)),
    select: (res) => res.data,
    enabled: !!tourKey,
  })

  // Age-band aware child validation (applies to any tour that publishes bands —
  // now both Viator AND Partner). Child bands = anything that isn't ADULT.
  const childBands = (tour?.age_bands || []).filter((b) => !isAdultBand(b))
  const childAgeHint = childBands.length
    ? `This tour accepts children ages ${Math.min(...childBands.map((b) => b.start_age))}–${Math.max(...childBands.map((b) => b.end_age))}.`
    : null
  const unmatchedChildAges = childBands.length
    ? childAges.filter((age) => !childBands.some((b) => age >= b.start_age && age <= b.end_age))
    : []

  const {
    data: availability,
    isLoading: availLoading,
    refetch: fetchAvailability,
  } = useQuery({
    queryKey: ['tour-availability', isViator ? 'viator' : 'local', tourKey, tourDate, adults, childAgesParam],
    queryFn: () => {
      const params = { tour_date: tourDate, adults, child_ages: childAgesParam || undefined }
      return isViator ? toursApi.getViatorAvailability(code, params) : toursApi.getAvailability(id, params)
    },
    select: (res) => res.data,
    enabled: showAvailability,
  })

  const { data: reviewsData } = useQuery({
    queryKey: ['reviews', isViator ? 'viator-tour' : 'tour', tourKey, reviewPage],
    queryFn: () => (isViator
      ? reviewsApi.listViatorTourReviews(code, { page: reviewPage, per_page: REVIEWS_PER_PAGE })
      : reviewsApi.listTourReviews(id, { page: reviewPage, per_page: REVIEWS_PER_PAGE })),
    select: (res) => res.data,
    enabled: !!tourKey,
  })

  const handleCheckAvailability = () => {
    if (!tourDate) { toast.error(t('tours:errors.selectDate')); return }
    if (unmatchedChildAges.length > 0) {
      toast.error(`Ages ${unmatchedChildAges.join(', ')} aren't accepted on this tour.`)
      return
    }
    setShowAvailability(true)
    fetchAvailability()
  }

  const handleBook = () => {
    if (!isAuthenticated) {
      navigate('/login?redirect=' + detailHref)
      return
    }
    if (!tourDate) { toast.error(t('tours:errors.selectDate')); return }
    if (unmatchedChildAges.length > 0) {
      toast.error(`Ages ${unmatchedChildAges.join(', ')} aren't accepted on this tour.`)
      return
    }
    if (isViator) {
      const price = availability?.price || tour?.price_per_person || 0
      setBookingData({
        selectedTour: {
          id: code,
          name: tour?.name,
          price_per_person: price,
          city: tour?.city,
          images: tour?.images || [],
          viator_product_code: code,
          viator_price: price,
          source: 'viator',
        },
        tourDate,
        adults,
        childAges,
      })
    } else {
      setBookingData({ selectedTour: tour, tourDate, adults, childAges })
    }
    navigate('/bookings/new?type=tour')
  }

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 space-y-4">
        <Skeleton className="h-96 rounded-xl" />
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (!tour) return <div className="text-center py-20 text-gray-400">{t('tours:detail.notFound')}</div>

  const itinerary = tour.itinerary || []
  const highlights = tour.highlights || []
  const includes = tour.includes || []
  const excludes = tour.excludes || []
  const displayPrice = availability?.price || tour.price_per_person || 0
  // Preview total: once availability is checked the per-person price already
  // reflects the pax mix, so price × participants is exact. Before that, build
  // from age bands (Partner) or default tiers (legacy/Viator).
  const previewTotal = availability?.price
    ? availability.price * participants
    : adultBandPrice(tour) * adults + childAges.reduce((sum, age) => sum + (childPreviewPrice(tour, age) ?? 0), 0)

  return (
    <>
      <Helmet>
        <title>{tour.name} — TravelBooking</title>
        <meta name="description" content={`${tour.name} — ${tour.duration_days}-day tour in ${tour.city}.`} />
      </Helmet>

      <div className="max-w-7xl mx-auto px-4 py-4">
        <Breadcrumb items={[
          { label: t('common:common.home'), to: '/' },
          { label: t('nav.tours'), to: '/tours' },
          { label: tour.name },
        ]} />

        <ImageGallery images={tour.images || []} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-8">
          {/* Left column */}
          <div className="lg:col-span-2 space-y-8">
            <div>
              <div className="flex items-start gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h1 className="font-heading text-2xl md:text-3xl font-bold text-gray-900">{tour.name}</h1>
                    {isViator && (
                      <span className="bg-emerald-100 text-emerald-700 text-xs font-semibold px-2 py-0.5 rounded-full">{t('tours:detail.liveViaViator')}</span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-wrap mt-1">
                    {tour.category && (
                      <span className="inline-block bg-primary/10 text-primary text-xs font-medium px-2 py-0.5 rounded-full capitalize">
                        {tour.category}
                      </span>
                    )}
                    {tour.owner_name && (
                      <span className="text-sm text-gray-500">by <span className="font-medium text-gray-700">{tour.owner_name}</span></span>
                    )}
                  </div>
                </div>
                {tour.avg_rating > 0 && (
                  <div className="text-right shrink-0">
                    <div className="flex items-center gap-1">
                      <Star className="w-4 h-4 fill-warning text-warning" />
                      <span className="font-bold">{tour.avg_rating.toFixed(1)}</span>
                    </div>
                    <p className="text-xs text-gray-400">{tour.total_reviews} reviews</p>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-4 mt-3 text-sm text-gray-500">
                {tour.city && (
                  <span className="flex items-center gap-1">
                    <MapPin className="w-4 h-4" />{tour.city}{tour.country ? `, ${tour.country}` : ''}
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <Clock className="w-4 h-4" />{tour.duration_days} day{tour.duration_days > 1 ? 's' : ''}
                </span>
                <span className="flex items-center gap-1">
                  <Users className="w-4 h-4" />Up to {tour.max_participants} people
                </span>
              </div>
            </div>

            {/* Description */}
            {tour.description && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-3">{t('tours:detail.about')}</h2>
                <p className="text-gray-600 text-sm leading-relaxed whitespace-pre-line">{tour.description}</p>
              </div>
            )}

            {/* Highlights */}
            {highlights.length > 0 && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-3">{t('tours:detail.highlights')}</h2>
                <ul className="space-y-2">
                  {highlights.map((h, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <CheckCircle className="w-4 h-4 text-success shrink-0 mt-0.5" />
                      {typeof h === 'string' ? h : h?.text || String(h)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Itinerary (partner tours typically) */}
            {itinerary.length > 0 && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-4">{t('tours:detail.itinerary')}</h2>
                <div className="space-y-3">
                  {itinerary.map((day, i) => (
                    <div key={i} className="border rounded-xl overflow-hidden">
                      <button
                        onClick={() => setExpandedDay(expandedDay === i ? -1 : i)}
                        className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50 transition-colors"
                      >
                        <div className="flex items-center gap-3">
                          <span className="bg-primary text-white text-xs font-bold w-8 h-8 rounded-full flex items-center justify-center">
                            {i + 1}
                          </span>
                          <span className="font-semibold text-sm">{day.title || `Day ${i + 1}`}</span>
                        </div>
                        {expandedDay === i ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                      {expandedDay === i && (
                        <div className="px-4 pb-4 pl-16 text-sm text-gray-600 leading-relaxed">
                          {day.description || (typeof day === 'string' ? day : '')}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Includes / Excludes */}
            {(includes.length > 0 || excludes.length > 0) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {includes.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2 text-gray-900">{t('tours:detail.includesTitle')}</h3>
                    <ul className="space-y-1">
                      {includes.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                          <CheckCircle className="w-3.5 h-3.5 text-success shrink-0 mt-0.5" />
                          {typeof item === 'string' ? item : item?.text || String(item)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {excludes.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2 text-gray-900">{t('tours:detail.excludesTitle')}</h3>
                    <ul className="space-y-1">
                      {excludes.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                          <XIcon className="w-3.5 h-3.5 text-error shrink-0 mt-0.5" />
                          {typeof item === 'string' ? item : item?.text || String(item)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* Reviews */}
            {(() => {
              const reviews = reviewsData?.items || []
              const totalPages = reviewsData?.meta?.total_pages || 1
              return (
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="font-heading font-bold text-lg">{t('tours:detail.reviews')}</h2>
                    {isViator && tour.avg_rating > 0 && (
                      <div className="flex items-center gap-2">
                        <div className="flex items-center gap-1 bg-primary text-white px-2.5 py-1 rounded-lg">
                          <Star className="w-4 h-4 fill-current" />
                          <span className="font-bold">{tour.avg_rating.toFixed(1)}</span>
                        </div>
                        <span className="text-sm text-gray-500">
                          {tour.total_reviews} {t('tours:detail.viatorReviewsLabel')}
                        </span>
                      </div>
                    )}
                  </div>

                  {reviews.length > 0 ? (
                    <>
                      <div className="space-y-5">
                        {reviews.map((r) => <ReviewCard key={r.id} review={r} />)}
                      </div>
                      <Pagination
                        currentPage={reviewPage}
                        totalPages={totalPages}
                        onPageChange={(p) => { setReviewPage(p); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
                      />
                    </>
                  ) : (
                    <div className="text-center py-8 bg-gray-50 rounded-xl">
                      {isViator && tour.avg_rating > 0 ? (
                        <>
                          <Star className="w-8 h-8 mx-auto mb-2 text-warning opacity-50" />
                          <p className="text-gray-600 font-medium">
                            {t('tours:detail.viatorRatingNote', { rating: tour.avg_rating.toFixed(1), count: tour.total_reviews })}
                          </p>
                          <p className="text-xs text-gray-400 mt-1">{t('tours:detail.viatorReviewsSource')}</p>
                        </>
                      ) : (
                        <p className="text-gray-400 text-sm">{t('tours:detail.noReviews')}</p>
                      )}
                    </div>
                  )}

                  {isAuthenticated && (
                    <div className="mt-6">
                      {isViator
                        ? <ReviewForm viatorProductCode={code} />
                        : <ReviewForm tourId={id} />}
                    </div>
                  )}
                </div>
              )
            })()}

            {/* Availability checker — works for both sources */}
            <div>
              <h2 className="font-heading font-bold text-lg mb-4">{t('tours:detail.checkAvailability')}</h2>
              <div className="bg-gray-50 rounded-xl p-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">{t('tours:detail.tourDateLabel')}</label>
                  <input
                    type="date"
                    value={tourDate}
                    min={today}
                    onChange={(e) => setTourDate(e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">{t('tours:detail.participantsLabel')}</label>
                  <OccupancySelector
                    mode="tour"
                    adults={adults}
                    childAges={childAges}
                    onChange={({ adults: a, childAges: c }) => { setAdults(a); setChildAges(c) }}
                    maxAdults={tour.max_participants}
                  />
                </div>
                <div className="flex items-end">
                  <button
                    onClick={handleCheckAvailability}
                    className="w-full bg-primary hover:bg-primary-dark text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
                  >
                    {availLoading ? t('tours:detail.checking') : t('tours:detail.checkRates')}
                  </button>
                </div>
              </div>

              {childAgeHint && childAges.length > 0 && unmatchedChildAges.length > 0 && (
                <div className="mt-2 flex items-start gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2.5 py-1.5">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span>{childAgeHint}</span>
                </div>
              )}

              {showAvailability && !availLoading && availability && (
                <div className={`mt-3 p-4 rounded-xl border ${availability.available ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                  {availability.available ? (
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-green-700 font-semibold flex items-center gap-1.5">
                          <CheckCircle className="w-4 h-4" /> {t('tours:detail.availableOn', { date: tourDate })}
                        </p>
                        {availability.price > 0 && (
                          <p className="text-sm text-gray-600 mt-0.5">
                            {fmt(availability.price)} {t('common:common.perPerson')}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={handleBook}
                        className="bg-accent hover:bg-accent-dark text-white font-semibold px-6 py-2 rounded-lg text-sm transition-colors"
                      >
                        {t('common:common.bookNow')}
                      </button>
                    </div>
                  ) : (
                    <p className="text-red-700 font-semibold flex items-center gap-1.5">
                      <XIcon className="w-4 h-4" /> {t('tours:detail.notAvailableOnDate')}
                    </p>
                  )}
                </div>
              )}

              {!showAvailability && (
                <div className="mt-3 text-center py-6 text-gray-400">
                  <Calendar className="w-8 h-8 mx-auto mb-2 opacity-40" />
                  <p className="text-sm">{t('tours:detail.selectDateHint')}</p>
                </div>
              )}
            </div>
          </div>

          {/* Right sticky booking panel */}
          <div className="lg:col-span-1">
            <div className="sticky top-20 bg-white border rounded-xl p-5 shadow-sm space-y-4">
              <div className="text-center">
                <p className="text-3xl font-bold text-gray-900">{fmt(displayPrice)}</p>
                <p className="text-sm text-gray-500">{t('common:common.perPerson')}</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('tours:detail.tourDateLabel')}</label>
                <input
                  type="date"
                  value={tourDate}
                  min={today}
                  onChange={(e) => setTourDate(e.target.value)}
                  className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">{t('tours:detail.participantsLabel')}</label>
                <OccupancySelector
                  mode="tour"
                  adults={adults}
                  childAges={childAges}
                  onChange={({ adults: a, childAges: c }) => { setAdults(a); setChildAges(c) }}
                  maxAdults={tour.max_participants}
                />
              </div>

              <hr />

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">{fmt(displayPrice)} × {participants}</span>
                  <span className="font-semibold">{fmt(previewTotal)}</span>
                </div>
                <div className="flex justify-between text-base font-bold pt-2 border-t">
                  <span>{t('common:common.total')}</span>
                  <span className="text-primary">{fmt(previewTotal)}</span>
                </div>
              </div>

              <button
                onClick={handleBook}
                className="w-full bg-accent hover:bg-accent-dark text-white font-bold py-3 rounded-lg transition-colors"
              >
                {t('common:common.bookNow')}
              </button>
              <ul className="text-xs text-gray-500 space-y-1">
                {isViator ? (
                  <li className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-success" /> {t('tours:detail.poweredByViator')}</li>
                ) : (
                  <li className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-success" /> {t('tours:detail.freeCancellation48h')}</li>
                )}
                <li className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-success" /> {t('tours:detail.instantConfirmation')}</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
