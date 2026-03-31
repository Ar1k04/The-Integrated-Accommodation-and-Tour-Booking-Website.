import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { toursApi } from '@/api/toursApi'
import { reviewsApi } from '@/api/reviewsApi'
import { useAuth } from '@/hooks/useAuth'
import ImageGallery from '@/components/hotel/ImageGallery'
import ReviewCard from '@/components/review/ReviewCard'
import ReviewForm from '@/components/review/ReviewForm'
import Breadcrumb from '@/components/common/Breadcrumb'
import Skeleton from '@/components/common/Skeleton'
import { formatCurrency, formatDate } from '@/utils/formatters'
import { format } from 'date-fns'
import {
  MapPin, Clock, Users, Star, Calendar, ChevronDown, ChevronUp,
  Check, X as XIcon, Minus, Plus,
} from 'lucide-react'

export default function TourDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const [participants, setParticipants] = useState(1)
  const [tourDate, setTourDate] = useState('')
  const [expandedDay, setExpandedDay] = useState(0)
  const [booking, setBooking] = useState(false)

  const { data: tour, isLoading } = useQuery({
    queryKey: ['tour', id],
    queryFn: () => toursApi.get(id),
    select: (res) => res.data,
  })

  const { data: reviewsData } = useQuery({
    queryKey: ['reviews', 'tour', id],
    queryFn: () => reviewsApi.listTourReviews(id, { per_page: 10 }),
    select: (res) => res.data,
  })

  const handleBook = async () => {
    if (!isAuthenticated) { navigate('/login'); return }
    if (!tourDate) { toast.error('Please select a tour date'); return }
    setBooking(true)
    try {
      const res = await toursApi.createBooking({
        tour_id: id,
        tour_date: tourDate,
        participants_count: participants,
      })
      toast.success('Tour booked successfully!')
      navigate(`/bookings/${res.data.id}/confirmation`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Booking failed')
    } finally {
      setBooking(false)
    }
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

  if (!tour) return <div className="text-center py-20 text-gray-400">Tour not found</div>

  const reviews = reviewsData?.items || []
  const itinerary = tour.itinerary || []
  const highlights = tour.highlights || []
  const includes = tour.includes || []
  const excludes = tour.excludes || []
  const totalPrice = tour.price_per_person * participants

  return (
    <>
      <Helmet>
        <title>{tour.name} — TravelBooking</title>
        <meta name="description" content={`${tour.name} in ${tour.city}, ${tour.country}. ${tour.duration_days} day tour from ${tour.price_per_person}/person.`} />
        <meta property="og:title" content={`${tour.name} — TravelBooking`} />
      </Helmet>
      <div className="max-w-7xl mx-auto px-4 py-4">
        <Breadcrumb items={[
          { label: 'Home', to: '/' },
          { label: 'Tours', to: '/tours' },
          { label: tour.name },
        ]} />

        <ImageGallery images={tour.images || []} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-8">
          <div className="lg:col-span-2 space-y-8">
            <div>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h1 className="font-heading text-2xl md:text-3xl font-bold text-gray-900">{tour.name}</h1>
                  <div className="flex flex-wrap items-center gap-3 mt-2 text-sm text-gray-500">
                    <span className="flex items-center gap-1"><MapPin className="w-4 h-4" />{tour.city}, {tour.country}</span>
                    <span className="flex items-center gap-1"><Clock className="w-4 h-4" />{tour.duration_days} day{tour.duration_days > 1 ? 's' : ''}</span>
                    <span className="flex items-center gap-1"><Users className="w-4 h-4" />Max {tour.max_participants} people</span>
                    {tour.category && (
                      <span className="bg-primary/10 text-primary text-xs font-semibold px-3 py-0.5 rounded-full capitalize">{tour.category}</span>
                    )}
                    {tour.owner_name && (
                      <span className="text-gray-500">by <span className="font-medium text-gray-700">{tour.owner_name}</span></span>
                    )}
                  </div>
                </div>
                {tour.avg_rating > 0 && (
                  <div className="text-right shrink-0">
                    <div className="bg-primary text-white font-bold text-lg px-3 py-1.5 rounded-lg">{tour.avg_rating.toFixed(1)}</div>
                    <p className="text-xs text-gray-500 mt-1">{tour.total_reviews} reviews</p>
                  </div>
                )}
              </div>
            </div>

            {tour.description && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-3">About This Tour</h2>
                <p className="text-gray-600 text-sm leading-relaxed whitespace-pre-line">{tour.description}</p>
              </div>
            )}

            {highlights.length > 0 && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-4">Highlights</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {highlights.map((h, i) => (
                    <div key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <Star className="w-4 h-4 text-warning shrink-0 mt-0.5" />
                      <span>{h}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {itinerary.length > 0 && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-4">Day-by-Day Itinerary</h2>
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
                          {day.description || day}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {includes.length > 0 && (
                <div>
                  <h2 className="font-heading font-bold text-lg mb-3">What's Included</h2>
                  <ul className="space-y-2">
                    {includes.map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                        <Check className="w-4 h-4 text-success shrink-0 mt-0.5" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {excludes.length > 0 && (
                <div>
                  <h2 className="font-heading font-bold text-lg mb-3">What's Not Included</h2>
                  <ul className="space-y-2">
                    {excludes.map((item, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                        <XIcon className="w-4 h-4 text-error shrink-0 mt-0.5" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div>
              <h2 className="font-heading font-bold text-lg mb-4">Reviews</h2>
              {reviews.length > 0 ? (
                <div className="space-y-5">
                  {reviews.map((r) => <ReviewCard key={r.id} review={r} />)}
                </div>
              ) : (
                <p className="text-gray-400 text-sm">No reviews yet. Be the first!</p>
              )}
              {isAuthenticated && <div className="mt-6"><ReviewForm tourId={id} /></div>}
            </div>
          </div>

          <div className="lg:col-span-1">
            <div className="sticky top-20 bg-white border rounded-xl p-5 shadow-sm space-y-5">
              <div className="text-center">
                <p className="text-3xl font-bold text-gray-900">{formatCurrency(tour.price_per_person)}</p>
                <p className="text-sm text-gray-500">per person</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Tour Date</label>
                <input
                  type="date"
                  value={tourDate}
                  onChange={(e) => setTourDate(e.target.value)}
                  min={format(new Date(), 'yyyy-MM-dd')}
                  className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Participants</label>
                <div className="flex items-center border rounded-lg">
                  <button
                    onClick={() => setParticipants(Math.max(1, participants - 1))}
                    className="px-3 py-2.5 hover:bg-gray-50 transition-colors"
                    aria-label="Decrease participants"
                  >
                    <Minus className="w-4 h-4" />
                  </button>
                  <span className="flex-1 text-center font-semibold">{participants}</span>
                  <button
                    onClick={() => setParticipants(Math.min(tour.max_participants, participants + 1))}
                    className="px-3 py-2.5 hover:bg-gray-50 transition-colors"
                    aria-label="Increase participants"
                  >
                    <Plus className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <hr />

              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">{formatCurrency(tour.price_per_person)} x {participants}</span>
                  <span className="font-semibold">{formatCurrency(totalPrice)}</span>
                </div>
                <div className="flex justify-between text-base font-bold pt-2 border-t">
                  <span>Total</span>
                  <span className="text-primary">{formatCurrency(totalPrice)}</span>
                </div>
              </div>

              <button
                onClick={handleBook}
                disabled={booking}
                className="w-full bg-accent hover:bg-accent-dark disabled:bg-gray-300 text-white font-bold py-3 rounded-lg transition-colors"
              >
                {booking ? 'Booking...' : 'Book Now'}
              </button>

              <ul className="text-xs text-gray-500 space-y-1">
                <li className="flex items-center gap-1"><Check className="w-3 h-3 text-success" /> Free cancellation up to 48h before</li>
                <li className="flex items-center gap-1"><Check className="w-3 h-3 text-success" /> Instant confirmation</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
