import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDebounce } from '@/hooks/useDebounce'

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe('useDebounce', () => {
  it('returns the initial value immediately', () => {
    const { result } = renderHook(() => useDebounce('a', 300))
    expect(result.current).toBe('a')
  })

  it('updates only after the delay elapses', () => {
    const { result, rerender } = renderHook(({ v }) => useDebounce(v, 300), {
      initialProps: { v: 'a' },
    })
    rerender({ v: 'b' })
    expect(result.current).toBe('a') // chưa đủ delay
    act(() => vi.advanceTimersByTime(300))
    expect(result.current).toBe('b')
  })

  it('resets the timer on rapid successive changes', () => {
    const { result, rerender } = renderHook(({ v }) => useDebounce(v, 300), {
      initialProps: { v: 'a' },
    })
    rerender({ v: 'b' })
    act(() => vi.advanceTimersByTime(200))
    rerender({ v: 'c' })
    act(() => vi.advanceTimersByTime(200))
    expect(result.current).toBe('a') // chưa lần nào giữ đủ 300ms liên tục
    act(() => vi.advanceTimersByTime(100))
    expect(result.current).toBe('c')
  })
})
