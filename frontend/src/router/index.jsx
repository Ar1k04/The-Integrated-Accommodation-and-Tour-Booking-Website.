import { createBrowserRouter } from 'react-router-dom'
import AppLayout from '@/components/common/AppLayout'
import AdminLayout from '@/components/common/AdminLayout'
import ProtectedRoute from '@/components/common/ProtectedRoute'
import RedirectIfAdmin from '@/components/common/RedirectIfAdmin'
import HomePage from '@/pages/HomePage'
import LoginPage from '@/pages/LoginPage'
import RegisterPage from '@/pages/RegisterPage'
import ForgotPasswordPage from '@/pages/ForgotPasswordPage'
import ResetPasswordPage from '@/pages/ResetPasswordPage'
import PartnerConfirmPage from '@/pages/PartnerConfirmPage'
import SearchResultsPage from '@/pages/SearchResultsPage'
import HotelDetailPage from '@/pages/HotelDetailPage'
import LiteapiHotelDetailPage from '@/pages/LiteapiHotelDetailPage'
import BookingPage from '@/pages/BookingPage'
import BookingConfirmationPage from '@/pages/BookingConfirmationPage'
import BookingFailurePage from '@/pages/BookingFailurePage'
import ToursPage from '@/pages/ToursPage'
import DealsPage from '@/pages/DealsPage'
import TourDetailPage from '@/pages/TourDetailPage'
import ProfilePage from '@/pages/ProfilePage'
import MyBookingsPage from '@/pages/MyBookingsPage'
import VNPayReturnPage from '@/pages/VNPayReturnPage'
import AdminDashboard from '@/pages/admin/AdminDashboard'
import ManageHotels from '@/pages/admin/ManageHotels'
import ManageRooms from '@/pages/admin/ManageRooms'
import ManageTours from '@/pages/admin/ManageTours'
import ManageBookings from '@/pages/admin/ManageBookings'
import ManageUsers from '@/pages/admin/ManageUsers'
import ManageVouchers from '@/pages/admin/ManageVouchers'
import ManageTiers from '@/pages/admin/ManageTiers'
import ManagePartners from '@/pages/admin/ManagePartners'
import FlightsSearchPage from '@/pages/FlightsSearchPage'
import FlightOfferDetailPage from '@/pages/FlightOfferDetailPage'
import FlightManageBookingPage from '@/pages/FlightManageBookingPage'
import FlightChangeRequestPage from '@/pages/FlightChangeRequestPage'
import FlightCheckoutPage from '@/pages/FlightCheckoutPage'
import NotFoundPage from '@/pages/NotFoundPage'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <RedirectIfAdmin><HomePage /></RedirectIfAdmin> },
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RedirectIfAdmin><RegisterPage /></RedirectIfAdmin> },
      { path: '/forgot-password', element: <ForgotPasswordPage /> },
      { path: '/reset-password', element: <ResetPasswordPage /> },
      { path: '/partner/confirm', element: <PartnerConfirmPage /> },
      { path: '/hotels/search', element: <RedirectIfAdmin><SearchResultsPage /></RedirectIfAdmin> },
      { path: '/hotels/liteapi/:liteapiId', element: <RedirectIfAdmin><LiteapiHotelDetailPage /></RedirectIfAdmin> },
      { path: '/hotels/:id', element: <RedirectIfAdmin><HotelDetailPage /></RedirectIfAdmin> },
      {
        path: '/bookings/new',
        element: <ProtectedRoute userOnly><BookingPage /></ProtectedRoute>,
      },
      {
        path: '/bookings/:id/confirmation',
        element: <ProtectedRoute userOnly><BookingConfirmationPage /></ProtectedRoute>,
      },
      {
        path: '/bookings/:id/failure',
        element: <ProtectedRoute userOnly><BookingFailurePage /></ProtectedRoute>,
      },
      { path: '/flights', element: <RedirectIfAdmin><FlightsSearchPage /></RedirectIfAdmin> },
      { path: '/flights/offers/:offerId', element: <RedirectIfAdmin><FlightOfferDetailPage /></RedirectIfAdmin> },
      {
        path: '/flights/checkout',
        element: <ProtectedRoute userOnly><FlightCheckoutPage /></ProtectedRoute>,
      },
      {
        path: '/flights/bookings/:bookingId',
        element: <ProtectedRoute userOnly><FlightManageBookingPage /></ProtectedRoute>,
      },
      {
        path: '/flights/bookings/:bookingId/change',
        element: <ProtectedRoute userOnly><FlightChangeRequestPage /></ProtectedRoute>,
      },
      { path: '/tours', element: <RedirectIfAdmin><ToursPage /></RedirectIfAdmin> },
      { path: '/deals', element: <RedirectIfAdmin><DealsPage /></RedirectIfAdmin> },
      { path: '/tours/viator/:code', element: <RedirectIfAdmin><TourDetailPage /></RedirectIfAdmin> },
      { path: '/tours/:id', element: <RedirectIfAdmin><TourDetailPage /></RedirectIfAdmin> },
      {
        path: '/profile',
        element: <ProtectedRoute userOnly><ProfilePage /></ProtectedRoute>,
      },
      {
        path: '/my-bookings',
        element: <ProtectedRoute userOnly><MyBookingsPage /></ProtectedRoute>,
      },
      { path: '/payments/vnpay/return', element: <VNPayReturnPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
  {
    element: <AdminLayout />,
    children: [
      {
        path: '/admin',
        element: <ProtectedRoute requireStaff><AdminDashboard /></ProtectedRoute>,
      },
      {
        path: '/admin/hotels',
        element: <ProtectedRoute requireStaff><ManageHotels /></ProtectedRoute>,
      },
      {
        path: '/admin/rooms',
        element: <ProtectedRoute requireStaff><ManageRooms /></ProtectedRoute>,
      },
      {
        path: '/admin/tours',
        element: <ProtectedRoute requireStaff><ManageTours /></ProtectedRoute>,
      },
      {
        path: '/admin/bookings',
        element: <ProtectedRoute requireStaff><ManageBookings /></ProtectedRoute>,
      },
      {
        path: '/admin/users',
        element: <ProtectedRoute requireAdmin><ManageUsers /></ProtectedRoute>,
      },
      {
        path: '/admin/partners',
        element: <ProtectedRoute requireAdmin><ManagePartners /></ProtectedRoute>,
      },
      {
        path: '/admin/loyalty-tiers',
        element: <ProtectedRoute requireAdmin><ManageTiers /></ProtectedRoute>,
      },
      {
        path: '/admin/vouchers',
        element: <ProtectedRoute requireStaff><ManageVouchers /></ProtectedRoute>,
      },
      { path: '/admin/*', element: <NotFoundPage /> },
    ],
  },
])
