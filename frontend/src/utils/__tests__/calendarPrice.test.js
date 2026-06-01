import { describe, it, expect } from 'vitest'
import {
  getCalendarPriceEstimate,
  formatCalendarPrice,
  formatCalendarPriceVnd,
} from '@/utils/calendarPrice'

// Khoảng hệ số kỳ vọng theo thứ trong tuần (multiplier ± stableOffset 0.04).
// Fri(5)/Sat(6): 1.08 ; Sun(0): 1.04 ; ngày thường: 1.00
function factorBand(day) {
  const d = day.getDay()
  if (d === 5 || d === 6) return [1.04, 1.12]
  if (d === 0) return [1.0, 1.08]
  return [0.96, 1.04]
}

describe('getCalendarPriceEstimate', () => {
  it('returns null for invalid or non-positive base price', () => {
    expect(getCalendarPriceEstimate(0, new Date(2026, 5, 1))).toBeNull()
    expect(getCalendarPriceEstimate(-10, new Date(2026, 5, 1))).toBeNull()
    expect(getCalendarPriceEstimate(NaN, new Date(2026, 5, 1))).toBeNull()
    expect(getCalendarPriceEstimate('abc', new Date(2026, 5, 1))).toBeNull()
  })

  it('is deterministic for the same base price and day', () => {
    const day = new Date(2026, 5, 10)
    expect(getCalendarPriceEstimate(120, day)).toBe(getCalendarPriceEstimate(120, day))
  })

  it('applies weekend/weekday multiplier within the expected band', () => {
    const base = 1000
    for (let i = 0; i < 14; i++) {
      const day = new Date(2026, 5, 1 + i)
      const est = getCalendarPriceEstimate(base, day)
      const [lo, hi] = factorBand(day)
      expect(est).toBeGreaterThanOrEqual(base * lo - 1)
      expect(est).toBeLessThanOrEqual(base * hi + 1)
    }
  })

  it('never returns below the 1 floor for tiny base prices', () => {
    const est = getCalendarPriceEstimate(0.001, new Date(2026, 5, 1))
    expect(est).toBeGreaterThanOrEqual(1)
  })
})

describe('formatCalendarPrice (USD)', () => {
  it('shows up to 2 decimals under $100', () => {
    expect(formatCalendarPrice(50, 'USD')).toBe('$50')
    expect(formatCalendarPrice(49.5, 'USD')).toBe('$49.5')
  })

  it('rounds to whole dollars at or above $100', () => {
    expect(formatCalendarPrice(1234, 'USD')).toBe('$1,234')
  })

  it('treats missing amount as zero', () => {
    expect(formatCalendarPrice(undefined, 'USD')).toBe('$0')
    expect(formatCalendarPrice(0, 'USD')).toBe('$0')
  })

  it('delegates to VND formatter when currency is VND', () => {
    expect(formatCalendarPrice(1, 'VND', 25000)).toBe('25K')
  })
})

describe('formatCalendarPriceVnd', () => {
  it('converts USD to thousands of VND with a K suffix', () => {
    expect(formatCalendarPriceVnd(1, 25000)).toBe('25K')
    expect(formatCalendarPriceVnd(100, 25000)).toBe('2.500K') // vi-VN dùng "." ngăn cách nghìn
  })

  it('falls back to the default 25000 rate when rate is falsy', () => {
    expect(formatCalendarPriceVnd(1, 0)).toBe('25K')
    expect(formatCalendarPriceVnd(1, undefined)).toBe('25K')
  })

  it('keeps at least 1K for very small amounts', () => {
    expect(formatCalendarPriceVnd(0.00001, 25000)).toBe('1K')
  })
})
