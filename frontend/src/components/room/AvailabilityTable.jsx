import { useState, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { differenceInDays } from 'date-fns'
import { CheckCircle, Info, ChevronDown, CreditCard } from 'lucide-react'
import {
  GuestIcons,
  AMENITY_ICONS,
  BedInfo,
  BoardBadge,
  CancellationLine,
} from './_internal'

/* ── main component ──────────────────────────────────────── */

/**
 * Booking.com-style availability table.
 *
 * Props:
 * - roomGroups: [{ id, name, room_type, max_guests, total_quantity?, amenities[], images[],
 *                  rates: [{ rate_id, board_name, refundable, cancellation_deadline?,
 *                            price, original_price?, discount_percent?, currency, max_occupancy }] }]
 * - checkIn, checkOut: ISO date strings (or empty)
 * - onReserve(group, perRateQuantities): called on "I'll reserve"
 * - onShowPrices: called when user clicks "Show prices" in the no-dates state
 * - fmt(value): currency formatter
 */
export default function AvailabilityTable({
  roomGroups,
  checkIn,
  checkOut,
  onReserve,
  onShowPrices,
  onSelectionChange,
  fmt,
}) {
  const { t } = useTranslation(['hotels', 'common'])
  const datesSelected = !!(checkIn && checkOut)
  const nights = datesSelected ? differenceInDays(new Date(checkOut), new Date(checkIn)) : 0

  // qty[groupId][rateId] = number
  const [qty, setQty] = useState({})
  const setRateQty = (groupId, rateId, n) => {
    const newQty = {
      ...qty,
      [groupId]: { ...(qty[groupId] || {}), [rateId]: n },
    }
    setQty(newQty)
    onSelectionChange?.(newQty)
  }

  const groupTotalQty = (groupId) =>
    Object.values(qty[groupId] || {}).reduce((s, n) => s + (n || 0), 0)

  if (!roomGroups || roomGroups.length === 0) {
    return <p className="text-gray-400 text-sm py-4">{t('hotels:detail.noRoomsAvailable')}</p>
  }

  /* ═══════════════ NO DATES SELECTED ═══════════════ */
  if (!datesSelected) {
    return (
      <div className="availability-table">
        <div className="flex items-start gap-2 bg-amber-50 border border-amber-300 rounded-lg px-4 py-3 mb-4">
          <Info className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
          <p className="text-sm text-amber-800 font-medium">{t('hotels:detail.selectDatesToSee')}</p>
        </div>

        {/* Desktop */}
        <div className="hidden md:block border border-gray-200 rounded-xl overflow-hidden">
          <div className="bg-primary text-white grid grid-cols-12 text-sm font-semibold">
            <div className="col-span-6 px-4 py-3">{t('hotels:detail.roomType')}</div>
            <div className="col-span-3 px-4 py-3">{t('hotels:detail.numberOfGuests')}</div>
            <div className="col-span-3 px-4 py-3"></div>
          </div>
          {roomGroups.map((group, idx) => (
            <div
              key={group.id}
              className={`grid grid-cols-12 border-t border-gray-200 ${
                idx % 2 === 1 ? 'bg-gray-50/50' : 'bg-white'
              }`}
            >
              <div className="col-span-6 px-4 py-4">
                <h3 className="font-semibold text-primary text-sm hover:underline cursor-pointer">
                  {group.name}
                </h3>
                <div className="mt-1.5">
                  <BedInfo roomType={group.room_type} />
                </div>
              </div>
              <div className="col-span-3 px-4 py-4 flex items-center">
                <GuestIcons count={group.max_guests} />
              </div>
              <div className="col-span-3 px-4 py-4 flex items-center justify-end">
                <button
                  onClick={onShowPrices}
                  className="bg-primary hover:bg-primary-dark text-white text-sm font-semibold px-4 py-2 rounded-md transition-colors whitespace-nowrap"
                >
                  {t('hotels:detail.showPrices')}
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Mobile */}
        <div className="md:hidden space-y-3 mt-4">
          {roomGroups.map((group) => (
            <div key={`m-${group.id}`} className="border rounded-xl p-4 bg-white">
              <h3 className="font-semibold text-primary text-sm">{group.name}</h3>
              <div className="mt-1">
                <BedInfo roomType={group.room_type} />
              </div>
              <div className="flex items-center justify-between mt-3">
                <GuestIcons count={group.max_guests} />
                <button
                  onClick={onShowPrices}
                  className="bg-primary hover:bg-primary-dark text-white text-xs font-semibold px-3 py-1.5 rounded-md transition-colors"
                >
                  {t('hotels:detail.showPrices')}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  /* ═══════════════ DATES SELECTED — multi-rate-plan grouping ═══════════════ */
  return (
    <div className="availability-table">
      {/* Desktop table */}
      <div className="hidden md:block border border-gray-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-primary text-white text-xs font-semibold">
              <th className="text-left px-4 py-3 w-[28%]">{t('hotels:detail.roomType')}</th>
              <th className="text-center px-2 py-3 w-[8%]">{t('hotels:detail.numberOfGuests')}</th>
              <th className="text-left px-2 py-3 w-[18%]">
                {t('hotels:detail.priceForNights', { count: nights })}
              </th>
              <th className="text-left px-2 py-3 w-[24%]">{t('hotels:detail.yourChoices')}</th>
              <th className="text-center px-2 py-3 w-[10%]">{t('hotels:detail.selectRooms')}</th>
              <th className="text-center px-2 py-3 w-[12%]"></th>
            </tr>
          </thead>
          <tbody>
            {roomGroups.map((group, gIdx) => {
              const rates = group.rates || []
              const rowSpan = Math.max(rates.length, 1)
              const totalQty = groupTotalQty(group.id)
              const stripe = gIdx % 2 === 1 ? 'bg-blue-50/30' : 'bg-white'

              if (rates.length === 0) {
                return (
                  <tr key={group.id} className={`${stripe} border-t border-gray-200`}>
                    <td className="px-4 py-4 align-top" colSpan={6}>
                      <RoomInfoCell group={group} t={t} />
                      <p className="text-xs text-gray-400 mt-2">
                        {t('hotels:detail.noRatesAvailable')}
                      </p>
                    </td>
                  </tr>
                )
              }

              return rates.map((rate, rIdx) => (
                <tr
                  key={`${group.id}:${rate.rate_id}`}
                  className={`${stripe} ${rIdx === 0 ? 'border-t-2 border-gray-300' : 'border-t border-dashed border-gray-200'}`}
                >
                  {rIdx === 0 && (
                    <td
                      rowSpan={rowSpan}
                      className="px-4 py-4 align-top border-r border-gray-200 bg-white"
                    >
                      <RoomInfoCell group={group} t={t} />
                    </td>
                  )}
                  <td className="px-2 py-4 text-center align-top border-r border-gray-100">
                    <GuestIcons count={rate.max_occupancy || group.max_guests} />
                  </td>
                  <td className="px-2 py-4 align-top border-r border-gray-100">
                    {rate.original_price && rate.original_price > rate.price && (
                      <p className="text-xs text-red-500 line-through">
                        {fmt(rate.original_price * Math.max(nights, 1))}
                      </p>
                    )}
                    <p className="text-lg font-bold text-gray-900">
                      {fmt(rate.price * Math.max(nights, 1))}
                    </p>
                    <p className="text-[11px] text-gray-500 mt-0.5">
                      {t('hotels:detail.includesTaxes')}
                    </p>
                    {rate.discount_percent ? (
                      <span className="inline-block mt-1.5 text-[10px] font-bold bg-green-700 text-white px-1.5 py-0.5 rounded">
                        {t('hotels:detail.percentOff', { percent: rate.discount_percent })}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-2 py-4 align-top space-y-1.5 border-r border-gray-100">
                    <BoardBadge boardName={rate.board_name} t={t} />
                    <CancellationLine rate={rate} t={t} />
                    <div className="flex items-start gap-1.5">
                      <CheckCircle className="w-3.5 h-3.5 text-green-600 shrink-0 mt-0.5" />
                      <span className="text-xs text-green-700">{t('hotels:detail.payAtProperty')}</span>
                    </div>
                    <div className="flex items-start gap-1.5">
                      <CreditCard className="w-3.5 h-3.5 text-green-600 shrink-0 mt-0.5" />
                      <span className="text-xs text-green-700">{t('hotels:detail.noCreditCard')}</span>
                    </div>
                  </td>
                  <td className="px-2 py-4 text-center align-top border-r border-gray-100">
                    <RateQtySelect
                      max={Math.min(group.total_quantity || 9, 9)}
                      value={qty[group.id]?.[rate.rate_id] || 0}
                      onChange={(n) => setRateQty(group.id, rate.rate_id, n)}
                    />
                  </td>
                  {rIdx === 0 && (
                    <td
                      rowSpan={rowSpan}
                      className="px-2 py-4 text-center align-top bg-white"
                    >
                      {totalQty > 0 ? (
                        <div className="flex flex-col items-stretch gap-2">
                          <button
                            onClick={() => onReserve(group, qty[group.id] || {})}
                            className="bg-primary hover:bg-primary-dark text-white text-xs font-bold py-2.5 px-3 rounded-md transition-colors"
                          >
                            {t('hotels:detail.illReserve')}
                          </button>
                          <ul className="text-[10px] text-gray-500 space-y-0.5 list-disc list-inside text-left">
                            <li>{t('hotels:detail.itOnlyTakes2Min')}</li>
                            <li>{t('hotels:detail.wontBeCharged')}</li>
                          </ul>
                        </div>
                      ) : (
                        <p className="text-[10px] text-gray-400 italic">
                          {t('hotels:detail.selectRooms')}
                        </p>
                      )}
                    </td>
                  )}
                </tr>
              ))
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile cards */}
      <div className="md:hidden space-y-4 mt-4">
        {roomGroups.map((group) => (
          <div key={`m-${group.id}`} className="border rounded-xl overflow-hidden bg-white">
            <div className="p-4 border-b border-gray-100">
              <RoomInfoCell group={group} t={t} compact />
            </div>
            {(group.rates || []).map((rate) => (
              <div key={rate.rate_id} className="p-4 border-b border-gray-100 last:border-b-0 bg-gray-50/40">
                <BoardBadge boardName={rate.board_name} t={t} />
                <div className="mt-2 space-y-1.5">
                  <CancellationLine rate={rate} t={t} />
                  <div className="flex items-center gap-1.5">
                    <CheckCircle className="w-3.5 h-3.5 text-green-600 shrink-0" />
                    <span className="text-xs text-green-700">{t('hotels:detail.payAtProperty')}</span>
                  </div>
                </div>
                <div className="mt-3 flex items-end justify-between">
                  <div>
                    {rate.original_price && rate.original_price > rate.price && (
                      <p className="text-xs text-red-500 line-through">
                        {fmt(rate.original_price * Math.max(nights, 1))}
                      </p>
                    )}
                    <p className="text-lg font-bold text-gray-900">
                      {fmt(rate.price * Math.max(nights, 1))}
                    </p>
                    <p className="text-[10px] text-gray-500">{t('hotels:detail.includesTaxes')}</p>
                  </div>
                  <RateQtySelect
                    max={Math.min(group.total_quantity || 9, 9)}
                    value={qty[group.id]?.[rate.rate_id] || 0}
                    onChange={(n) => setRateQty(group.id, rate.rate_id, n)}
                  />
                </div>
              </div>
            ))}
            {groupTotalQty(group.id) > 0 && (
              <div className="p-4 bg-white">
                <button
                  onClick={() => onReserve(group, qty[group.id] || {})}
                  className="w-full bg-primary hover:bg-primary-dark text-white text-sm font-bold py-2.5 rounded-md transition-colors"
                >
                  {t('hotels:detail.illReserve')}
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

/* ── sub-components ──────────────────────────────────────── */

function RoomInfoCell({ group, t, compact = false }) {
  const remaining = group.total_quantity
  return (
    <div>
      <h3 className="font-semibold text-primary text-sm hover:underline cursor-pointer">
        {group.name}
      </h3>
      {remaining != null && remaining > 0 && remaining <= 3 && (
        <p className="text-xs text-red-600 font-medium mt-1 flex items-center gap-1">
          <span className="inline-block w-2 h-2 bg-red-500 rounded-full"></span>
          {t('hotels:detail.weHaveNLeft', { count: remaining })}
        </p>
      )}
      {group.room_type && (
        <div className="mt-2">
          <BedInfo roomType={group.room_type} />
        </div>
      )}
      <div className="mt-2 flex items-center gap-2">
        <GuestIcons count={group.max_guests} />
      </div>
      {!compact && group.amenities?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {group.amenities.slice(0, 6).map((a) => {
            const key = String(a).toLowerCase().replace(/\s+/g, '_')
            const Icon = AMENITY_ICONS[key]
            return (
              <span
                key={a}
                className="inline-flex items-center gap-1 text-xs border border-gray-300 rounded px-1.5 py-0.5 text-gray-600 capitalize"
              >
                {Icon && <Icon className="w-3 h-3" />}
                {String(a).replace(/_/g, ' ')}
              </span>
            )
          })}
        </div>
      )}
      {!compact && group.amenities?.length > 6 && (
        <div className="mt-2 space-y-0.5">
          {group.amenities.slice(6, 12).map((a) => (
            <div key={a} className="flex items-center gap-1 text-xs text-gray-500">
              <CheckCircle className="w-3 h-3 text-green-500 shrink-0" />
              <span className="capitalize">{String(a).replace(/_/g, ' ')}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function RateQtySelect({ max, value, onChange }) {
  const options = useMemo(() => Array.from({ length: max + 1 }, (_, i) => i), [max])
  return (
    <div className="relative inline-block w-16">
      <select
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value, 10))}
        className="w-full border border-gray-300 rounded-md px-2 py-1.5 text-sm appearance-none bg-white pr-7 focus:outline-none focus:ring-2 focus:ring-primary"
      >
        {options.map((i) => (
          <option key={i} value={i}>
            {i}
          </option>
        ))}
      </select>
      <ChevronDown className="w-4 h-4 text-gray-400 absolute right-1.5 top-1/2 -translate-y-1/2 pointer-events-none" />
    </div>
  )
}
