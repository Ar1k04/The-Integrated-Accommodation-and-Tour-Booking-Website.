import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useParams, Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { AlertTriangle, ArrowLeft, RefreshCw, Copy } from 'lucide-react'
import { toast } from 'sonner'
import { bookingsApi } from '@/api/bookingsApi'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'

/**
 * Shown when payment succeeded but the supplier booking (Duffel order) failed.
 * The backend has already attempted an automatic refund; this page tells the
 * user what happened and where their money is.
 *
 * Two entry routes:
 *   1. Navigated to from BookingPage.handlePaymentSuccess with `location.state.failure`
 *   2. Reloaded directly (state lost) — falls back to the booking row's status
 *      and last_error stored on the FlightBooking.
 */
export default function BookingFailurePage() {
  const { id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const fmt = useFormatCurrency()

  const initial = location.state?.failure || null
  const [fallback, setFallback] = useState(null)

  useEffect(() => {
    if (initial) return
    let mounted = true
    bookingsApi.get(id)
      .then((res) => {
        if (!mounted) return
        const booking = res?.data?.data || res?.data
        // Synthesize a failure object from persisted state.
        const flightItem = (booking?.items || []).find((it) => it.item_type === 'flight')
        const lastError = flightItem?.flight_booking?.passenger_details?.last_error
        setFallback({
          booking_id: booking?.id || id,
          status: booking?.status === 'cancelled' ? 'failed' : 'partial',
          supplier_error: lastError ? {
            supplier: 'duffel',
            error_code: lastError.error_code,
            message: 'Your flight booking could not be completed.',
          } : null,
          refund: null,
        })
      })
      .catch(() => {
        if (mounted) setFallback({ booking_id: id, status: 'failed' })
      })
    return () => { mounted = false }
  }, [id, initial])

  const data = initial || fallback
  const status = data?.status || 'failed'
  const refund = data?.refund
  const supplierError = data?.supplier_error
  const userMsg = supplierError?.message
    || (data?.failed_items?.[0]?.user_message)
    || 'Your flight booking could not be completed. Your payment has been refunded.'

  const copyRef = () => {
    navigator.clipboard.writeText(id)
    toast.success('Booking reference copied')
  }

  return (
    <>
      <Helmet><title>Booking issue — TravelBooking</title></Helmet>
      <div className="max-w-2xl mx-auto px-4 py-10">
        <div className="bg-white rounded-2xl border border-red-100 shadow-sm overflow-hidden">
          <div className="bg-red-500 text-white px-6 py-5 flex items-center gap-3">
            <AlertTriangle className="w-6 h-6" />
            <div>
              <h1 className="font-heading text-xl font-bold">
                {status === 'partial' ? 'Booking partially completed' : "We couldn't book your flight"}
              </h1>
              <p className="text-sm opacity-90">
                {status === 'partial'
                  ? 'Some items in your booking went through; one or more did not.'
                  : 'Your payment has been refunded.'}
              </p>
            </div>
          </div>

          <div className="p-6 space-y-5">
            <p className="text-gray-700">{userMsg}</p>

            {refund && (
              <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-4 text-sm">
                <p className="font-semibold text-emerald-800">
                  {refund.issued ? 'Refund issued' : 'Refund pending'}
                </p>
                {refund.issued && refund.amount_usd != null && (
                  <p className="text-emerald-700 mt-1">
                    {fmt(refund.amount_usd)} returned to your original payment method.
                    Allow 5-7 business days for it to appear on your statement.
                  </p>
                )}
                {!refund.issued && (
                  <p className="text-emerald-700 mt-1">
                    A refund is being processed manually by our support team. You'll
                    receive a confirmation within 24 hours.
                  </p>
                )}
                {refund.stripe_refund_id && (
                  <p className="text-xs text-emerald-600 mt-1 font-mono break-all">
                    Refund ID: {refund.stripe_refund_id}
                  </p>
                )}
              </div>
            )}

            <div className="bg-gray-50 rounded-lg p-4 text-sm">
              <p className="text-gray-500 mb-1">Booking reference</p>
              <div className="flex items-center gap-2">
                <code className="font-mono text-gray-900">{id}</code>
                <button onClick={copyRef} className="text-gray-400 hover:text-gray-700">
                  <Copy className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <Link
                to="/flights"
                className="bg-accent hover:bg-accent/90 text-white font-semibold px-5 py-3 rounded-lg inline-flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Search flights again
              </Link>
              <button
                onClick={() => navigate('/profile')}
                className="border border-gray-300 hover:bg-gray-50 text-gray-700 font-semibold px-5 py-3 rounded-lg inline-flex items-center gap-2"
              >
                <ArrowLeft className="w-4 h-4" />
                Back to my bookings
              </button>
            </div>

            <p className="text-xs text-gray-500 pt-3 border-t">
              Need help? Reply to the email we just sent you and quote the booking
              reference above. Our support team typically responds within an hour.
            </p>
          </div>
        </div>
      </div>
    </>
  )
}
