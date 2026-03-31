import { Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

export default function RedirectIfAdmin({ children }) {
  const { isAuthenticated, isAdmin, isLoading } = useAuth()

  if (!isLoading && isAuthenticated && isAdmin) {
    return <Navigate to="/admin" replace />
  }

  return children
}
