import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { formatCurrency } from '@/utils/formatters'
import { ChevronRight, ChevronDown, ChevronUp, Briefcase, RefreshCcw, Clock } from 'lucide-react'

function formatTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })
  } catch { return iso }
}

function formatDateTime(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString([], {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
    })
  } catch { return iso }
}

function layoverMinutes(prevArr, nextDep) {
  try {
    return Math.max(0, Math.floor((new Date(nextDep) - new Date(prevArr)) / 60000))
  } catch { return 0 }
}

function minutesToHm(mins) {
  if (!mins) return ''
  const h = Math.floor(mins / 60)
  const m = mins % 60
  return `${h}h ${m}m`
}

export default function FlightOfferCard({ offer, onSelect }) {
  const { t } = useTranslation(['flights', 'common'])
  const [expanded, setExpanded] = useState(false)
  const isRoundTrip = offer.slices?.length > 1
  const refundable = !!offer.conditions?.refund_before_departure?.allowed
  const hasBaggage = !!offer.has_baggage

  const renderSliceSummary = (slice, idx) => {
    const segs = slice.segments || []
    const firstSeg = segs[0]
    const lastSeg = segs[segs.length - 1]
    const stops = Math.max(0, segs.length - 1)
    const stopsLabel = stops === 0
      ? t('flights:card.direct')
      : t('flights:card.stop', { count: stops })

    return (
      <div key={idx} className={idx > 0 ? 'mt-3 pt-3 border-t' : ''}>
        <div className="flex items-center gap-3 text-sm">
          <div className="text-center min-w-[3rem]">
            <p className="font-bold text-gray-900">{slice.origin}</p>
            <p className="text-xs text-gray-400">{firstSeg && formatTime(firstSeg.departure_at)}</p>
          </div>
          <div className="flex-1 flex flex-col items-center">
            <p className="text-xs text-gray-400 mb-0.5">{slice.duration || ''}</p>
            <div className="w-full flex items-center">
              <div className="flex-1 h-px bg-gray-200" />
              <ChevronRight className="w-3 h-3 text-gray-400 mx-0.5" />
              <div className="flex-1 h-px bg-gray-200" />
            </div>
            <p className="text-xs text-gray-500 mt-0.5">{stopsLabel}</p>
            {stops > 0 && segs.length > 1 && (
              <p className="text-[10px] text-gray-400 mt-0.5">
                via {segs.slice(0, -1).map((s) => s.destination_iata).join(', ')}
              </p>
            )}
          </div>
          <div className="text-center min-w-[3rem]">
            <p className="font-bold text-gray-900">{slice.destination}</p>
            <p className="text-xs text-gray-400">{lastSeg && formatTime(lastSeg.arrival_at)}</p>
          </div>
        </div>
        {firstSeg && (
          <p className="text-xs text-gray-400 mt-1">
            {firstSeg.flight_number} · {formatDateTime(firstSeg.departure_at)}
          </p>
        )}
      </div>
    )
  }

  const renderSegmentDetails = () => (
    <div className="mt-3 pt-3 border-t space-y-3">
      {offer.slices?.map((slice, si) => (
        <div key={si} className="space-y-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            {si === 0 ? t('flights:detail.outbound') : t('flights:detail.returnFlight')}
          </p>
          {slice.segments?.map((seg, i) => {
            const prevSeg = slice.segments[i - 1]
            return (
              <div key={i}>
                {prevSeg && (
                  <p className="text-[11px] text-gray-400 italic ml-7 mb-1">
                    <Clock className="w-3 h-3 inline mr-1" />
                    {t('flights:card.layover', 'Layover')} {minutesToHm(layoverMinutes(prevSeg.arrival_at, seg.departure_at))} {t('flights:card.in', 'in')} {seg.origin_iata}
                  </p>
                )}
                <div className="flex items-start gap-3 text-xs">
                  <div className="font-mono text-primary bg-primary/5 px-1.5 py-0.5 rounded text-[10px] shrink-0 mt-0.5">
                    {seg.airline_iata}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-700">
                      {seg.flight_number} · {seg.aircraft || ''}
                    </p>
                    <p className="text-gray-500 mt-0.5">
                      {seg.origin_iata} {formatTime(seg.departure_at)} → {seg.destination_iata} {formatTime(seg.arrival_at)}
                      <span className="text-gray-400 ml-2">({seg.duration})</span>
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )

  return (
    <div className="border rounded-xl p-4 bg-white hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-3 flex-wrap">
            <span className="bg-primary/10 text-primary text-xs font-semibold px-2 py-0.5 rounded-full">
              {offer.airline_iata || 'XX'}
            </span>
            <span className="text-sm font-medium text-gray-800">{offer.airline_name}</span>
            {isRoundTrip && (
              <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">
                {t('flights:card.roundTrip', 'Round-trip')}
              </span>
            )}
            {offer.cabin_class && (
              <span className="text-xs text-gray-400 capitalize">
                {offer.cabin_class.replace('_', ' ')}
              </span>
            )}
            {refundable && (
              <span className="text-xs bg-green-50 text-green-700 px-2 py-0.5 rounded-full flex items-center gap-1">
                <RefreshCcw className="w-3 h-3" />
                {t('flights:card.refundable')}
              </span>
            )}
            {hasBaggage && (
              <span className="text-xs bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full flex items-center gap-1">
                <Briefcase className="w-3 h-3" />
                {t('flights:card.baggage')}
              </span>
            )}
          </div>

          {offer.slices?.map(renderSliceSummary)}

          {expanded && renderSegmentDetails()}

          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-3 text-xs text-primary hover:underline font-medium flex items-center gap-1"
          >
            {expanded ? (
              <>
                <ChevronUp className="w-3 h-3" />
                {t('flights:card.hideSegments')}
              </>
            ) : (
              <>
                <ChevronDown className="w-3 h-3" />
                {t('flights:card.showSegments')}
              </>
            )}
          </button>
        </div>

        <div className="text-right shrink-0">
          <p className="text-2xl font-bold text-gray-900">
            {formatCurrency(offer.total_amount, offer.currency)}
          </p>
          <p className="text-xs text-gray-400 mb-3">{t('flights:card.perPerson')}</p>
          <button
            onClick={() => onSelect(offer)}
            className="bg-accent hover:bg-accent/90 text-white font-semibold px-5 py-2 rounded-lg text-sm transition-colors"
          >
            {t('flights:card.select')}
          </button>
        </div>
      </div>
    </div>
  )
}
