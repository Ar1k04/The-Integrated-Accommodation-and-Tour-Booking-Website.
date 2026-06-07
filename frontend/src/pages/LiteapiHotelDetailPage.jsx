import { useState, useRef, useMemo, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { hotelsApi } from '@/api/hotelsApi'
import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import ImageGallery from '@/components/hotel/ImageGallery'
import AvailabilityTable from '@/components/room/AvailabilityTable'
import RoomRecommendation from '@/components/room/RoomRecommendation'
import { recommendCombination } from '@/utils/roomRecommender'
import ReviewCard from '@/components/review/ReviewCard'
import ReviewForm from '@/components/review/ReviewForm'
import StarRating from '@/components/common/StarRating'
import Breadcrumb from '@/components/common/Breadcrumb'
import Skeleton from '@/components/common/Skeleton'
import FacilitiesSection from '@/components/hotel/FacilitiesSection'
import OccupancySelector from '@/components/hotel/OccupancySelector'
import HotelMiniMap from '@/components/hotel/HotelMiniMap'
import NearbyHotelsMapModal from '@/components/hotel/NearbyHotelsMapModal'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { MapPin, CalendarDays, Users, CheckCircle, Search, Star } from 'lucide-react'
import { format, differenceInDays } from 'date-fns'

export default function LiteapiHotelDetailPage() {
  const { liteapiId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const { t } = useTranslation(['hotels', 'common'])
  const setBookingData = useBookingStore((s) => s.setBookingData)
  const datePickerRef = useRef(null)

  const today = format(new Date(), 'yyyy-MM-dd')

  const [checkIn, setCheckIn] = useState(searchParams.get('check_in') || '')
  const [checkOut, setCheckOut] = useState(searchParams.get('check_out') || '')
  const [adults, setAdults] = useState(parseInt(searchParams.get('adults') || searchParams.get('guests') || '2'))
  const [childAges, setChildAges] = useState(() => {
    const raw = searchParams.get('child_ages') || ''
    return raw
      ? raw.split(',').map((s) => parseInt(s, 10)).filter((n) => !Number.isNaN(n) && n >= 0 && n <= 17)
      : []
  })
  const [rooms, setRooms] = useState(parseInt(searchParams.get('rooms') || '1'))
  const guests = adults + childAges.length
  const childAgesParam = childAges.join(',')
  const [reviewPage, setReviewPage] = useState(1)
  const [mapOpen, setMapOpen] = useState(false)
  const REVIEWS_PER_PAGE = 5

  const datesSelected = !!(checkIn && checkOut)

  const { data: hotel, isLoading } = useQuery({
    queryKey: ['liteapi-hotel', liteapiId],
    queryFn: () => hotelsApi.getLiteapi(liteapiId),
    select: (res) => res.data,
  })

  // Live rates with multi-rate-plan grouping (when dates picked).
  const { data: liteapiRates } = useQuery({
    queryKey: ['liteapi-rates', liteapiId, checkIn, checkOut, adults, childAgesParam, rooms],
    queryFn: () =>
      hotelsApi.getRates(liteapiId, {
        check_in: checkIn,
        check_out: checkOut,
        adults,
        child_ages: childAgesParam || undefined,
        guests,
        rooms,
      }),
    select: (res) => res.data || [],
    enabled: datesSelected,
  })

  // Room-type catalog (no prices) — used for the no-dates state.
  const { data: liteapiCatalog } = useQuery({
    queryKey: ['liteapi-room-types', liteapiId],
    queryFn: () => hotelsApi.getLiteapiRoomTypes(liteapiId),
    select: (res) => res.data || [],
    enabled: !datesSelected,
    staleTime: 60 * 60 * 1000,
  })

  // Guest reviews proxied from LiteAPI.
  const { data: liteapiReviews } = useQuery({
    queryKey: ['liteapi-reviews', liteapiId],
    queryFn: () => hotelsApi.getLiteapiReviews(liteapiId, { limit: 20 }),
    select: (res) => res.data?.items || [],
    staleTime: 60 * 60 * 1000,
  })

  const fmt = useFormatCurrency()

  const handleShowPrices = () => {
    if (datePickerRef.current) {
      datePickerRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
      datePickerRef.current.classList.add('ring-4', 'ring-amber-400')
      setTimeout(() => {
        datePickerRef.current?.classList.remove('ring-4', 'ring-amber-400')
      }, 1500)
    }
  }

  const handleReserve = (group, quantities) => {
    if (!isAuthenticated) {
      navigate('/login?redirect=/hotels/liteapi/' + liteapiId)
      return
    }
    const items = Object.entries(quantities)
      .filter(([, n]) => n > 0)
      .map(([rate_id, n]) => {
        const rate = group.rates.find((r) => r.rate_id === rate_id)
        return {
          rate_id,
          quantity: n,
          price: rate?.price,
          board_name: rate?.board_name,
          refundable: rate?.refundable,
          liteapi_rate_id: rate_id,
        }
      })
    if (items.length === 0) return

    setBookingData({
      hotel: { ...hotel, source: 'liteapi', liteapi_hotel_id: liteapiId },
      selectedRoomGroup: { id: group.id, name: group.name, max_guests: group.max_guests },
      selectedItems: items,
      selectedRoom: {
        id: items[0].rate_id,
        name: group.name,
        price_per_night: items[0].price,
        currency: group.rates[0]?.currency || 'USD',
        max_guests: group.max_guests,
        images: group.images || [],
        liteapi_rate_id: items[0].rate_id,
        liteapi_price: items[0].price,
        liteapi_hotel_id: liteapiId,
      },
      checkIn,
      checkOut,
      adults,
      childAges,
      rooms,
    })
    navigate('/bookings/new')
  }

  // Must be declared before any early returns to satisfy Rules of Hooks.
  const [tableSelections, setTableSelections] = useState({})
  useEffect(() => { setTableSelections({}) }, [checkIn, checkOut, adults, childAgesParam, rooms])

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

  if (!hotel) return <div className="text-center py-20 text-gray-400">{t('hotels:detail.notFound')}</div>

  const sourceList = datesSelected ? liteapiRates : liteapiCatalog
  const roomGroups = (sourceList || []).map((rt) => ({
    id: rt.room_type_id,
    name: rt.room_name,
    room_type: rt.room_name,
    max_guests: rt.max_guests,
    total_quantity: null,
    amenities: rt.amenities || [],
    images: rt.images || [],
    rates: (rt.rates || []).map((r) => ({
      rate_id: r.rate_id,
      board_name: r.board_name,
      refundable: r.refundable,
      cancellation_deadline: r.cancellation_deadline,
      price: r.price,
      price_excl_taxes: r.price_excl_taxes,
      taxes: r.taxes,
      original_price: r.original_price,
      discount_percent: r.discount_percent,
      currency: r.currency,
      max_occupancy: r.max_occupancy,
      adult_count: r.adult_count,
      child_count: r.child_count,
      children_ages: r.children_ages,
      occupancy_number: r.occupancy_number,
    })),
  }))

  const nights = datesSelected ? differenceInDays(new Date(checkOut), new Date(checkIn)) : 0
  const recommendation = datesSelected
    ? recommendCombination(roomGroups, { adults, childAges, rooms, nights })
    : null

  let _selTotal = 0
  for (const [groupId, rateQtys] of Object.entries(tableSelections)) {
    const group = roomGroups.find((g) => String(g.id) === String(groupId))
    if (!group) continue
    for (const [rateId, q] of Object.entries(rateQtys)) {
      if (!q) continue
      const rate = group.rates.find((r) => r.rate_id === rateId)
      if (rate?.price) _selTotal += rate.price * q * Math.max(nights, 1)
    }
  }
  const selectedTotal = _selTotal > 0 ? _selTotal : null

  const selectedRoomsCount = Object.values(tableSelections).reduce(
    (sum, rateQtys) => sum + Object.values(rateQtys).reduce((s, n) => s + (n || 0), 0),
    0
  )

  const handleReserveSelected = () => {
    if (!isAuthenticated) {
      navigate('/login?redirect=/hotels/liteapi/' + liteapiId)
      return
    }
    const allItems = []
    for (const [groupId, rateQtys] of Object.entries(tableSelections)) {
      const group = roomGroups.find((g) => String(g.id) === String(groupId))
      if (!group) continue
      for (const [rateId, q] of Object.entries(rateQtys)) {
        if (!q) continue
        const rate = group.rates.find((r) => r.rate_id === rateId)
        if (rate) allItems.push({ group, rate, quantity: q, perUnitGuests: [] })
      }
    }
    if (allItems.length === 0) return
    if (allItems.length === 1) {
      handleReserve(allItems[0].group, { [allItems[0].rate.rate_id]: allItems[0].quantity })
    } else {
      handleReserveCombination(allItems)
    }
  }

  const handleReserveCombination = (items) => {
    if (!isAuthenticated) {
      navigate('/login?redirect=/hotels/liteapi/' + liteapiId)
      return
    }
    const storeItems = items.map((it) => ({
      rate_id: it.rate.rate_id,
      quantity: it.quantity,
      price: it.rate.price,
      board_name: it.rate.board_name,
      refundable: it.rate.refundable,
      room_name: it.group.name,
      max_guests: it.group.max_guests,
      per_unit_guests: it.perUnitGuests,
      liteapi_rate_id: it.rate.rate_id,
    }))
    setBookingData({
      hotel: { ...hotel, source: 'liteapi', liteapi_hotel_id: liteapiId },
      selectedRoomGroup: null,
      selectedItems: storeItems,
      selectedRoom: {
        id: storeItems[0].rate_id,
        name: storeItems[0].room_name,
        price_per_night: storeItems[0].price,
        currency: items[0].rate.currency || 'USD',
        max_guests: storeItems[0].max_guests,
        images: items[0].group.images || [],
        liteapi_rate_id: storeItems[0].rate_id,
        liteapi_price: storeItems[0].price,
        liteapi_hotel_id: liteapiId,
      },
      checkIn,
      checkOut,
      adults,
      childAges,
      rooms,
    })
    navigate('/bookings/new')
  }

  const allPrices = roomGroups.flatMap((g) => (g.rates || []).map((r) => r.price)).filter((p) => p > 0)
  const startingPrice = allPrices.length ? Math.min(...allPrices) : hotel.min_room_price || null

  return (
    <>
      <Helmet>
        <title>{hotel.name} — TravelBooking</title>
        <meta name="description" content={`${hotel.name} — ${hotel.star_rating}-star hotel in ${hotel.city}, ${hotel.country}. Live rates available.`} />
      </Helmet>

      <div className="max-w-7xl mx-auto px-4 py-4">
        <Breadcrumb items={[
          { label: t('common:common.home'), to: '/' },
          { label: t('common:nav.hotels'), to: '/hotels/search' },
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
                    <span className="bg-emerald-100 text-emerald-700 text-xs font-semibold px-2 py-0.5 rounded-full">{t('hotels:detail.liveRates')}</span>
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
                    <p className="text-xs text-gray-500 mt-1">{t('hotels:detail.reviewsCount', { count: hotel.total_reviews })}</p>
                  </div>
                )}
              </div>
              <div className="flex items-center gap-1.5 mt-3 text-gray-500 text-sm">
                <MapPin className="w-4 h-4" />{hotel.address || `${hotel.city}, ${hotel.country}`}
              </div>
            </div>

            {hotel.description && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-3">{t('hotels:detail.about')}</h2>
                <p className="text-gray-600 text-sm leading-relaxed whitespace-pre-line">{hotel.description}</p>
              </div>
            )}

            <FacilitiesSection amenities={hotel.amenities} />

            {/* Reviews — our guests' reviews (after a completed stay) merged
                ahead of LiteAPI's own feed. Authenticated guests can post one
                at the bottom; the backend rejects it unless they completed a
                stay at this hotel. Paginated 5 per page. */}
            <div>
              <h2 className="font-heading font-bold text-lg mb-4">{t('hotels:detail.guestReviews')}</h2>
              {liteapiReviews && liteapiReviews.length > 0 ? (
                <>
                  <div className="space-y-5">
                    {liteapiReviews
                      .slice((reviewPage - 1) * REVIEWS_PER_PAGE, reviewPage * REVIEWS_PER_PAGE)
                      .map((r) => <ReviewCard key={r.id} review={r} />)}
                  </div>
                  {liteapiReviews.length > REVIEWS_PER_PAGE && (
                    <div className="flex items-center justify-center gap-3 mt-6">
                      <button
                        type="button"
                        onClick={() => setReviewPage((p) => Math.max(1, p - 1))}
                        disabled={reviewPage === 1}
                        className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        {t('common:common.back')}
                      </button>
                      <span className="text-sm text-gray-600">
                        {reviewPage} / {Math.ceil(liteapiReviews.length / REVIEWS_PER_PAGE)}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          setReviewPage((p) =>
                            Math.min(Math.ceil(liteapiReviews.length / REVIEWS_PER_PAGE), p + 1)
                          )
                        }
                        disabled={reviewPage >= Math.ceil(liteapiReviews.length / REVIEWS_PER_PAGE)}
                        className="px-3 py-1.5 text-sm border rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        {t('common:common.next')}
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-gray-400 text-sm">{t('hotels:detail.noReviews')}</p>
              )}
              {isAuthenticated && (
                <div className="mt-6"><ReviewForm liteapiHotelId={liteapiId} /></div>
              )}
            </div>

            {/* Availability section */}
            <div>
              <h2 className="font-heading font-bold text-xl mb-4">{t('hotels:detail.rooms')}</h2>

              {/* Booking.com-style date search bar */}
              <div
                ref={datePickerRef}
                className="rounded-xl p-3 mb-5 flex flex-col sm:flex-row items-stretch sm:items-end gap-3 transition-all duration-300"
                style={{ border: '2px solid #febb02', backgroundColor: '#febb0208' }}
              >
                <div className="flex-1 min-w-0">
                  <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 mb-1">
                    <CalendarDays className="w-3.5 h-3.5 text-gray-500" />
                    {t('hotels:detail.checkIn')}
                  </label>
                  <input
                    type="date"
                    value={checkIn}
                    min={today}
                    onChange={(e) => setCheckIn(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 mb-1">
                    <CalendarDays className="w-3.5 h-3.5 text-gray-500" />
                    {t('hotels:detail.checkOut')}
                  </label>
                  <input
                    type="date"
                    value={checkOut}
                    min={checkIn || today}
                    onChange={(e) => setCheckOut(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
                  />
                </div>
                <div className="sm:w-72">
                  <label className="flex items-center gap-1.5 text-xs font-semibold text-gray-700 mb-1">
                    <Users className="w-3.5 h-3.5 text-gray-500" />
                    {t('hotels:detail.guests')}
                  </label>
                  <OccupancySelector
                    adults={adults}
                    childAges={childAges}
                    rooms={rooms}
                    onChange={({ adults: a, childAges: c, rooms: r }) => {
                      setAdults(a)
                      setChildAges(c)
                      setRooms(r)
                    }}
                  />
                </div>
                <div className="sm:w-auto">
                  <label className="block text-xs font-semibold text-transparent mb-1 select-none sm:block hidden">&nbsp;</label>
                  <button
                    type="button"
                    className="w-full sm:w-auto bg-primary hover:bg-primary-dark text-white font-bold px-6 py-2 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 whitespace-nowrap"
                  >
                    <Search className="w-4 h-4" />
                    {datesSelected ? t('hotels:detail.changeSearch') : t('hotels:detail.searchBtn')}
                  </button>
                </div>
              </div>

              {datesSelected && (rooms > 1 || guests > 2) && recommendation && (
                <RoomRecommendation
                  recommendation={recommendation}
                  nights={nights}
                  guests={guests}
                  adults={adults}
                  children={childAges.length}
                  fmt={fmt}
                  onReserve={handleReserveCombination}
                />
              )}

              <AvailabilityTable
                key={`${checkIn}:${checkOut}:${guests}:${rooms}`}
                roomGroups={roomGroups}
                checkIn={checkIn}
                checkOut={checkOut}
                onReserve={handleReserve}
                onShowPrices={handleShowPrices}
                onSelectionChange={setTableSelections}
                fmt={fmt}
              />
            </div>
          </div>

          {/* Right sticky panel */}
          <div className="lg:col-span-1 space-y-4">
            {hotel.latitude != null && hotel.longitude != null && (
              <>
                <div className="rounded-xl overflow-hidden border border-gray-200 shadow-sm h-56 relative">
                  <HotelMiniMap
                    latitude={hotel.latitude}
                    longitude={hotel.longitude}
                    name={hotel.name}
                    onExpand={() => setMapOpen(true)}
                  />
                </div>
                <NearbyHotelsMapModal
                  open={mapOpen}
                  onClose={() => setMapOpen(false)}
                  centerLat={hotel.latitude}
                  centerLng={hotel.longitude}
                  centerHotelName={hotel.name}
                  centerHotelId={hotel.liteapi_hotel_id}
                />
              </>
            )}
            <div className="sticky top-20 bg-white border rounded-xl p-5 shadow-sm space-y-4">
              <div className="text-center">
                <p className="text-3xl font-bold text-gray-900">
                  {selectedTotal ? fmt(selectedTotal) : (startingPrice ? fmt(startingPrice) : '—')}
                </p>
                <p className="text-sm text-gray-500">
                  {selectedTotal
                    ? t('hotels:detail.selectedSummary', { count: selectedRoomsCount, nights })
                    : t('hotels:detail.startingPerNight')}
                </p>
              </div>
              <button
                onClick={() => {
                  if (selectedTotal) {
                    handleReserveSelected()
                  } else {
                    handleShowPrices()
                  }
                }}
                className="w-full bg-primary hover:bg-primary-dark text-white font-bold py-3 rounded-lg transition-colors"
              >
                {selectedTotal ? t('hotels:detail.reserveSelected') : t('hotels:detail.checkAvailability')}
              </button>
              <ul className="text-xs text-gray-500 space-y-1">
                <li className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-success" /> {t('hotels:detail.bestPriceGuarantee')}</li>
                <li className="flex items-center gap-1"><Star className="w-3 h-3 text-success" /> {t('hotels:detail.poweredBy')}</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
