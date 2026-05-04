import { useTranslation } from 'react-i18next'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'

export default function PriceBreakdown({ pricePerNight, nights, discount = 0, labelOverride }) {
  const { t } = useTranslation('common')
  const fmt = useFormatCurrency()
  const subtotal = pricePerNight * nights
  const taxes = Math.round(subtotal * 0.1 * 100) / 100
  const total = subtotal + taxes - discount
  const perLabel = labelOverride || t('common.perNight')

  return (
    <div className="space-y-2 text-sm">
      <div className="flex justify-between">
        <span className="text-gray-600">
          {fmt(pricePerNight)} x {nights} {perLabel}
        </span>
        <span>{fmt(subtotal)}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-gray-600">{t('common.taxes')} (10%)</span>
        <span>{fmt(taxes)}</span>
      </div>
      {discount > 0 && (
        <div className="flex justify-between text-success">
          <span>{t('common.discount')}</span>
          <span>-{fmt(discount)}</span>
        </div>
      )}
      <hr />
      <div className="flex justify-between font-bold text-base">
        <span>{t('common.total')}</span>
        <span className="text-primary">{fmt(total)}</span>
      </div>
    </div>
  )
}
