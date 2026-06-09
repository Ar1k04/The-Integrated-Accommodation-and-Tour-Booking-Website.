import { useState, useRef, useMemo, useEffect } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { hotelsApi } from '@/api/hotelsApi'
import { roomsApi } from '@/api/roomsApi'
import { reviewsApi } from '@/api/reviewsApi'
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
import WishlistButton from '@/components/common/WishlistButton'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { MapPin, Star, CalendarDays, Users, Search } from 'lucide-react'
import { format, addDays, differenceInDays } from 'date-fns'

export default function HotelDetailPage() {
  const { id } = useParams()
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
    queryKey: ['hotel', id],
    queryFn: () => hotelsApi.get(id),
    select: (res) => res.data,
  })

  const liteapiHotelId = hotel?.liteapi_hotel_id || null
  const useLiteapi = !!liteapiHotelId

  const roomParams = {
    ...(checkIn && checkOut ? { check_in: checkIn, check_out: checkOut } : {}),
    guests,
  }

  // DB-hotel rooms (used when the hotel has no liteapi_hotel_id).
  const { data: dbRooms } = useQuery({
    queryKey: ['hotel-rooms', id, checkIn, checkOut, guests],
    queryFn: () => roomsApi.listByHotel(id, roomParams),
    select: (res) => res.data?.items || [],
    enabled: !!hotel && !useLiteapi,
  })

  // LiteAPI live rates (when dates picked).
  const { data: liteapiRates } = useQuery({
    queryKey: ['liteapi-rates', liteapiHotelId, checkIn, checkOut, adults, childAgesParam, rooms],
    queryFn: () =>
      hotelsApi.getRates(liteapiHotelId, {
        check_in: checkIn,
        check_out: checkOut,
        adults,
        child_ages: childAgesParam || undefined,
        guests,
        rooms,
      }),
    select: (res) => res.data || [],
    enabled: useLiteapi && datesSelected,
  })

  // LiteAPI catalog (no prices) — used when no dates are picked yet.
  const { data: liteapiCatalog } = useQuery({
    queryKey: ['liteapi-room-types', liteapiHotelId],
    queryFn: () => hotelsApi.getLiteapiRoomTypes(liteapiHotelId),
    select: (res) => res.data || [],
    enabled: useLiteapi && !datesSelected,
    staleTime: 60 * 60 * 1000,
  })

  // Build the unified roomGroups[] shape the AvailabilityTable expects.
  const roomGroups = (() => {
    if (useLiteapi) {
      const source = datesSelected ? liteapiRates : liteapiCatalog
      if (!source) return []
      return source.map((rt) => ({
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
    }
    // Local DB hotel: each Room becomes a group with one synthesized rate.
    return (dbRooms || []).map((room) => ({
      id: room.id,
      name: room.name,
      room_type: room.room_type,
      max_guests: room.max_guests,
      total_quantity: room.total_quantity,
      amenities: room.amenities || [],
      images: room.images || [],
      rates: datesSelected
        ? [
            {
              rate_id: `db:${room.id}`,
              board_name: '',
              refundable: true,
              cancellation_deadline: null,
              price: room.price_per_night,
              price_excl_taxes: null,
              taxes: null,
              original_price: null,
              discount_percent: null,
              currency: hotel?.currency || 'USD',
              max_occupancy: room.max_guests,
            },
          ]
        : [],
    }))
  })()

  const { data: reviewsData } = useQuery({
    queryKey: ['reviews', 'hotel', id],
    // Fetch a large page: the merged feed (local + LiteAPI) is paginated
    // client-side below, so we want all items in one response.
    queryFn: () => reviewsApi.listHotelReviews(id, { per_page: 100 }),
    select: (res) => res.data,
  })

  const fmt = useFormatCurrency()

  /**
   * Reserve a room group. `quantities` maps rate_id → count.
   * For LiteAPI: rate_id is the LiteAPI offerId (passed downstream to prebook).
   * For DB hotels: rate_id is "db:<room.id>" — strip the prefix when downstream needs the room id.
   */
  const handleReserve = (group, quantities) => {
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
          liteapi_rate_id: useLiteapi ? rate_id : null,
          db_room_id: useLiteapi ? null : rate_id.replace(/^db:/, ''),
        }
      })
    if (items.length === 0) return

    setBookingData({
      hotel,
      selectedRoomGroup: { id: group.id, name: group.name, max_guests: group.max_guests },
      selectedItems: items,
      // Legacy single-room fields for backward compat with the existing booking page:
      selectedRoom: useLiteapi
        ? {
            id: items[0].rate_id,
            name: group.name,
            price_per_night: items[0].price,
            currency: group.rates[0]?.currency || 'USD',
            max_guests: group.max_guests,
            images: group.images || [],
            liteapi_rate_id: items[0].rate_id,
            liteapi_price: items[0].price,
            liteapi_hotel_id: liteapiHotelId,
          }
        : (dbRooms || []).find((r) => r.id === items[0].db_room_id) || null,
      checkIn,
      checkOut,
      adults,
      childAges,
      rooms,
    })
    navigate('/bookings/new')
  }

  const handleShowPrices = () => {
    if (datePickerRef.current) {
      datePickerRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
      // Briefly pulse the search bar to draw attention
      datePickerRef.current.classList.add('ring-4', 'ring-amber-400')
      setTimeout(() => {
        datePickerRef.current?.classList.remove('ring-4', 'ring-amber-400')
      }, 1500)
    }
  }

  const nights = datesSelected ? differenceInDays(new Date(checkOut), new Date(checkIn)) : 0
  const recommendation = useMemo(
    () =>
      datesSelected
        ? recommendCombination(roomGroups, { adults, childAges, rooms, nights })
        : null,
    // childAgesParam (CSV) is the stable dependency for the child-ages array.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [roomGroups, adults, childAgesParam, rooms, nights, datesSelected]
  )

  // Track room selections from AvailabilityTable for dynamic right-panel pricing.
  const [tableSelections, setTableSelections] = useState({})
  useEffect(() => { setTableSelections({}) }, [checkIn, checkOut, guests, rooms])

  const selectedTotal = useMemo(() => {
    let total = 0
    for (const [groupId, rateQtys] of Object.entries(tableSelections)) {
      const group = roomGroups.find((g) => String(g.id) === String(groupId))
      if (!group) continue
      for (const [rateId, q] of Object.entries(rateQtys)) {
        if (!q) continue
        const rate = group.rates.find((r) => r.rate_id === rateId)
        if (rate?.price) total += rate.price * q * Math.max(nights, 1)
      }
    }
    return total > 0 ? total : null
  }, [tableSelections, roomGroups, nights])

  const selectedRoomsCount = useMemo(
    () =>
      Object.values(tableSelections).reduce(
        (sum, rateQtys) => sum + Object.values(rateQtys).reduce((s, n) => s + (n || 0), 0),
        0
      ),
    [tableSelections]
  )

  const handleReserveSelected = () => {
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
    const storeItems = items.map((it) => ({
      rate_id: it.rate.rate_id,
      quantity: it.quantity,
      price: it.rate.price,
      board_name: it.rate.board_name,
      refundable: it.rate.refundable,
      room_name: it.group.name,
      max_guests: it.group.max_guests,
      per_unit_guests: it.perUnitGuests,
      liteapi_rate_id: useLiteapi ? it.rate.rate_id : null,
      db_room_id: useLiteapi ? null : String(it.rate.rate_id).replace(/^db:/, ''),
    }))

    setBookingData({
      hotel,
      selectedRoomGroup: null,
      selectedItems: storeItems,
      // Legacy single-room fields populated from the first item, for the existing
      // single-room booking page to render until multi-room checkout ships.
      selectedRoom: useLiteapi
        ? {
            id: storeItems[0].rate_id,
            name: storeItems[0].room_name,
            price_per_night: storeItems[0].price,
            currency: items[0].rate.currency || 'USD',
            max_guests: storeItems[0].max_guests,
            images: items[0].group.images || [],
            liteapi_rate_id: storeItems[0].rate_id,
            liteapi_price: storeItems[0].price,
            liteapi_hotel_id: liteapiHotelId,
          }
        : (dbRooms || []).find((r) => r.id === storeItems[0].db_room_id) || null,
      checkIn,
      checkOut,
      adults,
      childAges,
      rooms,
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

  if (!hotel) return <div className="text-center py-20 text-gray-400">{t('hotels:detail.notFound')}</div>

  const reviews = reviewsData?.items || []
  const allRatePrices = roomGroups.flatMap((g) => (g.rates || []).map((r) => r.price)).filter((p) => p > 0)
  const startingPrice = allRatePrices.length ? Math.min(...allRatePrices) : hotel?.min_room_price || null
  const cheapestGroup = roomGroups.find((g) => (g.rates || []).some((r) => r.price === startingPrice)) || null

  return (
    <>
      <Helmet>
        <title>{hotel.name} — TravelBooking</title>
        <meta name="description" content={`${hotel.name} — ${hotel.star_rating}-star hotel in ${hotel.city}, ${hotel.country}. Browse available rooms and reserve your stay.`} />
        <meta property="og:title" content={`${hotel.name} — TravelBooking`} />
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
                  <h1 className="font-heading text-2xl md:text-3xl font-bold text-gray-900">{hotel.name}</h1>
                  <div className="flex items-center gap-3 mt-2">
                    <StarRating rating={hotel.star_rating} />
                    {hotel.property_type && (
                      <span className="bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded-full">{hotel.property_type}</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <WishlistButton hotelId={hotel.id} />
                  {hotel.avg_rating > 0 && (
                    <div className="text-right">
                      <div className="bg-primary text-white font-bold text-lg px-3 py-1.5 rounded-lg">{hotel.avg_rating.toFixed(1)}</div>
                      <p className="text-xs text-gray-500 mt-1">{t('hotels:detail.reviewsCount', { count: hotel.total_reviews })}</p>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1.5 mt-3 text-gray-500 text-sm">
                <MapPin className="w-4 h-4" />{hotel.address || `${hotel.city}, ${hotel.country}`}
              </div>
              {hotel.owner_name && (
                <p className="mt-1 text-sm text-gray-500">{t('hotels:detail.managedBy')} <span className="font-medium text-gray-700">{hotel.owner_name}</span></p>
              )}
            </div>

            {/* Description */}
            {hotel.description && (
              <div>
                <h2 className="font-heading font-bold text-lg mb-3">{t('hotels:detail.about')}</h2>
                <p className="text-gray-600 text-sm leading-relaxed whitespace-pre-line">{hotel.description}</p>
              </div>
            )}

            {/* Facilities */}
            <FacilitiesSection amenities={hotel.amenities} />

            {/* Reviews — paginated 5 per page. Authenticated guests with a
                completed stay can post a review at the bottom of the list. */}
            <div>
              <h2 className="font-heading font-bold text-lg mb-4">{t('hotels:detail.guestReviews')}</h2>
              {reviews.length > 0 ? (
                <>
                  <div className="space-y-5">
                    {reviews
                      .slice((reviewPage - 1) * REVIEWS_PER_PAGE, reviewPage * REVIEWS_PER_PAGE)
                      .map((r) => <ReviewCard key={r.id} review={r} />)}
                  </div>
                  {reviews.length > REVIEWS_PER_PAGE && (
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
                        {reviewPage} / {Math.ceil(reviews.length / REVIEWS_PER_PAGE)}
                      </span>
                      <button
                        type="button"
                        onClick={() =>
                          setReviewPage((p) =>
                            Math.min(Math.ceil(reviews.length / REVIEWS_PER_PAGE), p + 1)
                          )
                        }
                        disabled={reviewPage >= Math.ceil(reviews.length / REVIEWS_PER_PAGE)}
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
              {isAuthenticated && <div className="mt-6"><ReviewForm hotelId={id} /></div>}
            </div>

            {/* Availability section */}
            <div>
              <h2 className="font-heading font-bold text-xl mb-4">{t('hotels:detail.rooms')}</h2>

              {/* Booking.com-style date search bar */}
              <div
                ref={datePickerRef}
                className="rounded-xl p-3 mb-5 flex flex-col sm:flex-row items-stretch sm:items-end gap-3 transition-all duration-300"
                style={{
                  border: '2px solid #febb02',
                  backgroundColor: '#febb0208',
                }}
              >
                {/* Check-in */}
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

                {/* Check-out */}
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

                {/* Guests + rooms (with per-child ages) */}
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

                {/* Search / Change search button */}
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

              {/* Recommended combination — shown when the search asks for more than 1 room or > 2 guests */}
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

              {/* Availability table */}
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

          {/* Right sticky booking panel */}
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
                  centerHotelId={hotel.id}
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
                    if (!cheapestGroup) return
                    const cheapestRate = cheapestGroup.rates.reduce(
                      (min, r) => (min == null || r.price < min.price ? r : min),
                      null
                    )
                    if (cheapestRate) handleReserve(cheapestGroup, { [cheapestRate.rate_id]: 1 })
                  }
                }}
                disabled={!datesSelected || (!selectedTotal && !cheapestGroup)}
                className="w-full bg-accent hover:bg-accent-dark text-white font-bold py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {selectedTotal ? t('hotels:detail.reserveSelected') : t('hotels:detail.reserveNow')}
              </button>
              <ul className="text-xs text-gray-500 space-y-1">
                <li className="flex items-center gap-1"><Star className="w-3 h-3 text-success" /> {t('hotels:detail.freeCancellation')}</li>
                <li className="flex items-center gap-1"><Star className="w-3 h-3 text-success" /> {t('hotels:detail.noPrepayment')}</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
