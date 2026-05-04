import { format, parseISO, differenceInDays } from 'date-fns'

const USD_TO_VND = 25_000

export function formatCurrency(amountUsd, currency = 'USD') {
  if (currency === 'VND') {
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

export function formatDate(dateStr, fmt = 'MMM dd, yyyy') {
  if (!dateStr) return ''
  const d = typeof dateStr === 'string' ? parseISO(dateStr) : dateStr
  return format(d, fmt)
}

export function nightsBetween(checkIn, checkOut) {
  if (!checkIn || !checkOut) return 0
  const a = typeof checkIn === 'string' ? parseISO(checkIn) : checkIn
  const b = typeof checkOut === 'string' ? parseISO(checkOut) : checkOut
  return Math.max(differenceInDays(b, a), 0)
}

export function truncate(str, max = 100) {
  if (!str || str.length <= max) return str
  return str.slice(0, max) + '...'
}

export function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/[\s_]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function starArray(count) {
  return Array.from({ length: 5 }, (_, i) => i < count)
}
