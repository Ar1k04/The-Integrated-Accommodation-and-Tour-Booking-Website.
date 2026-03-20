import { format, parseISO, differenceInDays } from 'date-fns'

export function formatCurrency(amount, currency = 'USD') {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount)
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
