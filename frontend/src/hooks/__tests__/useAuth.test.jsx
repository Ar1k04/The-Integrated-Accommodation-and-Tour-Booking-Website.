import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useAuth } from '@/hooks/useAuth'
import { useAuthStore } from '@/store/authStore'

beforeEach(() => useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: false }))

describe('useAuth role flags', () => {
  it('guest: all role flags are false', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current.isStaff).toBe(false)
    expect(result.current.isAdmin).toBe(false)
    expect(result.current.isPartner).toBe(false)
  })

  it('partner: isStaff + isPartner, not admin', () => {
    useAuthStore.setState({ user: { role: 'partner' }, isAuthenticated: true })
    const { result } = renderHook(() => useAuth())
    expect(result.current.isStaff).toBe(true)
    expect(result.current.isPartner).toBe(true)
    expect(result.current.isAdmin).toBe(false)
  })

  it('admin: isStaff + isAdmin + isSuperAdmin alias', () => {
    useAuthStore.setState({ user: { role: 'admin' }, isAuthenticated: true })
    const { result } = renderHook(() => useAuth())
    expect(result.current.isStaff).toBe(true)
    expect(result.current.isAdmin).toBe(true)
    expect(result.current.isSuperAdmin).toBe(true)
    expect(result.current.isPartner).toBe(false)
  })

  it('exposes the auth action functions', () => {
    const { result } = renderHook(() => useAuth())
    expect(typeof result.current.login).toBe('function')
    expect(typeof result.current.logout).toBe('function')
    expect(typeof result.current.updateProfile).toBe('function')
  })
})
