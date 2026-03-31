import { useAuthStore } from '@/store/authStore'

export function useAuth() {
  const user = useAuthStore((s) => s.user)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const isLoading = useAuthStore((s) => s.isLoading)
  const login = useAuthStore((s) => s.login)
  const logout = useAuthStore((s) => s.logout)
  const register = useAuthStore((s) => s.register)
  const refreshToken = useAuthStore((s) => s.refreshToken)
  const updateProfile = useAuthStore((s) => s.updateProfile)

  const isAdmin = user?.role === 'admin' || user?.role === 'superadmin'
  const isSuperAdmin = user?.role === 'superadmin'

  return {
    user,
    isAuthenticated,
    isLoading,
    isAdmin,
    isSuperAdmin,
    login,
    logout,
    register,
    refreshToken,
    updateProfile,
  }
}
