import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { useUiStore } from '@/store/uiStore'

beforeEach(() => useUiStore.setState({ currency: 'USD', usdToVnd: 25000 }))

describe('useFormatCurrency', () => {
  it('formats USD using the store currency', () => {
    const { result } = renderHook(() => useFormatCurrency())
    expect(result.current(50)).toBe('$50')
  })

  it('formats VND when the store currency is VND', () => {
    useUiStore.setState({ currency: 'VND', usdToVnd: 25000 })
    const { result } = renderHook(() => useFormatCurrency())
    expect(result.current(1)).toContain('₫') // 1 USD × 25000 = 25.000 ₫
  })

  it('honours an explicit currency override', () => {
    const { result } = renderHook(() => useFormatCurrency())
    expect(result.current(1, 'VND')).toContain('₫')
  })

  it('treats a null amount as zero', () => {
    const { result } = renderHook(() => useFormatCurrency())
    expect(result.current(null)).toBe('$0')
  })
})
