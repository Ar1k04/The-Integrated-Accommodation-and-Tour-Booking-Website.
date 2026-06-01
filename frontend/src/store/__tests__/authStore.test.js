import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock API auth + uiStore (hydrateUiPrefs gọi useUiStore.getState()).
vi.mock('@/api/authApi', () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn().mockResolvedValue({}),
    refreshToken: vi.fn(),
    getMe: vi.fn(),
    updateMe: vi.fn(),
  },
}))
vi.mock('@/store/uiStore', () => ({
  useUiStore: { getState: () => ({ setCurrency: vi.fn(), setLocale: vi.fn() }) },
}))

import { useAuthStore } from '@/store/authStore'
import { authApi } from '@/api/authApi'

beforeEach(() => {
  vi.clearAllMocks()
  useAuthStore.setState({ user: null, accessToken: null, isAuthenticated: false, isLoading: true })
})

describe('authStore.login', () => {
  it('stores the token + user and flags authenticated', async () => {
    authApi.login.mockResolvedValue({ data: { access_token: 'tok123' } })
    authApi.getMe.mockResolvedValue({ data: { id: 'u1', email: 'a@b.com', role: 'user' } })

    const user = await useAuthStore.getState().login('a@b.com', 'pw')

    const s = useAuthStore.getState()
    expect(s.accessToken).toBe('tok123')
    expect(s.isAuthenticated).toBe(true)
    expect(s.user.email).toBe('a@b.com')
    expect(user.id).toBe('u1')
  })
})

describe('authStore.logout', () => {
  it('clears the session on success', async () => {
    useAuthStore.setState({ user: { id: 'u1' }, accessToken: 't', isAuthenticated: true })
    await useAuthStore.getState().logout()
    const s = useAuthStore.getState()
    expect(s.user).toBeNull()
    expect(s.accessToken).toBeNull()
    expect(s.isAuthenticated).toBe(false)
  })

  it('still clears the session even if the logout API throws', async () => {
    authApi.logout.mockRejectedValueOnce(new Error('network'))
    useAuthStore.setState({ user: { id: 'u1' }, accessToken: 't', isAuthenticated: true })
    await useAuthStore.getState().logout()
    expect(useAuthStore.getState().isAuthenticated).toBe(false)
  })
})

describe('authStore.refreshToken', () => {
  it('refreshes the token and loads the user on success', async () => {
    authApi.refreshToken.mockResolvedValue({ data: { access_token: 'new-token' } })
    authApi.getMe.mockResolvedValue({ data: { id: 'u1', role: 'user' } })

    const token = await useAuthStore.getState().refreshToken()

    expect(token).toBe('new-token')
    expect(useAuthStore.getState().isAuthenticated).toBe(true)
  })

  it('clears the session and returns null when refresh fails', async () => {
    authApi.refreshToken.mockRejectedValueOnce(new Error('401'))
    useAuthStore.setState({ user: { id: 'u1' }, accessToken: 't', isAuthenticated: true })

    const token = await useAuthStore.getState().refreshToken()

    expect(token).toBeNull()
    const s = useAuthStore.getState()
    expect(s.isAuthenticated).toBe(false)
    expect(s.isLoading).toBe(false)
  })
})

describe('authStore.updateProfile', () => {
  it('updates the stored user from the response', async () => {
    authApi.updateMe.mockResolvedValue({ data: { id: 'u1', full_name: 'New Name' } })
    const updated = await useAuthStore.getState().updateProfile({ full_name: 'New Name' })
    expect(updated.full_name).toBe('New Name')
    expect(useAuthStore.getState().user.full_name).toBe('New Name')
  })
})
