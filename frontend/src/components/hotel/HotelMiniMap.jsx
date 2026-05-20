import { MapContainer, Marker, TileLayer, Tooltip } from 'react-leaflet'
import { validCoords } from '@/utils/hotelMapHelpers'

export default function HotelMiniMap({ latitude, longitude, name, onExpand }) {
  if (!validCoords({ latitude, longitude })) return null

  const center = [Number(latitude), Number(longitude)]

  return (
    <div className="relative w-full h-full isolate">
      <MapContainer
        center={center}
        zoom={14}
        dragging={false}
        scrollWheelZoom={false}
        doubleClickZoom={false}
        touchZoom={false}
        keyboard={false}
        zoomControl={false}
        attributionControl
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Marker position={center}>
          {name ? <Tooltip>{name}</Tooltip> : null}
        </Marker>
      </MapContainer>
      {onExpand && (
        <button
          type="button"
          onClick={onExpand}
          aria-label="Expand map to see nearby hotels"
          className="absolute inset-0 z-[400] cursor-pointer bg-transparent hover:bg-primary/5 transition-colors"
        />
      )}
    </div>
  )
}
