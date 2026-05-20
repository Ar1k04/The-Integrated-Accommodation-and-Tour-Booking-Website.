import { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { format } from 'date-fns'
import {
  Circle,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  Tooltip,
} from 'react-leaflet'
import StarRating from '@/components/common/StarRating'
import { hotelsApi } from '@/api/hotelsApi'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { useSearchStore } from '@/store/searchStore'
import { useEscapeKey } from '@/hooks/useEscapeKey'
import {
  buildCenterPinIcon,
  buildHotelHref,
  buildPricePinIcon,
  validCoords,
} from '@/utils/hotelMapHelpers'
import MyLocationControl from './MyLocationControl'

const RADIUS_KM = 5

export default function NearbyHotelsMapModal({
  open,
  onClose,
  centerLat,
  centerLng,
  centerHotelName,
  centerHotelId,
}) {
  const fmt = useFormatCurrency()
  const { checkIn, checkOut, guests } = useSearchStore()

  useEscapeKey(onClose, open)
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  const queryParams = useMemo(() => {
    const adults = guests?.adults || 1
    const childAges = guests?.child_ages || []
    return {
      latitude: centerLat,
      longitude: centerLng,
      radius_km: RADIUS_KM,
      check_in: checkIn ? format(checkIn, 'yyyy-MM-dd') : undefined,
      check_out: checkOut ? format(checkOut, 'yyyy-MM-dd') : undefined,
      guests: adults + childAges.length,
      child_ages: childAges.length ? childAges.join(',') : undefined,
      per_page: 50,
    }
  }, [centerLat, centerLng, checkIn, checkOut, guests])

  const enabled = !!open && centerLat != null && centerLng != null
  const { data, isLoading, isError } = useQuery({
    queryKey: ['nearby-hotels', queryParams],
    queryFn: () => hotelsApi.list(queryParams),
    enabled,
  })

  if (!open) return null

  const items = data?.data?.items || []
  const nearby = items.filter((h) => {
    if (!validCoords(h)) return false
    if (centerHotelId && (h.id === centerHotelId || h.liteapi_hotel_id === centerHotelId)) {
      return false
    }
    return true
  })

  return createPortal(
    <div
      className="fixed inset-0 z-[1000] flex items-start justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="relative mx-auto my-8 w-full max-w-6xl rounded-2xl bg-white overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200">
          <h2 className="font-heading font-bold text-lg text-gray-900">
            Hotels near {centerHotelName}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close map"
            className="p-1.5 rounded-full hover:bg-gray-100 text-gray-500"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="relative h-[75vh]">
          <MapContainer
            center={[centerLat, centerLng]}
            zoom={14}
            scrollWheelZoom
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <Circle
              center={[centerLat, centerLng]}
              radius={RADIUS_KM * 1000}
              pathOptions={{ color: '#0ea5e9', weight: 1, fillOpacity: 0.05 }}
            />
            <MyLocationControl />
            <Marker position={[centerLat, centerLng]} icon={buildCenterPinIcon()}>
              <Tooltip permanent direction="top" offset={[0, -10]}>
                {centerHotelName}
              </Tooltip>
            </Marker>
            {nearby.map((hotel) => {
              const isPartner = hotel.source !== 'liteapi'
              const price = hotel.min_room_price != null ? fmt(hotel.min_room_price) : null
              const href = buildHotelHref(hotel, { checkIn, checkOut, guests })
              const key = hotel.id || hotel.liteapi_hotel_id
              return (
                <Marker
                  key={key}
                  position={[Number(hotel.latitude), Number(hotel.longitude)]}
                  icon={buildPricePinIcon(price, isPartner)}
                >
                  <Popup>
                    <div className="space-y-1.5 min-w-[180px]">
                      {hotel.images?.[0] && (
                        <img
                          src={hotel.images[0]}
                          alt={hotel.name}
                          className="w-full h-24 object-cover rounded"
                        />
                      )}
                      <div className="flex items-center gap-1">
                        {isPartner && (
                          <span className="text-[10px] font-semibold px-1.5 py-0.5 bg-accent text-white rounded">
                            Partner
                          </span>
                        )}
                        <span className="text-sm font-semibold text-gray-900 line-clamp-2">
                          {hotel.name}
                        </span>
                      </div>
                      <StarRating rating={hotel.star_rating} size={12} />
                      {isPartner && hotel.owner_name && (
                        <p className="text-[11px] text-gray-500">by {hotel.owner_name}</p>
                      )}
                      {price && (
                        <p className="text-sm font-bold text-primary">
                          {price}<span className="text-xs font-normal text-gray-500"> / night</span>
                        </p>
                      )}
                      <Link
                        to={href}
                        onClick={onClose}
                        className="block text-center text-xs font-semibold bg-primary text-white px-2 py-1.5 rounded hover:bg-primary-dark"
                      >
                        View
                      </Link>
                    </div>
                  </Popup>
                </Marker>
              )
            })}
          </MapContainer>

          {isLoading && (
            <div className="absolute inset-0 bg-white/70 flex items-center justify-center text-sm text-gray-600 pointer-events-none">
              Loading nearby hotels…
            </div>
          )}
          {!isLoading && isError && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-white border rounded-lg px-3 py-2 text-sm text-gray-600 shadow">
              Unable to load nearby hotels.
            </div>
          )}
          {!isLoading && !isError && nearby.length === 0 && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-white border rounded-lg px-3 py-2 text-sm text-gray-600 shadow">
              No other hotels within {RADIUS_KM} km.
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  )
}
