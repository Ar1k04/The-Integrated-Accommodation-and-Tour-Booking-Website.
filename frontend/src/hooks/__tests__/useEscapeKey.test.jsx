import { describe, it, expect, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useEscapeKey } from '@/hooks/useEscapeKey'

function pressKey(key) {
  document.dispatchEvent(new KeyboardEvent('keydown', { key }))
}

describe('useEscapeKey', () => {
  it('calls the handler when Escape is pressed', () => {
    const handler = vi.fn()
    renderHook(() => useEscapeKey(handler))
    pressKey('Escape')
    expect(handler).toHaveBeenCalledTimes(1)
  })

  it('ignores other keys', () => {
    const handler = vi.fn()
    renderHook(() => useEscapeKey(handler))
    pressKey('Enter')
    expect(handler).not.toHaveBeenCalled()
  })

  it('does nothing when disabled', () => {
    const handler = vi.fn()
    renderHook(() => useEscapeKey(handler, false))
    pressKey('Escape')
    expect(handler).not.toHaveBeenCalled()
  })

  it('removes the listener on unmount', () => {
    const handler = vi.fn()
    const { unmount } = renderHook(() => useEscapeKey(handler))
    unmount()
    pressKey('Escape')
    expect(handler).not.toHaveBeenCalled()
  })
})
