import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export default function ProtectedRoute({
  children,
  requireStaff = false,    // any staff (partner OR admin)
  requireAdmin = false,    // admin only (formerly requireSuperAdmin)
  userOnly = false,
}) {
  const { isAuthenticated, isLoading, isStaff, isAdmin } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  if (requireAdmin && !isAdmin) {
    return <Navigate to="/admin" replace />
  }

  if (requireStaff && !isStaff) {
    return <Navigate to="/" replace />
  }

  if (userOnly && isStaff) {
    return <Navigate to="/admin" replace />
  }

  return children
}
