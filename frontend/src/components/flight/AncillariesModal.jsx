import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Briefcase, Utensils, Sparkles, Minus, Plus } from 'lucide-react'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'

const TYPE_ICONS = {
  baggage: Briefcase,
  meal: Utensils,
}

function describeService(s, t) {
  if (s.type === 'baggage') {
    const meta = s.metadata || {}
    const subtype = meta.type === 'carry_on' ? 'Carry-on' : 'Checked'
    const weight = meta.maximum_weight_kg ? `${meta.maximum_weight_kg}kg` : ''
    return `${subtype} ${weight}`.trim() || t('flights:ancillaries.baggage')
  }
  if (s.type === 'meal') {
    return s.metadata?.meal_type || t('flights:ancillaries.meals')
  }
  return s.metadata?.name || s.type || t('flights:ancillaries.other')
}

/**
 * AncillariesModal — tabbed picker for baggage / meals / other Duffel services.
 *
 * Props:
 *   open: bool
 *   onClose()
 *   services: Duffel available_services list
 *   passengers: PassengerInfo[]
 *   initialSelection: [{id, quantity}]
 *   onApply(selectedServices)
 */
export default function AncillariesModal({
  open, onClose, services = [], passengers = [], initialSelection = [], onApply,
}) {
  const { t } = useTranslation(['flights'])
  const fmt = useFormatCurrency()

  const [tab, setTab] = useState('baggage')
  const [quantities, setQuantities] = useState(() => {
    const map = {}
    for (const item of initialSelection) map[item.id] = item.quantity || 0
    return map
  })

  // Group services by type
  const grouped = useMemo(() => {
    const out = { baggage: [], meal: [], other: [] }
    for (const s of services) {
      if (s.type === 'baggage') out.baggage.push(s)
      else if (s.type === 'meal') out.meal.push(s)
      else out.other.push(s)
    }
    return out
  }, [services])

  const tabs = [
    { key: 'baggage', icon: Briefcase, label: t('flights:ancillaries.baggage'), count: grouped.baggage.length },
    { key: 'meal', icon: Utensils, label: t('flights:ancillaries.meals'), count: grouped.meal.length },
    { key: 'other', icon: Sparkles, label: t('flights:ancillaries.other'), count: grouped.other.length },
  ]

  const total = useMemo(() => {
    return services.reduce((acc, s) => {
      const q = quantities[s.id] || 0
      return acc + q * (parseFloat(s.total_amount) || 0)
    }, 0)
  }, [services, quantities])

  const currency = services.find((s) => quantities[s.id])?.total_currency
    || services[0]?.total_currency

  const handleApply = () => {
    const out = Object.entries(quantities)
      .filter(([, q]) => q > 0)
      .map(([id, quantity]) => ({ id, quantity }))
    onApply?.(out)
    onClose?.()
  }

  if (!open) return null

  const bump = (id, delta, max) => {
    setQuantities((prev) => {
      const cur = prev[id] || 0
      const next = Math.max(0, Math.min(max ?? 9, cur + delta))
      return { ...prev, [id]: next }
    })
  }

  const groupedForTab = grouped[tab] || []

  return (
    <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={onClose}>
      <div
        className="bg-white rounded-2xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <div>
            <h2 className="font-heading font-bold text-lg">{t('flights:ancillaries.title')}</h2>
            <p className="text-xs text-gray-400">{t('flights:ancillaries.subtitle')}</p>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-gray-100 rounded-full">
            <X className="w-4 h-4" />
          </button>
        </div>

        {services.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center py-12 text-gray-400">
            <Briefcase className="w-12 h-12 mb-3 opacity-30" />
            <p className="text-sm">{t('flights:ancillaries.noServices')}</p>
          </div>
        ) : (
          <>
            {/* Tab bar */}
            <div className="px-6 py-3 border-b flex gap-2">
              {tabs.map((tb) => {
                const Icon = tb.icon
                return (
                  <button
                    key={tb.key}
                    onClick={() => setTab(tb.key)}
                    disabled={tb.count === 0}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors disabled:opacity-40 ${
                      tab === tb.key
                        ? 'bg-primary text-white'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {tb.label}
                    <span className="text-xs opacity-70">({tb.count})</span>
                  </button>
                )
              })}
            </div>

            {/* Service list */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2">
              {groupedForTab.length === 0 && (
                <p className="text-center text-sm text-gray-400 py-8">
                  {t('flights:ancillaries.noServices')}
                </p>
              )}
              {groupedForTab.map((s) => {
                const q = quantities[s.id] || 0
                const Icon = TYPE_ICONS[s.type] || Sparkles
                const max = s.maximum_quantity ?? 9
                const paxIdx = (s.passenger_ids && s.passenger_ids.length > 0)
                  ? passengers.findIndex((_, i) => i === 0)
                  : null
                const paxLabel = (paxIdx != null && passengers[0])
                  ? `${passengers[0].first_name || 'Passenger'} ${passengers[0].last_name || ''}`.trim()
                  : null
                return (
                  <div key={s.id} className="border rounded-xl p-3 flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                      <Icon className="w-5 h-5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-sm text-gray-900 truncate">
                        {describeService(s, t)}
                      </p>
                      {paxLabel && (
                        <p className="text-xs text-gray-400 truncate">{paxLabel}</p>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-sm font-bold">
                        {fmt(parseFloat(s.total_amount) || 0, s.total_currency)}
                      </p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        onClick={() => bump(s.id, -1, max)}
                        disabled={q === 0}
                        className="w-7 h-7 rounded-full border flex items-center justify-center disabled:opacity-30 hover:bg-gray-50"
                      >
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="w-6 text-center text-sm font-semibold">{q}</span>
                      <button
                        onClick={() => bump(s.id, 1, max)}
                        disabled={q >= max}
                        className="w-7 h-7 rounded-full border flex items-center justify-center disabled:opacity-30 hover:bg-gray-50"
                      >
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          </>
        )}

        <div className="px-6 py-4 border-t flex items-center justify-between gap-3">
          <div className="text-sm text-gray-500">
            {t('flights:ancillaries.total')}:
            <strong className="ml-2 text-gray-900">{fmt(total, currency)}</strong>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100"
            >
              {t('flights:ancillaries.cancel')}
            </button>
            <button
              onClick={handleApply}
              className="bg-primary hover:bg-primary/90 text-white font-medium px-5 py-2 rounded-lg text-sm"
            >
              {t('flights:ancillaries.apply')}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
