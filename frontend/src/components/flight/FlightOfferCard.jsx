import { formatCurrency } from '@/utils/formatters'
import { Clock, ChevronRight } from 'lucide-react'

export default function FlightOfferCard({ offer, onSelect }) {
  const firstSlice = offer.slices?.[0]
  const lastSlice = offer.slices?.[offer.slices.length - 1]
  const firstSeg = firstSlice?.segments?.[0]
  const lastSeg = lastSlice?.segments?.[lastSlice.segments.length - 1]
  const isRoundTrip = offer.slices?.length > 1

  const formatTime = (iso) => {
    if (!iso) return '—'
    try {
      return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
    } catch { return iso }
  }

  const formatDateTime = (iso) => {
    if (!iso) return '—'
    try {
      return new Date(iso).toLocaleString([], {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
      })
    } catch { return iso }
  }

  return (
    <div className="border rounded-xl p-4 bg-white hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-4">
        {/* Airline + flight info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-3">
            <span className="bg-primary/10 text-primary text-xs font-semibold px-2 py-0.5 rounded-full">
              {offer.airline_iata || 'XX'}
            </span>
            <span className="text-sm font-medium text-gray-800">{offer.airline_name}</span>
            {isRoundTrip && (
              <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">Round-trip</span>
            )}
            {offer.cabin_class && (
              <span className="text-xs text-gray-400 capitalize">{offer.cabin_class.replace('_', ' ')}</span>
            )}
          </div>

          {offer.slices?.map((slice, i) => (
            <div key={i} className={i > 0 ? 'mt-3 pt-3 border-t' : ''}>
              <div className="flex items-center gap-3 text-sm">
                <div className="text-center">
                  <p className="font-bold text-gray-900">{slice.origin}</p>
                  <p className="text-xs text-gray-400">
                    {slice.segments?.[0] ? formatTime(slice.segments[0].departure_at) : '—'}
                  </p>
                </div>
                <div className="flex-1 flex flex-col items-center">
                  <p className="text-xs text-gray-400 mb-0.5">{slice.duration || ''}</p>
                  <div className="w-full flex items-center">
                    <div className="flex-1 h-px bg-gray-200" />
                    <ChevronRight className="w-3 h-3 text-gray-400 mx-0.5" />
                    <div className="flex-1 h-px bg-gray-200" />
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {slice.segments?.length === 1 ? 'Direct' : `${slice.segments?.length - 1} stop`}
                  </p>
                </div>
                <div className="text-center">
                  <p className="font-bold text-gray-900">{slice.destination}</p>
                  <p className="text-xs text-gray-400">
                    {slice.segments?.length > 0
                      ? formatTime(slice.segments[slice.segments.length - 1].arrival_at)
                      : '—'}
                  </p>
                </div>
              </div>
              {slice.segments?.[0] && (
                <p className="text-xs text-gray-400 mt-1">
                  {slice.segments[0].flight_number} · {formatDateTime(slice.segments[0].departure_at)}
                </p>
              )}
            </div>
          ))}
        </div>

        {/* Price + CTA */}
        <div className="text-right shrink-0">
          <p className="text-2xl font-bold text-gray-900">{formatCurrency(offer.total_amount, offer.currency)}</p>
          <p className="text-xs text-gray-400 mb-3">per person</p>
          <button
            onClick={() => onSelect(offer)}
            className="bg-accent hover:bg-accent/90 text-white font-semibold px-5 py-2 rounded-lg text-sm transition-colors"
          >
            Select
          </button>
        </div>
      </div>
    </div>
  )
}
