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

  // Any platform staff (partner = hotel/tour owner, admin = platform admin)
  const isStaff = user?.role === 'partner' || user?.role === 'admin'
  // Full platform admin only
  const isAdmin = user?.role === 'admin'
  // Hotel/tour owner only
  const isPartner = user?.role === 'partner'

  return {
    user,
    isAuthenticated,
    isLoading,
    isStaff,
    isAdmin,
    isPartner,
    // Legacy aliases kept so existing consumers don't break while we migrate
    isSuperAdmin: isAdmin,
    login,
    logout,
    register,
    refreshToken,
    updateProfile,
  }
}
