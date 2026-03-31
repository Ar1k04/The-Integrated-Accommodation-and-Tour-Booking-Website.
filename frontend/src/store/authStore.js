import { create } from 'zustand'
import { authApi } from '@/api/authApi'

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
    return me.data
  },

  register: async (data) => {
    const res = await authApi.register(data)
    const { access_token } = res.data
    set({ accessToken: access_token, isAuthenticated: true })
    const me = await authApi.getMe(access_token)
    set({ user: me.data, isLoading: false })
    return me.data
  },

  logout: async () => {
    try {
      await authApi.logout()
    } catch {
      // ignore
    }
    set({ user: null, accessToken: null, isAuthenticated: false })
  },

  refreshToken: async () => {
    try {
      const res = await authApi.refreshToken()
      const { access_token } = res.data
      set({ accessToken: access_token, isAuthenticated: true })
      const me = await authApi.getMe(access_token)
      set({ user: me.data, isLoading: false })
      return access_token
    } catch {
      set({ user: null, accessToken: null, isAuthenticated: false, isLoading: false })
      return null
    }
  },

  updateProfile: async (data) => {
    const res = await authApi.updateMe(data)
    set({ user: res.data })
    return res.data
  },

  initialize: async () => {
    set({ isLoading: true })
    await get().refreshToken()
  },
}))
