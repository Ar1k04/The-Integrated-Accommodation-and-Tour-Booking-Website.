import { useTranslation } from 'react-i18next'
import { CheckCircle, Coffee, AlertCircle } from 'lucide-react'
import { OccupancySlot, BedInfo } from './_internal'

/**
 * Booking.com-style "Recommended for N adults" panel. Renders the precomputed
 * combination from `recommendCombination()` and surfaces a single
 * "Reserve your selections" button that yields the chosen items.
 *
 * Props:
 *   recommendation: result of recommendCombination(...)
 *   nights:         number of nights for the search window
 *   guests:         total adults requested
 *   fmt:            currency formatter (useFormatCurrency hook)
 *   onReserve:      (items) => void — called with `recommendation.items`
 */
export default function RoomRecommendation({ recommendation, nights, guests, adults, children = 0, fmt, onReserve }) {
  const { t } = useTranslation(['hotels', 'common'])
  if (!recommendation || !recommendation.items?.length) return null

  const { items, totalPrice, totalTaxes } = recommendation
  const stayPrice = totalPrice * Math.max(nights, 1)
  const stayTaxes = (totalTaxes || 0) * Math.max(nights, 1)
  // When the caller passes `adults` (new API), use it; fall back to `guests`
  // for callers still on the legacy single-count API.
  const adultsCount = adults != null ? adults : guests
  const headerLabel = children > 0
    ? t('hotels:detail.recommendedForAdultsChildren', { adults: adultsCount, count: children })
    : t('hotels:detail.recommendedForAdults', { count: adultsCount })
  const stayLabel = children > 0
    ? t('hotels:detail.nightsAdultsChildren', { nights, adults: adultsCount, count: children })
    : t('hotels:detail.nightsAdults', { nights, guests: adultsCount })

  const expandedFrom = recommendation.expandedFromRooms
  const expandedToRooms = recommendation.totalRooms

  return (
    <div className="rounded-xl border border-gray-200 overflow-hidden mb-6 shadow-sm">
      <div className="bg-white px-4 py-3 border-b border-gray-200">
        <h3 className="font-bold text-gray-900 text-base">
          {headerLabel}
        </h3>
        {expandedFrom != null && (
          <div className="mt-2 flex items-start gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2.5 py-1.5">
            <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
            <span>
              {t('hotels:detail.expandedRoomsNote', {
                requested: expandedFrom,
                used: expandedToRooms,
                defaultValue: 'We split your party across {{used}} rooms to comfortably fit everyone ({{requested}} requested).',
              })}
            </span>
          </div>
        )}
      </div>

      {/* Desktop layout: 3-column grid, sticky reserve panel on the right */}
      <div className="hidden md:grid grid-cols-12">
        {/* Left/middle: rows */}
        <div className="col-span-9 divide-y divide-gray-200">
          {items.map((item) => (
            <RecommendationRow key={item.group.id} item={item} nights={nights} fmt={fmt} t={t} />
          ))}
        </div>

        {/* Right reserve panel */}
        <div className="col-span-3 bg-white p-5 border-l border-gray-200 flex flex-col gap-3">
          <p className="text-sm text-gray-600">
            {stayLabel}
          </p>
          <div>
            <p className="text-2xl font-bold text-gray-900">{fmt(stayPrice)}</p>
            {stayTaxes > 0 && (
              <p className="text-xs text-gray-500 mt-1">
                {t('hotels:detail.taxesAndFees', { amount: fmt(stayTaxes) })}
              </p>
            )}
          </div>
          <button
            onClick={() => onReserve(items)}
            className="w-full bg-primary hover:bg-primary-dark text-white font-bold py-3 rounded-lg transition-colors text-sm"
          >
            {t('hotels:detail.reserveYourSelections')}
          </button>
          <p className="text-[11px] text-gray-500 leading-snug">
            {t('hotels:detail.wontChargeAnything')}
          </p>
        </div>
      </div>

      {/* Mobile: stacked rows + bottom panel */}
      <div className="md:hidden">
        <div className="divide-y divide-gray-200">
          {items.map((item) => (
            <RecommendationRow
              key={`m-${item.group.id}`}
              item={item}
              nights={nights}
              fmt={fmt}
              t={t}
              compact
            />
          ))}
        </div>
        <div className="bg-white p-4 border-t border-gray-200 space-y-2">
          <p className="text-sm text-gray-600">
            {stayLabel}
          </p>
          <p className="text-2xl font-bold text-gray-900">{fmt(stayPrice)}</p>
          {stayTaxes > 0 && (
            <p className="text-xs text-gray-500">
              {t('hotels:detail.taxesAndFees', { amount: fmt(stayTaxes) })}
            </p>
          )}
          <button
            onClick={() => onReserve(items)}
            className="w-full bg-primary hover:bg-primary-dark text-white font-bold py-3 rounded-lg transition-colors text-sm"
          >
            {t('hotels:detail.reserveYourSelections')}
          </button>
          <p className="text-[11px] text-gray-500">{t('hotels:detail.wontChargeAnything')}</p>
        </div>
      </div>
    </div>
  )
}

