import { useUiStore } from '@/store/uiStore'

export function useFormatCurrency() {
  const currency = useUiStore((s) => s.currency)
  const usdToVnd = useUiStore((s) => s.usdToVnd)

  return function fmt(amountUsd, currencyOverride) {
    const cur = currencyOverride || currency || 'USD'
    if (cur === 'VND') {
      const vnd = Math.round((amountUsd || 0) * usdToVnd)
      return new Intl.NumberFormat('vi-VN', {
        style: 'currency',
        currency: 'VND',
        maximumFractionDigits: 0,
      }).format(vnd)
    }
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(amountUsd || 0)
  }
}
