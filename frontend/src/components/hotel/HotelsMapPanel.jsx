import { useEffect, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { MapContainer, Marker, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import StarRating from '@/components/common/StarRating'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { useSearchStore } from '@/store/searchStore'
import { buildHotelHref, buildPricePinIcon, validCoords } from '@/utils/hotelMapHelpers'
import MyLocationControl from './MyLocationControl'

function FitBounds({ positions }) {
  const map = useMap()
  useEffect(() => {
    if (!positions.length) return
    if (positions.length === 1) {
      map.setView(positions[0], 14)
    } else {
      map.fitBounds(L.latLngBounds(positions), { padding: [40, 40] })
    }
  }, [map, positions])
  return null
}

export default function HotelsMapPanel({ hotels = [], preview = false, onExpand, height }) {
  const fmt = useFormatCurrency()
  const { checkIn, checkOut, guests } = useSearchStore()

  const plotted = useMemo(() => hotels.filter(validCoords), [hotels])
  const missing = hotels.length - plotted.length
  const positions = useMemo(
    () => plotted.map((h) => [Number(h.latitude), Number(h.longitude)]),
    [plotted]
  )

  if (!plotted.length) return null

  const heightClass = height || (preview ? 'h-48' : 'h-72 md:h-80')

  return (
    <div className="flex flex-col isolate">
      <div className={`${heightClass} relative`}>
        <MapContainer
          center={positions[0]}
          zoom={13}
          dragging={!preview}
          scrollWheelZoom={!preview}
          doubleClickZoom={!preview}
          touchZoom={!preview}
          keyboard={!preview}
          zoomControl={!preview}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitBounds positions={positions} />
          {!preview && <MyLocationControl />}
          {plotted.map((hotel) => {
            const isPartner = hotel.source !== 'liteapi'
            const price = hotel.min_room_price != null ? fmt(hotel.min_room_price) : null
            const href = buildHotelHref(hotel, { checkIn, checkOut, guests })
            const key = hotel.id || hotel.liteapi_hotel_id || `${hotel.latitude},${hotel.longitude}`
            return (
              <Marker
                key={key}
                position={[Number(hotel.latitude), Number(hotel.longitude)]}
                icon={buildPricePinIcon(price, isPartner)}
                interactive={!preview}
              >
                {preview ? null : <Popup>
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
                      <p className="text-sm font-bold text-primary">{price}<span className="text-xs font-normal text-gray-500"> / night</span></p>
                    )}
                    <Link
                      to={href}
                      className="block text-center text-xs font-semibold bg-primary text-white px-2 py-1.5 rounded hover:bg-primary-dark"
                    >
                      View
                    </Link>
                  </div>
                </Popup>}
              </Marker>
            )
          })}
        </MapContainer>
        {preview && onExpand && (
          <button
            type="button"
            onClick={onExpand}
            aria-label="Expand map"
            className="absolute inset-0 z-[400] cursor-pointer bg-transparent hover:bg-primary/5 transition-colors"
          />
        )}
      </div>
      {missing > 0 && (
        <p className="px-4 py-2 text-xs text-gray-500 bg-gray-50 border-t border-gray-100">
          {missing} hotel{missing > 1 ? 's' : ''} without coordinates are not shown on the map.
        </p>
      )}
    </div>
  )
}