function RecommendationRow({ item, nights, fmt, t, compact = false }) {
  const { group, rate, quantity, perUnitGuests, perUnitSlots } = item
  // Prefer the new slot composition (adults + child ages); fall back to the
  // legacy count list for callers still passing { guests } only.
  const slots = perUnitSlots && perUnitSlots.length > 0
    ? perUnitSlots
    : (perUnitGuests || []).map((n) => ({ adults: n, childAges: [] }))
  const stayPriceForRow =
    (rate.price_excl_taxes != null ? rate.price_excl_taxes : rate.price) *
    quantity *
    Math.max(nights, 1)
  const stayTaxesForRow = (rate.taxes || 0) * quantity * Math.max(nights, 1)
  const lowStock = group.total_quantity != null && group.total_quantity > 0 && group.total_quantity <= 5
  const breakfast = (rate.board_name || '').toLowerCase().includes('breakfast')

  return (
    <div className={compact ? 'p-4' : 'grid grid-cols-12 p-4 gap-4'}>
      {/* Room info column */}
      <div className={compact ? '' : 'col-span-8'}>
        <p className="text-sm text-gray-900 mb-1">
          <span className="font-semibold">{quantity} ×</span>{' '}
          <a className="text-primary font-semibold hover:underline cursor-pointer">{group.name}</a>
        </p>
        <p className="text-xs text-gray-700 mb-1 flex flex-wrap items-center gap-2">
          <span className="font-medium">{t('hotels:detail.priceForLabel')}</span>
          {slots.map((slot, i) => (
            <span key={i} className="inline-flex items-center">
              <OccupancySlot adults={slot.adults} childAges={slot.childAges} />
              {i < slots.length - 1 && <span className="text-gray-400 mx-1">,</span>}
            </span>
          ))}
        </p>
        {group.room_type && (
          <p className="text-xs text-gray-700 mb-1">
            <span className="font-semibold">
              {quantity > 1 ? t('hotels:detail.eachUnitHas') : t('hotels:detail.bedsLabel')}
            </span>{' '}
            <BedInfo roomType={group.room_type} />
          </p>
        )}
        <ul className="text-xs space-y-1 mt-2">
          <li className="flex items-start gap-1.5">
            <CheckCircle className="w-3.5 h-3.5 text-green-600 shrink-0 mt-0.5" />
            <span className="text-green-700 font-medium">
              {rate.refundable
                ? t('hotels:detail.freeCancellationAnytime')
                : t('hotels:detail.nonRefundableShort')}
            </span>
          </li>
          <li className="flex items-start gap-1.5">
            <CheckCircle className="w-3.5 h-3.5 text-green-600 shrink-0 mt-0.5" />
            <span className="text-green-700">
              <span className="font-medium">{t('hotels:detail.noPrepayment')}</span>
            </span>
          </li>
          {breakfast && (
            <li className="flex items-start gap-1.5 text-gray-600">
              <Coffee className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <span>{t('hotels:detail.breakfastIncluded')}</span>
            </li>
          )}
        </ul>
        {lowStock && (
          <p className="text-xs text-red-600 font-medium mt-2 flex items-center gap-1">
            <span className="inline-block w-2 h-2 bg-red-500 rounded-full"></span>
            {t('hotels:detail.weHaveNLeft', { count: group.total_quantity })}
          </p>
        )}
      </div>

      {/* Per-row price column (desktop) / inline summary (mobile) */}
      <div className={compact ? 'mt-3 flex items-end justify-between' : 'col-span-4 text-right'}>
        <div className={compact ? '' : 'inline-block text-left'}>
          <p className="text-lg font-bold text-gray-900">{fmt(stayPriceForRow)}</p>
          {stayTaxesForRow > 0 && (
            <p className="text-xs text-gray-500 mt-0.5">
              {t('hotels:detail.taxesAndFees', { amount: fmt(stayTaxesForRow) })}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
