import { useTranslation } from 'react-i18next'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'

/**
 * FareBreakdownCard — base + taxes + services + total.
 *
 * Props:
 *   offer: { base_amount?, tax_amount?, total_amount, currency }
 *   paxCount: number
 *   servicesTotal: number  — sum of selected ancillary prices
 */
export default function FareBreakdownCard({ offer, paxCount = 1, servicesTotal = 0 }) {
  const { t } = useTranslation(['flights'])
  const fmt = useFormatCurrency()

  if (!offer) return null

  const total = (offer.total_amount || 0) + (servicesTotal || 0)
  const perPax = paxCount > 0 ? total / paxCount : total
  const hasBreakdown = offer.base_amount != null && offer.tax_amount != null

  return (
    <div className="bg-white border rounded-xl p-5 space-y-3">
      <h3 className="font-heading font-bold text-sm">
        {t('flights:fareBreakdown.title')}
      </h3>

      <div className="space-y-1.5 text-sm">
        {hasBreakdown ? (
          <>
            <Row label={t('flights:fareBreakdown.base')} value={fmt(offer.base_amount, offer.currency)} />
            <Row label={t('flights:fareBreakdown.taxes')} value={fmt(offer.tax_amount, offer.currency)} />
          </>
        ) : (
          <Row
            label={`${t('flights:detail.perPersonTotalFare')} × ${paxCount}`}
            value={fmt(offer.total_amount, offer.currency)}
          />
        )}

        {servicesTotal > 0 && (
          <Row
            label={t('flights:fareBreakdown.services')}
            value={fmt(servicesTotal, offer.currency)}
          />
        )}

        <hr className="my-2" />

        <Row
          label={t('flights:fareBreakdown.total')}
          value={fmt(total, offer.currency)}
          bold
        />
        {paxCount > 1 && (
          <p className="text-xs text-gray-400 text-right">
            ≈ {fmt(perPax, offer.currency)} {t('flights:fareBreakdown.perPax')}
          </p>
        )}
      </div>
    </div>
  )
}

function Row({ label, value, bold }) {
  return (
    <div className={`flex justify-between ${bold ? 'font-bold text-gray-900' : 'text-gray-600'}`}>
      <span>{label}</span>
      <span>{value}</span>
    </div>
  )
}
