import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Armchair } from 'lucide-react'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'

/**
 * SeatMapModal — visual seat picker.
 *
 * Props:
 *   open: bool
 *   onClose()
 *   seatMaps: Duffel seat_maps response (list of segments)
 *   passengers: PassengerInfo[]   — index used as pax key
 *   initialSelected: { [paxIndex]: service_id }
 *   onApply(selectedSeats: { [paxIndex]: service_id })
 *
 * Each seat element has:
 *   { type: 'seat'|'lavatory'|'galley'|'exit_row'|...,
 *     designator: '12A',
 *     available_services: [{ id, total_amount, total_currency, passenger_id }] }
 */
export default function SeatMapModal({
  open, onClose, seatMaps = [], passengers = [], initialSelected = {}, onApply,
}) {
  const { t } = useTranslation(['flights'])
  const fmt = useFormatCurrency()

  const [segIdx, setSegIdx] = useState(0)
  const [paxIdx, setPaxIdx] = useState(0)
  const [selected, setSelected] = useState(initialSelected)

  const allRows = useMemo(() => {
    const m = seatMaps[segIdx]
    if (!m) return []
    const rows = []
    for (const cabin of m.cabins || []) {
      for (const row of cabin.rows || []) {
        rows.push({ cabin, row })
      }
    }
    return rows
  }, [seatMaps, segIdx])

  if (!open) return null

  const segments = seatMaps.map((_, i) => i)

  const isPickedByOther = (designator) => {
    return Object.entries(selected).some(([k, val]) => {
      return Number(k) !== paxIdx && val?._designator === designator
    })
  }

  const pickedForCurrentPax = selected[paxIdx]

  const pickSeat = (element) => {
    if (!element.available_services?.length) return
    if (isPickedByOther(element.designator)) return
    const svc = element.available_services[0]
    setSelected((prev) => ({
      ...prev,
      [paxIdx]: {
        service_id: svc.id,
        _designator: element.designator,
        amount: svc.total_amount,
        currency: svc.total_currency,
      },
    }))
  }

  const clearForPax = () => {
    setSelected((prev) => {
      const next = { ...prev }
      delete next[paxIdx]
      return next
    })
  }

  const handleApply = () => {
    const out = {}
    for (const [k, v] of Object.entries(selected)) {
      if (v?.service_id) out[k] = v.service_id
    }
    onApply?.(out)
    onClose?.()
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <div>
            <h2 className="font-heading font-bold text-lg">{t('flights:seats.title')}</h2>
            <p className="text-xs text-gray-400">{t('flights:seats.subtitle')}</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-full">
            <X className="w-4 h-4" />
          </button>
        </div>

        {seatMaps.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center py-16 text-gray-400">
            <Armchair className="w-12 h-12 mb-3 opacity-30" />
            <p className="text-sm">{t('flights:seats.noSeatMap')}</p>
          </div>
        ) : (
          <>
            {/* Segment tabs (only show if >1) */}
            {segments.length > 1 && (
              <div className="px-6 py-2 border-b flex gap-2 text-sm">
                {segments.map((i) => (
                  <button
                    key={i}
                    onClick={() => setSegIdx(i)}
                    className={`px-3 py-1 rounded-full font-medium transition-colors ${
                      segIdx === i
                        ? 'bg-primary text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    {t('flights:seats.segment', { n: i + 1 })}
                  </button>
                ))}
              </div>
            )}

            {/* Passenger picker */}
            <div className="px-6 py-3 border-b flex gap-2 text-sm flex-wrap">
              {passengers.map((p, i) => {
                const seat = selected[i]
                const label = (p.first_name || p.last_name)
                  ? `${p.first_name || ''} ${p.last_name || ''}`.trim()
                  : t('flights:seats.passengerN', { n: i + 1 })
                return (
                  <button
                    key={i}
                    onClick={() => setPaxIdx(i)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-full border transition-colors ${
                      paxIdx === i
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'bg-white border-gray-200 hover:border-primary'
                    }`}
                  >
                    <span className="w-5 h-5 rounded-full bg-primary text-white flex items-center justify-center text-xs">
                      {i + 1}
                    </span>
                    <span className="text-xs font-medium">{label}</span>
                    {seat && (
                      <span className="font-mono text-xs text-primary font-bold">{seat._designator}</span>
                    )}
                  </button>
                )
              })}
            </div>

            {/* Legend */}
            <div className="px-6 py-2 flex gap-4 text-xs text-gray-500 border-b">
              <LegendSwatch className="bg-white border-gray-300">{t('flights:seats.available')}</LegendSwatch>
              <LegendSwatch className="bg-primary border-primary">{t('flights:seats.selected')}</LegendSwatch>
              <LegendSwatch className="bg-gray-300 border-gray-300">{t('flights:seats.occupied')}</LegendSwatch>
            </div>

            {/* Seat grid */}
            <div className="flex-1 overflow-y-auto px-6 py-4 bg-gray-50">
              <div className="max-w-md mx-auto space-y-1">
                {allRows.map(({ row }, rowIdx) => (
                  <div key={rowIdx} className="flex items-center gap-1 justify-center">
                    <span className="text-xs text-gray-400 w-6 text-right">{row.number || ''}</span>
                    {(row.sections || []).map((section, secIdx) => (
                      <div key={secIdx} className="flex gap-1 px-1">
                        {(section.elements || []).map((el, elIdx) => {
                          if (el.type !== 'seat') {
                            return (
                              <div
                                key={elIdx}
                                className="w-8 h-8 flex items-center justify-center text-[10px] text-gray-400"
                                title={el.type}
                              >
                                {el.type === 'exit_row' ? '⎯' : ''}
                              </div>
                            )
                          }
                          const available = (el.available_services?.length || 0) > 0
                          const designator = el.designator
                          const occupiedByOther = isPickedByOther(designator)
                          const pickedHere = pickedForCurrentPax?._designator === designator
                          const price = el.available_services?.[0]?.total_amount
                          const currency = el.available_services?.[0]?.total_currency
                          let cls = 'bg-white border-gray-300 hover:border-primary text-gray-700 cursor-pointer'
                          if (!available) cls = 'bg-gray-200 border-gray-200 text-gray-400 cursor-not-allowed'
                          if (occupiedByOther) cls = 'bg-gray-300 border-gray-300 text-gray-500 cursor-not-allowed'
                          if (pickedHere) cls = 'bg-primary border-primary text-white font-bold'

                          return (
                            <button
                              key={elIdx}
                              type="button"
                              onClick={() => pickSeat(el)}
                              disabled={!available || occupiedByOther}
                              title={designator + (price ? ` · ${fmt(parseFloat(price), currency)}` : '')}
                              className={`w-8 h-8 rounded-md border text-[10px] flex items-center justify-center transition-colors ${cls}`}
                            >
                              {designator?.slice(-1)}
                            </button>
                          )
                        })}
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        <div className="px-6 py-4 border-t flex items-center justify-between gap-3">
          {pickedForCurrentPax ? (
            <button
              onClick={clearForPax}
              className="text-sm text-gray-500 hover:text-gray-700 underline"
            >
              Clear
            </button>
          ) : <span />}
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100"
            >
              {t('flights:seats.cancel')}
            </button>
            <button
              onClick={handleApply}
              className="bg-primary hover:bg-primary/90 text-white font-medium px-5 py-2 rounded-lg text-sm"
            >
              {t('flights:seats.apply')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function LegendSwatch({ className, children }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-4 h-4 rounded-sm border ${className}`} />
      {children}
    </span>
  )
}
