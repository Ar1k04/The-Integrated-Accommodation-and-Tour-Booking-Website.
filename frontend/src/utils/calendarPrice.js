export function getCalendarPriceEstimate(basePriceUsd, day) {
  const base = Number(basePriceUsd)
  if (!Number.isFinite(base) || base <= 0) return null

  const dayOfWeek = day.getDay()
  const weekendMultiplier = dayOfWeek === 5 || dayOfWeek === 6 ? 1.08 : dayOfWeek === 0 ? 1.04 : 1
  const stableOffset = (((day.getFullYear() * 13) + ((day.getMonth() + 1) * 17) + (day.getDate() * 7)) % 9 - 4) / 100

  return Math.max(1, Math.round(base * (weekendMultiplier + stableOffset) * 100) / 100)
}

export function formatCalendarPrice(amountUsd, currency, usdToVnd) {
  if (currency === 'VND') return formatCalendarPriceVnd(amountUsd, usdToVnd)

  const amount = Number(amountUsd) || 0
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: amount < 100 ? 2 : 0,
  }).format(amount)
}

export function formatCalendarPriceVnd(amountUsd, usdToVnd) {
  const rate = Number(usdToVnd) || 25_000
  const amount = Number(amountUsd) || 0
  const thousandsVnd = Math.max(1, Math.round((amount * rate) / 1000))
  return `${new Intl.NumberFormat('vi-VN').format(thousandsVnd)}K`
}
