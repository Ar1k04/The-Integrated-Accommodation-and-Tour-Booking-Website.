import { useState } from 'react'
import { Marker, Tooltip, useMap } from 'react-leaflet'
import { Crosshair, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { buildUserLocationIcon } from '@/utils/hotelMapHelpers'

export default function MyLocationControl() {
  const map = useMap()
  const [coords, setCoords] = useState(null)
  const [status, setStatus] = useState('idle') // idle | loading | error
  const [error, setError] = useState('')

  const fail = (message) => {
    setStatus('error')
    setError(message)
    toast.error(message)
  }

  const locate = () => {
    if (!('geolocation' in navigator)) {
      fail('Geolocation is not supported by your browser')
      return
    }
    // Chrome only exposes geolocation on secure origins (https or localhost).
    // Accessing the dev server via a LAN IP over http silently blocks it.
    if (typeof window !== 'undefined' && window.isSecureContext === false) {
      fail('Location requires HTTPS or localhost (Chrome blocks it on http via IP)')
      return
    }
    setStatus('loading')
    setError('')
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const next = [pos.coords.latitude, pos.coords.longitude]
        setCoords(next)
        setStatus('idle')
        map.flyTo(next, Math.max(map.getZoom(), 14), { duration: 0.8 })
      },
      (err) => {
        if (err.code === 1) fail('Location permission denied')
        else if (err.code === 2) fail('Your location is unavailable')
        else if (err.code === 3) fail('Timed out while getting your location')
        else fail('Unable to get your location')
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    )
  }

  return (
    <>
      <div className="leaflet-top leaflet-right" style={{ pointerEvents: 'none' }}>
        <div className="leaflet-control" style={{ pointerEvents: 'auto', marginTop: 10, marginRight: 10 }}>
          <button
            type="button"
            onClick={locate}
            disabled={status === 'loading'}
            aria-label="Show my location"
            title={error || 'Show my location'}
            className="bg-white hover:bg-gray-50 border border-gray-300 rounded-md shadow p-2 text-gray-700 disabled:opacity-60"
          >
            {status === 'loading' ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Crosshair className={`w-4 h-4 ${coords ? 'text-primary' : ''}`} />
            )}
          </button>
        </div>
      </div>
      {coords && (
        <Marker position={coords} icon={buildUserLocationIcon()}>
          <Tooltip direction="top" offset={[0, -10]}>You are here</Tooltip>
        </Marker>
      )}
    </>
  )
}
