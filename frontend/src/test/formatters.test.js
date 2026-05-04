import { describe, it, expect } from 'vitest'
import { formatCurrency, nightsBetween, truncate, slugify, starArray } from '@/utils/formatters'

describe('formatCurrency', () => {
  it('formats USD correctly', () => {
    expect(formatCurrency(150)).toBe('$150')
    expect(formatCurrency(1250.99)).toBe('$1,250.99')
  })

  it('formats EUR', () => {
    const result = formatCurrency(100, 'EUR')
    expect(result).toContain('100')
  })

  it('handles zero', () => {
    expect(formatCurrency(0)).toBe('$0')
  })

  it('formats VND with multiplied amount', () => {
    const vnd = formatCurrency(50, 'VND')
    expect(vnd).toContain('₫')
    expect(vnd).toContain('1.250.000')
  })
})

describe('nightsBetween', () => {
  it('calculates nights between dates', () => {
    expect(nightsBetween('2026-03-01', '2026-03-05')).toBe(4)
  })

  it('returns 0 for same dates', () => {
    expect(nightsBetween('2026-03-01', '2026-03-01')).toBe(0)
  })

  it('returns 0 for missing dates', () => {
    expect(nightsBetween(null, null)).toBe(0)
  })
})

describe('truncate', () => {
  it('truncates long strings', () => {
    const long = 'a'.repeat(150)
    expect(truncate(long, 100)).toHaveLength(103) // 100 + '...'
  })

  it('keeps short strings', () => {
    expect(truncate('hello', 100)).toBe('hello')
  })

  it('handles null', () => {
    expect(truncate(null)).toBeNull()
  })
})

describe('slugify', () => {
  it('converts to slug', () => {
    expect(slugify('Hello World')).toBe('hello-world')
  })

  it('removes special chars', () => {
    expect(slugify('Café & Bar!')).toBe('caf-bar')
  })
})

describe('starArray', () => {
  it('returns correct boolean array', () => {
    const result = starArray(3)
    expect(result).toEqual([true, true, true, false, false])
  })

  it('handles 5 stars', () => {
    expect(starArray(5)).toEqual([true, true, true, true, true])
  })

  it('handles 0 stars', () => {
    expect(starArray(0)).toEqual([false, false, false, false, false])
  })
})
