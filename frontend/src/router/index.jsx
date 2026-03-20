import { createBrowserRouter } from 'react-router-dom'
import AppLayout from '@/components/common/AppLayout'
import ProtectedRoute from '@/components/common/ProtectedRoute'
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
      { path: '/', element: <HomePage /> },
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/hotels/search', element: <SearchResultsPage /> },
      { path: '/hotels/:id', element: <HotelDetailPage /> },
      {
        path: '/bookings/new',
        element: <ProtectedRoute><BookingPage /></ProtectedRoute>,
      },
      {
        path: '/bookings/:id/confirmation',
        element: <ProtectedRoute><BookingConfirmationPage /></ProtectedRoute>,
      },
      { path: '/tours', element: <ToursPage /> },
      { path: '/tours/:id', element: <TourDetailPage /> },
      {
        path: '/profile',
        element: <ProtectedRoute><ProfilePage /></ProtectedRoute>,
      },
      {
        path: '/my-bookings',
        element: <ProtectedRoute><MyBookingsPage /></ProtectedRoute>,
      },
      {
        path: '/admin',
        element: <ProtectedRoute><AdminDashboard /></ProtectedRoute>,
      },
      {
        path: '/admin/hotels',
        element: <ProtectedRoute><ManageHotels /></ProtectedRoute>,
      },
      {
        path: '/admin/rooms',
        element: <ProtectedRoute><ManageRooms /></ProtectedRoute>,
      },
      {
        path: '/admin/tours',
        element: <ProtectedRoute><ManageTours /></ProtectedRoute>,
      },
      {
        path: '/admin/bookings',
        element: <ProtectedRoute><ManageBookings /></ProtectedRoute>,
      },
      {
        path: '/admin/users',
        element: <ProtectedRoute><ManageUsers /></ProtectedRoute>,
      },
    ],
  },
])
