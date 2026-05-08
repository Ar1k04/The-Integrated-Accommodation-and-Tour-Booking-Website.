import { useEffect } from 'react'

/**
 * Calls `handler` when the Escape key is pressed.
 * Attach to any modal/dialog to support keyboard dismissal.
 */
export function useEscapeKey(handler, enabled = true) {
  useEffect(() => {
    if (!enabled) return
    const onKeyDown = (e) => {
      if (e.key === 'Escape') handler()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [handler, enabled])
}
