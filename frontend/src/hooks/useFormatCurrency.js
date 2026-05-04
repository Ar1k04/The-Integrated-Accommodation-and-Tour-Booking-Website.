import { useUiStore } from '@/store/uiStore'

const USD_TO_VND = 25_000

export function useFormatCurrency() {
  const currency = useUiStore((s) => s.currency)

  return function fmt(amountUsd, currencyOverride) {
    const cur = currencyOverride || currency || 'USD'
    if (cur === 'VND') {
      const vnd = Math.round((amountUsd || 0) * USD_TO_VND)
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
