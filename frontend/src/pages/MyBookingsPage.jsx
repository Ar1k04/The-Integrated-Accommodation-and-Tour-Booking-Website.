import { Navigate } from 'react-router-dom'

export default function MyBookingsPage() {
  return <Navigate to="/profile?tab=bookings" replace />
}
