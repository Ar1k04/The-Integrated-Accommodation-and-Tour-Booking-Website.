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
import ReviewCard from '@/components/review/ReviewCard'
import ReviewForm from '@/components/review/ReviewForm'
import Pagination from '@/components/common/Pagination'
import Breadcrumb from '@/components/common/Breadcrumb'
import Skeleton from '@/components/common/Skeleton'
import { format, addDays } from 'date-fns'
import { toast } from 'sonner'
import {
  MapPin, Clock, Users, Star, Calendar, CheckCircle, X as XIcon,
  Minus, Plus,
} from 'lucide-react'

export default function ViatorTourDetailPage() {
  const { code } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const setBookingData = useBookingStore((s) => s.setBookingData)
  const { t } = useTranslation(['common', 'tours'])
  const fmt = useFormatCurrency()

  const today = format(new Date(), 'yyyy-MM-dd')
  const [tourDate, setTourDate] = useState(searchParams.get('tour_date') || format(addDays(new Date(), 7), 'yyyy-MM-dd'))
  const [participants, setParticipants] = useState(parseInt(searchParams.get('guests') || '1'))
  const [showAvailability, setShowAvailability] = useState(false)
  const [reviewPage, setReviewPage] = useState(1)
  const REVIEWS_PER_PAGE = 5

  const { data: tour, isLoading } = useQuery({
    queryKey: ['viator-tour', code],
    queryFn: () => toursApi.getViator(code),
    select: (res) => res.data,
  })

  const {
    data: availability,
    isLoading: availLoading,
    refetch: fetchAvailability,
  } = useQuery({
    queryKey: ['viator-availability', code, tourDate, participants],
    queryFn: () => toursApi.getViatorAvailability(code, { tour_date: tourDate, guests: participants }),
    select: (res) => res.data,
    enabled: showAvailability,
  })

  const { data: reviewsData } = useQuery({
    queryKey: ['reviews', 'viator-tour', code, reviewPage],
    queryFn: () => reviewsApi.listViatorTourReviews(code, { page: reviewPage, per_page: REVIEWS_PER_PAGE }),
    select: (res) => res.data,
    enabled: !!code,
  })

  const handleCheckAvailability = () => {
    if (!tourDate) { toast.error(t('tours:errors.selectDate')); return }
    setShowAvailability(true)
    fetchAvailability()
  }

  const handleBook = () => {
    if (!isAuthenticated) {
      navigate('/login?redirect=/tours/viator/' + code)
      return
    }
    if (!tourDate) { toast.error(t('tours:errors.selectDate')); return }
    const price = availability?.price || tour?.price_per_person || 0
    setBookingData({
      selectedTour: {
        id: code,
        name: tour?.name,
        price_per_person: price,
        images: tour?.images || [],
        viator_product_code: code,
        viator_price: price,
        source: 'viator',
      },
      tourDate,
      guests: participants,
    })
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

  const displayPrice = availability?.price || tour.price_per_person || 0
  const totalPrice = displayPrice * participants

  return (
    <>
      <Helmet>
        <title>{tour.name} — TravelBooking</title>
        <meta name="description" content={`${tour.name} — ${tour.duration_days}-day tour in ${tour.city}. Book now with Viator.`} />
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
                    <span className="bg-emerald-100 text-emerald-700 text-xs font-semibold px-2 py-0.5 rounded-full">{t('tours:detail.liveViaViator')}</span>
                  </div>
                  {tour.category && (
                    <span className="inline-block mt-1 bg-primary/10 text-primary text-xs font-medium px-2 py-0.5 rounded-full capitalize">
                      {tour.category}
                    </span>
                  )}
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
                    <MapPin className="w-4 h-4" />{tour.city}
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
            {tour.highlights?.length > 0 && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-3">{t('tours:detail.highlights')}</h2>
                <ul className="space-y-2">
                  {tour.highlights.map((h, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <CheckCircle className="w-4 h-4 text-success shrink-0 mt-0.5" />
                      {typeof h === 'string' ? h : h?.text || String(h)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Includes / Excludes */}
            {(tour.includes?.length > 0 || tour.excludes?.length > 0) && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {tour.includes?.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2 text-gray-900">{t('tours:detail.includesTitle')}</h3>
                    <ul className="space-y-1">
                      {tour.includes.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                          <CheckCircle className="w-3.5 h-3.5 text-success shrink-0 mt-0.5" />
                          {typeof item === 'string' ? item : item?.text || String(item)}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {tour.excludes?.length > 0 && (
                  <div>
                    <h3 className="font-semibold mb-2 text-gray-900">{t('tours:detail.excludesTitle')}</h3>
                    <ul className="space-y-1">
                      {tour.excludes.map((item, i) => (
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
                    {tour.avg_rating > 0 && (
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
                      <Star className="w-8 h-8 mx-auto mb-2 text-warning opacity-50" />
                      {tour.avg_rating > 0 ? (
                        <>
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
                      <ReviewForm viatorProductCode={code} />
                    </div>
                  )}
                </div>
              )
            })()}

            {/* Availability checker */}
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
                  <div className="flex items-center border rounded-lg overflow-hidden">
                    <button
                      onClick={() => setParticipants(Math.max(1, participants - 1))}
                      className="px-3 py-2 hover:bg-gray-100 transition-colors"
                    >
                      <Minus className="w-4 h-4" />
                    </button>
                    <span className="flex-1 text-center text-sm font-medium py-2">{participants}</span>
                    <button
                      onClick={() => setParticipants(Math.min(tour.max_participants, participants + 1))}
                      className="px-3 py-2 hover:bg-gray-100 transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                    </button>
                  </div>
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
                <p className="text-3xl font-bold text-gray-900">
                  {fmt(displayPrice)}
                </p>
                <p className="text-sm text-gray-500">{t('common:common.perPerson')}</p>
                {participants > 1 && (
                  <p className="text-sm text-gray-400 mt-1">
                    {t('tours:detail.totalFor', { price: fmt(totalPrice), count: participants })}
                  </p>
                )}
              </div>
              <button
                onClick={handleBook}
                className="w-full bg-accent hover:bg-accent-dark text-white font-bold py-3 rounded-lg transition-colors"
              >
                {t('common:common.bookNow')}
              </button>
              <ul className="text-xs text-gray-500 space-y-1">
                <li className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-success" /> {t('tours:detail.poweredByViator')}</li>
                <li className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-success" /> {t('tours:detail.instantConfirmation')}</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
