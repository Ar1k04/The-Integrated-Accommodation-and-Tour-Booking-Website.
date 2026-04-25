import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { paymentsApi } from '@/api/paymentsApi'
import { CheckCircle, XCircle, Loader } from 'lucide-react'

export default function VNPayReturnPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [status, setStatus] = useState('verifying') // 'verifying' | 'success' | 'failed'
  const [bookingId, setBookingId] = useState(null)

  useEffect(() => {
    const params = Object.fromEntries(searchParams.entries())
    if (!params.vnp_TxnRef) {
      setStatus('failed')
      return
    }

    paymentsApi
      .verifyVnpayReturn(params)
      .then((res) => {
        const data = res.data?.data || res.data
        if (res.data?.success) {
          setBookingId(data.booking_id)
          setStatus('success')
        } else {
          setBookingId(data?.booking_id)
          setStatus('failed')
        }
      })
      .catch(() => {
        setStatus('failed')
      })
  }, [searchParams])

  useEffect(() => {
    if (status === 'success' && bookingId) {
      const timer = setTimeout(() => {
        navigate(`/bookings/${bookingId}/confirmation`)
      }, 2000)
      return () => clearTimeout(timer)
    }
  }, [status, bookingId, navigate])

  return (
    <>
      <Helmet>
        <title>Payment — TravelBooking</title>
      </Helmet>
      <div className="min-h-screen flex items-center justify-center bg-surface">
        <div className="bg-white rounded-2xl border p-10 max-w-md w-full text-center space-y-4">
          {status === 'verifying' && (
            <>
              <Loader className="w-12 h-12 text-primary animate-spin mx-auto" />
              <h2 className="font-heading text-xl font-bold">Verifying Payment...</h2>
              <p className="text-gray-500 text-sm">Please wait while we confirm your payment.</p>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircle className="w-16 h-16 text-success mx-auto" />
              <h2 className="font-heading text-2xl font-bold text-success">Payment Successful!</h2>
              <p className="text-gray-500 text-sm">
                Your booking has been confirmed. Redirecting to your booking details...
              </p>
              {bookingId && (
                <button
                  onClick={() => navigate(`/bookings/${bookingId}/confirmation`)}
                  className="bg-primary text-white px-6 py-2.5 rounded-lg text-sm font-semibold"
                >
                  View Booking
                </button>
              )}
            </>
          )}

          {status === 'failed' && (
            <>
              <XCircle className="w-16 h-16 text-error mx-auto" />
              <h2 className="font-heading text-2xl font-bold text-error">Payment Failed</h2>
              <p className="text-gray-500 text-sm">
                Your payment was not completed. Please try again or choose a different payment method.
              </p>
              <div className="flex gap-3 justify-center">
                <button
                  onClick={() => navigate(-2)}
                  className="bg-primary text-white px-6 py-2.5 rounded-lg text-sm font-semibold"
                >
                  Try Again
                </button>
                <button
                  onClick={() => navigate('/')}
                  className="border px-6 py-2.5 rounded-lg text-sm font-semibold"
                >
                  Go Home
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  )
}
