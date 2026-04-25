import { formatCurrency } from '@/utils/formatters'

export default function PriceBreakdown({ pricePerNight, nights, discount = 0, currency = 'USD' }) {
  const subtotal = pricePerNight * nights
  const taxes = Math.round(subtotal * 0.1 * 100) / 100
  const total = subtotal + taxes - discount

  return (
    <div className="space-y-2 text-sm">
      <div className="flex justify-between">
        <span className="text-gray-600">
          {formatCurrency(pricePerNight, currency)} x {nights} night{nights > 1 ? 's' : ''}
        </span>
        <span>{formatCurrency(subtotal, currency)}</span>
      </div>
      <div className="flex justify-between">
        <span className="text-gray-600">Taxes & fees (10%)</span>
        <span>{formatCurrency(taxes, currency)}</span>
      </div>
      {discount > 0 && (
        <div className="flex justify-between text-success">
          <span>Discount</span>
          <span>-{formatCurrency(discount, currency)}</span>
        </div>
      )}
      <hr />
      <div className="flex justify-between font-bold text-base">
        <span>Total</span>
        <span className="text-primary">{formatCurrency(total, currency)}</span>
      </div>
    </div>
  )
}
