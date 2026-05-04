import { Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export default function RedirectIfAdmin({ children }) {
  const { isAuthenticated, isStaff, isLoading } = useAuth()

  if (!isLoading && isAuthenticated && isStaff) {
    return <Navigate to="/admin" replace />
  }

  return children
}
