import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { hotelsApi } from '@/api/hotelsApi'
import { roomsApi } from '@/api/roomsApi'
import { reviewsApi } from '@/api/reviewsApi'
import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import ImageGallery from '@/components/hotel/ImageGallery'
import RoomCard from '@/components/room/RoomCard'
import ReviewCard from '@/components/review/ReviewCard'
import ReviewForm from '@/components/review/ReviewForm'
import StarRating from '@/components/common/StarRating'
import Breadcrumb from '@/components/common/Breadcrumb'
import Skeleton from '@/components/common/Skeleton'
import { formatCurrency } from '@/utils/formatters'
import { MapPin, Wifi, Car, Dumbbell, UtensilsCrossed, Waves, Star } from 'lucide-react'

const AMENITY_ICONS = { wifi: Wifi, parking: Car, gym: Dumbbell, restaurant: UtensilsCrossed, pool: Waves }

export default function HotelDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const setBookingData = useBookingStore((s) => s.setBookingData)

  const { data: hotel, isLoading } = useQuery({
    queryKey: ['hotel', id],
    queryFn: () => hotelsApi.get(id),
    select: (res) => res.data,
  })

  const { data: rooms } = useQuery({
    queryKey: ['hotel-rooms', id],
    queryFn: () => roomsApi.listByHotel(id),
    select: (res) => res.data?.items || [],
  })

  const { data: reviewsData } = useQuery({
    queryKey: ['reviews', 'hotel', id],
    queryFn: () => reviewsApi.listHotelReviews(id, { per_page: 10 }),
    select: (res) => res.data,
  })

  const handleReserve = (room) => {
    setBookingData({ selectedRoom: room, hotel })
    navigate('/bookings/new')
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

  if (!hotel) return <div className="text-center py-20 text-gray-400">Hotel not found</div>

  const reviews = reviewsData?.items || []
  const cheapestRoom = rooms?.length
    ? rooms.reduce((min, r) => (min === null || r.price_per_night < min.price_per_night ? r : min), null)
    : null
  const startingPrice = cheapestRoom?.price_per_night

  return (
    <>
      <Helmet>
        <title>{hotel.name} — TravelBooking</title>
        <meta name="description" content={`${hotel.name} — ${hotel.star_rating}-star hotel in ${hotel.city}, ${hotel.country}. Browse available rooms and reserve your stay.`} />
        <meta property="og:title" content={`${hotel.name} — TravelBooking`} />
      </Helmet>
      <div className="max-w-7xl mx-auto px-4 py-4">
        <Breadcrumb items={[
          { label: 'Home', to: '/' },
          { label: 'Hotels', to: '/hotels/search' },
          { label: hotel.name },
        ]} />

        <ImageGallery images={hotel.images || []} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-8">
          {/* Left */}
          <div className="lg:col-span-2 space-y-8">
            <div>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h1 className="font-heading text-2xl md:text-3xl font-bold text-gray-900">{hotel.name}</h1>
                  <div className="flex items-center gap-3 mt-2">
                    <StarRating rating={hotel.star_rating} />
                    {hotel.property_type && (
                      <span className="bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded-full">{hotel.property_type}</span>
                    )}
                  </div>
                </div>
                {hotel.avg_rating > 0 && (
                  <div className="text-right shrink-0">
                    <div className="bg-primary text-white font-bold text-lg px-3 py-1.5 rounded-lg">{hotel.avg_rating.toFixed(1)}</div>
                    <p className="text-xs text-gray-500 mt-1">{hotel.total_reviews} reviews</p>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-1.5 mt-3 text-gray-500 text-sm">
                <MapPin className="w-4 h-4" />{hotel.address || `${hotel.city}, ${hotel.country}`}
              </div>
              {hotel.owner_name && (
                <p className="mt-1 text-sm text-gray-500">Managed by <span className="font-medium text-gray-700">{hotel.owner_name}</span></p>
              )}
            </div>

            {/* Amenities */}
            {hotel.amenities?.length > 0 && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-4">Amenities</h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {hotel.amenities.map((a) => {
                    const Icon = AMENITY_ICONS[a] || Star
                    return (
                      <div key={a} className="flex items-center gap-2 text-sm text-gray-700 capitalize">
                        <Icon className="w-4 h-4 text-primary" />{a.replace('_', ' ')}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Description */}
            {hotel.description && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-3">About this hotel</h2>
                <p className="text-gray-600 text-sm leading-relaxed whitespace-pre-line">{hotel.description}</p>
              </div>
            )}

            {/* Rooms */}
            <div>
              <h2 className="font-heading font-bold text-lg mb-4">Available Rooms</h2>
              <div className="space-y-4">
                {rooms?.map((room) => (
                  <RoomCard key={room.id} room={room} onReserve={handleReserve} />
                ))}
                {rooms?.length === 0 && <p className="text-gray-400 text-sm">No rooms available for selected dates.</p>}
              </div>
            </div>

            {/* Reviews */}
            <div>
              <h2 className="font-heading font-bold text-lg mb-4">Guest Reviews</h2>
              {reviews.length > 0 ? (
                <div className="space-y-5">
                  {reviews.map((r) => <ReviewCard key={r.id} review={r} />)}
                </div>
              ) : (
                <p className="text-gray-400 text-sm">No reviews yet. Be the first!</p>
              )}
              {isAuthenticated && <div className="mt-6"><ReviewForm hotelId={id} /></div>}
            </div>
          </div>

          {/* Right sticky booking panel */}
          <div className="lg:col-span-1">
            <div className="sticky top-20 bg-white border rounded-xl p-5 shadow-sm space-y-4">
              <div className="text-center">
                <p className="text-3xl font-bold text-gray-900">
                  {startingPrice ? formatCurrency(startingPrice, hotel.currency) : '—'}
                </p>
                <p className="text-sm text-gray-500">starting per night</p>
              </div>
              <button
                onClick={() => cheapestRoom && handleReserve(cheapestRoom)}
                disabled={!cheapestRoom}
                className="w-full bg-accent hover:bg-accent-dark text-white font-bold py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Reserve Now
              </button>
              <ul className="text-xs text-gray-500 space-y-1">
                <li className="flex items-center gap-1"><Star className="w-3 h-3 text-success" /> Free cancellation</li>
                <li className="flex items-center gap-1"><Star className="w-3 h-3 text-success" /> No prepayment needed</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
