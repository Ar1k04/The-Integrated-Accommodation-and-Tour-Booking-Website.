import { useTranslation } from 'react-i18next'
import { PlaneTakeoff, PlaneLanding, Clock } from 'lucide-react'

function formatTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
  } catch { return iso }
}

function formatDateFull(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString([], {
      weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
    })
  } catch { return iso }
}

/**
 * FlightItineraryBlock — visual itinerary used on detail / confirmation / manage pages.
 *
 * Props:
 *   slices         — list of { origin, destination, duration, segments[] }
 *   airlineName    — optional header
 *   airlineIata    — optional header chip
 *   cabinClass     — optional small pill
 *   compact        — bool. Compact: smaller times, no airline header, dense rows.
 */
export default function FlightItineraryBlock({
  slices = [],
  airlineName,
  airlineIata,
  cabinClass,
  compact = false,
}) {
  const { t } = useTranslation(['flights', 'common'])

  if (!slices.length) {
    return <p className="text-sm text-gray-400">{t('flights:detail.notFound')}</p>
  }

  return (
    <div className={compact ? 'space-y-4' : 'bg-white border rounded-xl p-6'}>
      {!compact && (airlineName || cabinClass) && (
        <div className="flex items-center gap-2 mb-5 flex-wrap">
          {airlineIata && (
            <span className="bg-primary/10 text-primary text-sm font-bold px-3 py-1 rounded-full">
              {airlineIata}
            </span>
          )}
          {airlineName && (
            <h2 className="font-heading font-bold text-lg">{airlineName}</h2>
          )}
          {cabinClass && (
            <span className="text-xs text-gray-400 capitalize bg-gray-100 px-2 py-0.5 rounded-full">
              {cabinClass.replace('_', ' ')} {t('flights:detail.class')}
            </span>
          )}
        </div>
      )}

      {slices.map((slice, si) => (
        <div key={si} className={si > 0 ? (compact ? 'pt-4 border-t' : 'mt-6 pt-6 border-t') : ''}>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            {si === 0 ? t('flights:detail.outbound') : t('flights:detail.returnFlight')}
          </p>
          {slice.segments?.map((seg, i) => (
            <div key={i} className={i > 0 ? 'mt-4 pt-4 border-t border-dashed' : ''}>
              <div className="flex items-center gap-4">
                <div className="text-center w-16 shrink-0">
                  <p className={`font-bold text-gray-900 ${compact ? 'text-lg' : 'text-2xl'}`}>
                    {formatTime(seg.departure_at)}
                  </p>
                  <p className="text-xs font-semibold text-primary">{seg.origin_iata}</p>
                  <p className="text-xs text-gray-400 truncate">{seg.origin_name}</p>
                </div>
                <div className="flex-1 flex flex-col items-center gap-1 min-w-0">
                  {seg.duration && (
                    <span className="text-xs text-gray-400 flex items-center gap-1">
                      <Clock className="w-3 h-3" />{seg.duration}
                    </span>
                  )}
                  <div className="w-full flex items-center">
                    <PlaneTakeoff className="w-4 h-4 text-gray-300 mr-1 shrink-0" />
                    <div className="flex-1 h-0.5 bg-gray-200" />
                    <PlaneLanding className="w-4 h-4 text-gray-300 ml-1 shrink-0" />
                  </div>
                  <span className="text-xs text-gray-400 truncate">
                    {seg.flight_number}
                    {seg.aircraft ? ` · ${seg.aircraft}` : ''}
                  </span>
                </div>
                <div className="text-center w-16 shrink-0">
                  <p className={`font-bold text-gray-900 ${compact ? 'text-lg' : 'text-2xl'}`}>
                    {formatTime(seg.arrival_at)}
                  </p>
                  <p className="text-xs font-semibold text-primary">{seg.destination_iata}</p>
                  <p className="text-xs text-gray-400 truncate">{seg.destination_name}</p>
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-2">{formatDateFull(seg.departure_at)}</p>
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}
