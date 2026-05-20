import L from 'leaflet'
import { format } from 'date-fns'

const PIN_BG = '#003580'
const PIN_BORDER = '#002050'

export function validCoords(hotel) {
  if (!hotel) return false
  const lat = Number(hotel.latitude)
  const lng = Number(hotel.longitude)
  return Number.isFinite(lat) && Number.isFinite(lng) && (lat !== 0 || lng !== 0)
}

export function buildHotelHref(hotel, { checkIn, checkOut, guests } = {}) {
  const basePath =
    hotel.source === 'liteapi'
      ? `/hotels/liteapi/${hotel.liteapi_hotel_id}`
      : `/hotels/${hotel.id}`

  const params = new URLSearchParams()
  if (checkIn) params.set('check_in', format(checkIn, 'yyyy-MM-dd'))
  if (checkOut) params.set('check_out', format(checkOut, 'yyyy-MM-dd'))
  if (guests) {
    const adults = guests.adults || 1
    const childAges = guests.child_ages || []
    const total = adults + childAges.length
    params.set('adults', String(adults))
    if (childAges.length) params.set('child_ages', childAges.join(','))
    if (total) params.set('guests', String(total))
    if (guests.rooms > 1) params.set('rooms', String(guests.rooms))
  }
  const qs = params.toString()
  return qs ? `${basePath}?${qs}` : basePath
}

export function buildPricePinIcon(formattedPrice, isPartner) {
  const prefix = isPartner ? '★ ' : ''
  const label = formattedPrice || '—'
  const style =
    `display:inline-block;transform:translate(-50%,-50%);` +
    `background:${PIN_BG};color:#fff;border:1px solid ${PIN_BORDER};` +
    `box-shadow:0 1px 4px rgba(0,0,0,0.3);` +
    `padding:5px 10px;border-radius:9999px;` +
    `font-size:11px;font-weight:700;line-height:1;letter-spacing:0.01em;` +
    `white-space:nowrap;`
  // iconSize [0,0] + transform translate(-50%,-50%) lets the label center
  // itself on the latLng regardless of content width — fixes the alignment.
  return L.divIcon({
    className: '',
    iconSize: [0, 0],
    iconAnchor: [0, 0],
    html: `<div style="${style}">${prefix}${label}</div>`,
  })
}

export function buildLocationDotIcon() {
  return L.divIcon({
    className: '',
    iconSize: [0, 0],
    iconAnchor: [0, 0],
    html:
      '<div style="transform:translate(-50%,-50%);width:12px;height:12px;border-radius:9999px;' +
      `background:${PIN_BG};border:2px solid #fff;box-shadow:0 0 0 1px ${PIN_BORDER};"></div>`,
  })
}

export function buildCenterPinIcon() {
  return L.divIcon({
    className: '',
    iconAnchor: [10, 10],
    html: '<div style="width:20px;height:20px;border-radius:9999px;background:#003580;border:3px solid #fff;box-shadow:0 0 0 2px #003580;"></div>',
  })
}

export function buildUserLocationIcon() {
  return L.divIcon({
    className: '',
    iconAnchor: [9, 9],
    html: `<div style="position:relative;width:18px;height:18px;">
      <div style="position:absolute;inset:-6px;border-radius:9999px;background:#3b82f6;opacity:0.25;animation:pulse-ring 1.6s ease-out infinite;"></div>
      <div style="position:absolute;inset:0;width:18px;height:18px;border-radius:9999px;background:#3b82f6;border:3px solid #fff;box-shadow:0 0 0 1px #3b82f6;"></div>
    </div>
    <style>@keyframes pulse-ring{0%{transform:scale(0.6);opacity:0.5}100%{transform:scale(1.6);opacity:0}}</style>`,
  })
}

// Fix the well-known Leaflet + Vite marker-icon-broken bug (asset URLs are
// resolved at runtime but Vite's bundler can't trace them). Pin to the
// installed Leaflet version's CDN.
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})
