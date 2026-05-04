import { useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { hotelsApi } from '@/api/hotelsApi'
import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import ImageGallery from '@/components/hotel/ImageGallery'
import StarRating from '@/components/common/StarRating'
import Breadcrumb from '@/components/common/Breadcrumb'
import Skeleton from '@/components/common/Skeleton'
import { formatCurrency } from '@/utils/formatters'
import { MapPin, Wifi, Car, Dumbbell, UtensilsCrossed, Waves, Star, Calendar, Users, CheckCircle, X } from 'lucide-react'
import { format, addDays } from 'date-fns'
import { toast } from 'sonner'

const AMENITY_ICONS = { wifi: Wifi, parking: Car, gym: Dumbbell, restaurant: UtensilsCrossed, pool: Waves }

export default function LiteapiHotelDetailPage() {
  const { liteapiId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const setBookingData = useBookingStore((s) => s.setBookingData)

  const today = format(new Date(), 'yyyy-MM-dd')
  const tomorrow = format(addDays(new Date(), 1), 'yyyy-MM-dd')

  const urlCheckIn = searchParams.get('check_in')
  const urlCheckOut = searchParams.get('check_out')
  const urlGuests = searchParams.get('guests')
  const urlRooms = searchParams.get('rooms')

  const [checkIn, setCheckIn] = useState(urlCheckIn || today)
  const [checkOut, setCheckOut] = useState(urlCheckOut || tomorrow)
  const [guests, setGuests] = useState(parseInt(urlGuests || '1'))
  const [rooms, setRooms] = useState(parseInt(urlRooms || '1'))
  // Auto-show rates if dates were passed from search
  const [showRates, setShowRates] = useState(!!(urlCheckIn && urlCheckOut))

  const { data: hotel, isLoading } = useQuery({
    queryKey: ['liteapi-hotel', liteapiId],
    queryFn: () => hotelsApi.getLiteapi(liteapiId),
    select: (res) => res.data,
  })

  const {
    data: rates,
    isLoading: ratesLoading,
    refetch: fetchRates,
  } = useQuery({
    queryKey: ['liteapi-rates', liteapiId, checkIn, checkOut, guests],
    queryFn: () => hotelsApi.getRates(liteapiId, { check_in: checkIn, check_out: checkOut, guests }),
    select: (res) => res.data,
    enabled: showRates,
  })

  const handleSearchRates = () => {
    if (!checkIn || !checkOut || checkIn >= checkOut) {
      toast.error('Please select valid check-in and check-out dates')
      return
    }
    setShowRates(true)
    fetchRates()
  }

  const handleBookRate = (rate) => {
    if (!isAuthenticated) {
      navigate('/login?redirect=/hotels/liteapi/' + liteapiId)
      return
    }
    setBookingData({
      hotel: { ...hotel, source: 'liteapi', liteapi_hotel_id: liteapiId },
      selectedRoom: {
        id: rate.rate_id,
        name: rate.room_name,
        price_per_night: rate.price,
        currency: rate.currency,
        max_guests: rate.max_guests,
        images: rate.images || [],
        liteapi_rate_id: rate.rate_id,
        liteapi_price: rate.price,
        liteapi_hotel_id: liteapiId,
      },
      checkIn,
      checkOut,
      guests,
    })
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

  return (
    <>
      <Helmet>
        <title>{hotel.name} — TravelBooking</title>
        <meta name="description" content={`${hotel.name} — ${hotel.star_rating}-star hotel in ${hotel.city}, ${hotel.country}. Live rates available.`} />
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
                  <div className="flex items-center gap-2">
                    <h1 className="font-heading text-2xl md:text-3xl font-bold text-gray-900">{hotel.name}</h1>
                    <span className="bg-emerald-100 text-emerald-700 text-xs font-semibold px-2 py-0.5 rounded-full">Live rates</span>
                  </div>
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
            </div>

            {/* Amenities */}
            {hotel.amenities?.length > 0 && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-4">Amenities</h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {hotel.amenities.map((a, i) => {
                    const key = typeof a === 'string' ? a : a?.name || String(i)
                    const label = typeof a === 'string' ? a : a?.name || a
                    const Icon = AMENITY_ICONS[key?.toLowerCase()] || Star
                    return (
                      <div key={i} className="flex items-center gap-2 text-sm text-gray-700 capitalize">
                        <Icon className="w-4 h-4 text-primary" />{String(label).replace('_', ' ')}
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
                <p className="text-gray-600 text-sm leading-relaxed whitespace-pre-line text-justify">{hotel.description}</p>
              </div>
            )}

            {/* Rates */}
            <div>
              <h2 className="font-heading font-bold text-lg mb-4">Available Rooms & Rates</h2>

              {/* Date + Guest selector */}
              <div className="bg-gray-50 rounded-xl p-4 mb-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Check-in</label>
                  <input
                    type="date"
                    value={checkIn}
                    min={today}
                    onChange={(e) => { setCheckIn(e.target.value); setShowRates(false) }}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Check-out</label>
                  <input
                    type="date"
                    value={checkOut}
                    min={checkIn || today}
                    onChange={(e) => { setCheckOut(e.target.value); setShowRates(false) }}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Guests</label>
                  <input
                    type="number"
                    value={guests}
                    min={1}
                    max={10}
                    onChange={(e) => { setGuests(parseInt(e.target.value) || 1); setShowRates(false) }}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Rooms</label>
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      value={rooms}
                      min={1}
                      max={10}
                      onChange={(e) => setRooms(parseInt(e.target.value) || 1)}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    />
                    <button
                      type="button"
                      onClick={handleSearchRates}
                      className="bg-primary hover:bg-primary-dark text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors whitespace-nowrap"
                    >
                      Search
                    </button>
                  </div>
                </div>
              </div>

              {ratesLoading && (
                <div className="space-y-3">
                  {[1,2,3].map(i => <Skeleton key={i} className="h-24 rounded-xl" />)}
                </div>
              )}

              {!ratesLoading && showRates && rates?.length === 0 && (
                <p className="text-gray-400 text-sm">No rates available for the selected dates. Try different dates.</p>
              )}

              {!ratesLoading && rates?.map((rate, i) => (
                <div key={i} className="border rounded-xl p-4 mb-3 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                  <div className="flex-1">
                    <h3 className="font-semibold text-gray-900">{rate.room_name}</h3>
                    <div className="flex flex-wrap gap-3 mt-1 text-xs text-gray-500">
                      {rate.meal_type && <span>{rate.meal_type}</span>}
                      {rate.cancellation_policy && <span>{rate.cancellation_policy}</span>}
                      {rate.refundable && (
                        <span className="flex items-center gap-1 text-green-600">
                          <CheckCircle className="w-3 h-3" /> Refundable
                        </span>
                      )}
                      {!rate.refundable && (
                        <span className="flex items-center gap-1 text-orange-500">
                          <X className="w-3 h-3" /> Non-refundable
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Users className="w-3 h-3" /> Up to {rate.max_guests} guests
                      </span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xl font-bold text-gray-900">{formatCurrency(rate.price, rate.currency)}</p>
                    <p className="text-xs text-gray-400 mb-2">total stay</p>
                    <button
                      onClick={() => handleBookRate(rate)}
                      className="bg-accent hover:bg-accent-dark text-white font-semibold px-5 py-2 rounded-lg text-sm transition-colors"
                    >
                      Book now
                    </button>
                  </div>
                </div>
              ))}

              {!showRates && (
                <div className="text-center py-8 text-gray-400">
                  <Calendar className="w-10 h-10 mx-auto mb-2 opacity-40" />
                  <p className="text-sm">Select your dates and click "Search" to see available rooms.</p>
                </div>
              )}
            </div>
          </div>

          {/* Right sticky panel */}
          <div className="lg:col-span-1">
            <div className="sticky top-20 bg-white border rounded-xl p-5 shadow-sm space-y-4">
              <div className="text-center">
                <p className="text-3xl font-bold text-gray-900">
                  {hotel.min_room_price ? formatCurrency(hotel.min_room_price, hotel.currency) : '—'}
                </p>
                <p className="text-sm text-gray-500">starting per night</p>
              </div>
              <button
                onClick={handleSearchRates}
                className="w-full bg-primary hover:bg-primary-dark text-white font-bold py-3 rounded-lg transition-colors"
              >
                Check Availability
              </button>
              <ul className="text-xs text-gray-500 space-y-1">
                <li className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-success" /> Best price guarantee</li>
                <li className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-success" /> Powered by LiteAPI</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
