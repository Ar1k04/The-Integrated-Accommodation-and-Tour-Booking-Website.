import { create } from 'zustand'
import { authApi } from '@/api/authApi'
import { useUiStore } from '@/store/uiStore'
import { queryClient } from '@/lib/queryClient'

function hydrateUiPrefs(user) {
  if (!user) return
  const { setCurrency, setLocale } = useUiStore.getState()
  if (user.preferred_currency) setCurrency(user.preferred_currency)
  if (user.preferred_locale) {
    setLocale(user.preferred_locale)
    import('@/i18n').then(({ default: i18n }) => i18n.changeLanguage(user.preferred_locale)).catch(() => {})
  }
}

export const useAuthStore = create((set, get) => ({
  user: null,
  accessToken: null,
  isAuthenticated: false,
  isLoading: true,

  setAccessToken: (token) => set({ accessToken: token }),

  login: async (email, password) => {
    const res = await authApi.login({ email, password })
    const { access_token } = res.data
    set({ accessToken: access_token, isAuthenticated: true })
    const me = await authApi.getMe(access_token)
    set({ user: me.data, isLoading: false })
    hydrateUiPrefs(me.data)
    return me.data
  },

  register: async (data) => {
    const res = await authApi.register(data)
    const { access_token } = res.data
    set({ accessToken: access_token, isAuthenticated: true })
    const me = await authApi.getMe(access_token)
    set({ user: me.data, isLoading: false })
    hydrateUiPrefs(me.data)
    return me.data
  },

  loginWithGoogle: async (accessToken, role = 'user') => {
    const res = await authApi.google({ access_token: accessToken, role })
    const { access_token } = res.data
    set({ accessToken: access_token, isAuthenticated: true })
    const me = await authApi.getMe(access_token)
    set({ user: me.data, isLoading: false })
    hydrateUiPrefs(me.data)
    return me.data
  },

  logout: async () => {
    try {
      await authApi.logout()
    } catch {
      // ignore
    }
    set({ user: null, accessToken: null, isAuthenticated: false })
    // Drop all cached queries so the next account never sees the previous
    // user's data (e.g. admin stats leaking into a partner session).
    queryClient.clear()
  },

  refreshToken: async () => {
    try {
      const res = await authApi.refreshToken()
      const { access_token } = res.data
      set({ accessToken: access_token, isAuthenticated: true })
      const me = await authApi.getMe(access_token)
      set({ user: me.data, isLoading: false })
      hydrateUiPrefs(me.data)
      return access_token
    } catch {
      set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
      return null
    }
  },

  refreshUser: async () => {
    const me = await authApi.getMe(get().accessToken)
    set({ user: me.data })
    return me.data
  },

  updateProfile: async (data) => {
    const res = await authApi.updateMe(data)
    set({ user: res.data })
    return res.data
  },

  uploadAvatar: async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await authApi.uploadAvatar(formData)
    set({ user: res.data })
    return res.data
  },

  initialize: async () => {
    set({ isLoading: true })
    await get().refreshToken()
  },
}))
