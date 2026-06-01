import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useInfiniteScroll } from '@/hooks/useInfiniteScroll'

// jsdom không có IntersectionObserver → cung cấp mock bắt được callback.
let observerCallback
class MockIntersectionObserver {
  constructor(cb) {
    observerCallback = cb
    this.observe = vi.fn()
    this.disconnect = vi.fn()
  }
}

beforeEach(() => {
  observerCallback = undefined
  global.IntersectionObserver = MockIntersectionObserver
})

describe('useInfiniteScroll', () => {
  it('invokes the callback when the sentinel intersects', () => {
    const cb = vi.fn()
    const { result } = renderHook(() => useInfiniteScroll(cb))
    act(() => result.current(document.createElement('div'))) // gắn ref → tạo observer
    act(() => observerCallback([{ isIntersecting: true }]))
    expect(cb).toHaveBeenCalledTimes(1)
  })

  it('does not invoke the callback when not intersecting', () => {
    const cb = vi.fn()
    const { result } = renderHook(() => useInfiniteScroll(cb))
    act(() => result.current(document.createElement('div')))
    act(() => observerCallback([{ isIntersecting: false }]))
    expect(cb).not.toHaveBeenCalled()
  })

  it('does not observe when disabled', () => {
    const cb = vi.fn()
    const { result } = renderHook(() => useInfiniteScroll(cb, { enabled: false }))
    act(() => result.current(document.createElement('div')))
    // enabled=false → ref callback trả về sớm, không tạo observer.
    expect(observerCallback).toBeUndefined()
    expect(cb).not.toHaveBeenCalled()
  })
})
