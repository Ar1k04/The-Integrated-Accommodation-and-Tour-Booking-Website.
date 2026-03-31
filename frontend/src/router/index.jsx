import { createBrowserRouter } from 'react-router-dom'
import AppLayout from '@/components/common/AppLayout'
import AdminLayout from '@/components/common/AdminLayout'
import ProtectedRoute from '@/components/common/ProtectedRoute'
import RedirectIfAdmin from '@/components/common/RedirectIfAdmin'
import HomePage from '@/pages/HomePage'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import SearchResultsPage from '@/pages/SearchResultsPage'
import HotelDetailPage from '@/pages/HotelDetailPage'
import BookingPage from '@/pages/BookingPage'
import BookingConfirmationPage from '@/pages/BookingConfirmationPage'
import ToursPage from '@/pages/ToursPage'
import TourDetailPage from '@/pages/TourDetailPage'
import ProfilePage from '@/pages/ProfilePage'
import MyBookingsPage from '@/pages/MyBookingsPage'
import AdminDashboard from '@/pages/admin/AdminDashboard'
import ManageHotels from '@/pages/admin/ManageHotels'
import ManageRooms from '@/pages/admin/ManageRooms'
import ManageTours from '@/pages/admin/ManageTours'
import ManageBookings from '@/pages/admin/ManageBookings'
import ManageUsers from '@/pages/admin/ManageUsers'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <RedirectIfAdmin><HomePage /></RedirectIfAdmin> },
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RedirectIfAdmin><RegisterPage /></RedirectIfAdmin> },
      { path: '/hotels/search', element: <RedirectIfAdmin><SearchResultsPage /></RedirectIfAdmin> },
      { path: '/hotels/:id', element: <RedirectIfAdmin><HotelDetailPage /></RedirectIfAdmin> },
      {
        path: '/bookings/new',
        element: <ProtectedRoute userOnly><BookingPage /></ProtectedRoute>,
      },
      {
        path: '/bookings/:id/confirmation',
        element: <ProtectedRoute userOnly><BookingConfirmationPage /></ProtectedRoute>,
      },
      { path: '/tours', element: <RedirectIfAdmin><ToursPage /></RedirectIfAdmin> },
      { path: '/tours/:id', element: <RedirectIfAdmin><TourDetailPage /></RedirectIfAdmin> },
      {
        path: '/profile',
        element: <ProtectedRoute userOnly><ProfilePage /></ProtectedRoute>,
      },
      {
        path: '/my-bookings',
        element: <ProtectedRoute userOnly><MyBookingsPage /></ProtectedRoute>,
      },
    ],
  },
  {
    element: <AdminLayout />,
    children: [
      {
        path: '/admin',
        element: <ProtectedRoute requireAdmin><AdminDashboard /></ProtectedRoute>,
      },
      {
        path: '/admin/hotels',
        element: <ProtectedRoute requireAdmin><ManageHotels /></ProtectedRoute>,
      },
      {
        path: '/admin/rooms',
        element: <ProtectedRoute requireAdmin><ManageRooms /></ProtectedRoute>,
      },
      {
        path: '/admin/tours',
        element: <ProtectedRoute requireAdmin><ManageTours /></ProtectedRoute>,
      },
      {
        path: '/admin/bookings',
        element: <ProtectedRoute requireAdmin><ManageBookings /></ProtectedRoute>,
      },
      {
        path: '/admin/users',
        element: <ProtectedRoute requireSuperAdmin><ManageUsers /></ProtectedRoute>,
      },
    ],
  },
])
