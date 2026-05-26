import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { bookingsApi } from '@/api/bookingsApi'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { formatDate } from '@/utils/formatters'
import { downloadBookingPdf } from '@/utils/bookingPdf'
import Skeleton from '@/components/common/Skeleton'
import { CheckCircle, Download, Calendar, Users, Copy, PlaneTakeoff, Ticket, Settings } from 'lucide-react'
import { toast } from 'sonner'
import { motion } from 'framer-motion'
import FlightItineraryBlock from '@/components/flight/FlightItineraryBlock'

export default function BookingConfirmationPage() {
  const { id } = useParams()
  const { t } = useTranslation('booking')
  const fmt = useFormatCurrency()

  const { data: booking, isLoading } = useQuery({
    queryKey: ['booking', id],
    queryFn: () => bookingsApi.get(id),
    select: (res) => res.data,
  })

  const copyRef = () => {
    navigator.clipboard.writeText(id)
    toast.success('Booking reference copied!')
  }

  const handleDownloadPDF = () => downloadBookingPdf(booking, fmt)

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-20 space-y-4">
        <Skeleton className="h-16 w-16 rounded-full mx-auto" />
        <Skeleton className="h-8 w-1/2 mx-auto" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  return (
    <>
      <Helmet><title>{t('confirmation.title')} — TravelBooking</title></Helmet>
      <div className="max-w-2xl mx-auto px-4 py-12">
        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', duration: 0.6 }}
          className="text-center mb-8">
          <CheckCircle className="w-20 h-20 text-success mx-auto" />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <h1 className="font-heading text-3xl font-bold text-center text-gray-900 mb-2">{t('confirmation.title')}</h1>
          <p className="text-gray-500 text-center mb-8">{t('confirmation.subtitle')}</p>

          <div className="bg-white rounded-2xl border shadow-sm p-6 space-y-6">
            <div className="text-center">
              <p className="text-sm text-gray-500 mb-1">{t('confirmation.bookingRef')}</p>
              <div className="flex items-center justify-center gap-2">
                <code className="text-lg font-mono font-bold text-primary">{id?.slice(0, 8).toUpperCase()}</code>
                <button onClick={copyRef} className="text-gray-400 hover:text-primary"><Copy className="w-4 h-4" /></button>
              </div>
            </div>

            <hr />

            {(() => {
              const roomItem = booking?.items?.find(i => i.item_type === 'room')
              const tourItem = booking?.items?.find(i => i.item_type === 'tour')
              const flightItem = booking?.items?.find(i => i.item_type === 'flight')
              return (
                <div className="grid grid-cols-2 gap-4 text-sm">
                  {roomItem && (
                    <>
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-gray-500">{t('summary.checkIn')}</p>
                          <p className="font-medium">{formatDate(roomItem.check_in)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-gray-500">{t('summary.checkOut')}</p>
                          <p className="font-medium">{formatDate(roomItem.check_out)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Users className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-gray-500">Rooms</p>
                          <p className="font-medium">{roomItem.quantity}</p>
                        </div>
                      </div>
                    </>
                  )}
                  {tourItem && (
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-gray-400" />
                      <div>
                        <p className="text-gray-500">Tour Date</p>
                        <p className="font-medium">{formatDate(tourItem.check_in)}</p>
                      </div>
                    </div>
                  )}
                  {flightItem && (
                    <div className="flex items-center gap-2">
                      <Users className="w-4 h-4 text-gray-400" />
                      <div>
                        <p className="text-gray-500">Passengers</p>
                        <p className="font-medium">{flightItem.quantity}</p>
                      </div>
                    </div>
                  )}
                  <div>
                    <p className="text-gray-500">Total Paid</p>
                    <p className="font-bold text-lg text-primary">{fmt(booking?.total_price)}</p>
                  </div>
                </div>
              )
            })()}

            {/* Flight-specific block */}
            {(() => {
              const flightItem = booking?.items?.find(i => i.item_type === 'flight')
              const flight = flightItem?.flight_booking
              if (!flight) return null
              const details = flight.passenger_details || {}
              const snapshot = details.offer_snapshot || {}
              const passengers = details.passengers || []
              return (
                <div className="border-t pt-4 space-y-4">
                  <div className="flex items-center gap-2">
                    <PlaneTakeoff className="w-5 h-5 text-primary" />
                    <h3 className="font-heading font-bold text-sm">
                      {flight.airline_name} — {flight.flight_number}
                    </h3>
                  </div>

                  {flight.duffel_booking_ref && (
                    <div className="bg-primary/5 border border-primary/20 rounded-lg p-4 text-center">
                      <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">
                        Booking Reference (PNR)
                      </p>
                      <code className="text-2xl font-mono font-bold text-primary tracking-widest">
                        {flight.duffel_booking_ref}
                      </code>
                    </div>
                  )}

                  {snapshot.slices?.length > 0 && (
                    <FlightItineraryBlock
                      slices={snapshot.slices}
                      cabinClass={flight.cabin_class}
                      compact
                    />
                  )}

                  {passengers.length > 0 && (
                    <div>
                      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
                        Passengers ({passengers.length})
                      </p>
                      <ul className="space-y-1 text-sm">
                        {passengers.map((p, i) => (
                          <li key={i} className="flex items-center gap-2 text-gray-700">
                            <Ticket className="w-3.5 h-3.5 text-gray-400" />
                            {p.title?.toUpperCase()}. {p.first_name} {p.last_name}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-xs text-blue-700">
                    💡 Online check-in opens 24 hours before departure.
                  </div>
                </div>
              )
            })()}

            {(booking?.subtotal > 0 || booking?.taxes > 0 || booking?.discount_amount > 0 || booking?.tier_discount > 0) && (
              <div className="rounded-lg bg-gray-50 px-4 py-3 text-sm space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-gray-600">Subtotal</span>
                  <span className="font-medium">{fmt(booking?.subtotal)}</span>
                </div>
                {booking?.taxes > 0 && (
                  <div className="flex justify-between">
                    <span className="text-gray-600">Taxes &amp; fees</span>
                    <span className="font-medium">{fmt(booking?.taxes)}</span>
                  </div>
                )}
                {booking?.tier_discount > 0 && (
                  <div className="flex justify-between text-green-700">
                    <span>Member discount</span>
                    <span>−{fmt(booking?.tier_discount)}</span>
                  </div>
                )}
                {booking?.discount_amount > 0 && (
                  <div className="flex justify-between text-green-700">
                    <span>Voucher discount</span>
                    <span>−{fmt(booking?.discount_amount)}</span>
                  </div>
                )}
                <div className="flex justify-between pt-1.5 border-t border-gray-200 font-semibold">
                  <span>Total</span>
                  <span className="text-primary">{fmt(booking?.total_price)}</span>
                </div>
              </div>
            )}

            <hr />

            <div className="flex flex-col sm:flex-row gap-3">
              <button onClick={handleDownloadPDF}
                className="flex-1 flex items-center justify-center gap-2 border border-primary text-primary font-semibold py-2.5 rounded-lg hover:bg-primary/5">
                <Download className="w-4 h-4" /> {t('confirmation.downloadPdf')}
              </button>
              {/* Flight bookings get a dedicated manage page with sync /
                  cancel / e-ticket / change-flight actions. Surface it
                  prominently so users don't dig through the bookings list. */}
              {booking?.items?.some(i => i.item_type === 'flight') && (
                <Link to={`/flights/bookings/${id}`}
                  className="flex-1 flex items-center justify-center gap-2 bg-primary text-white font-semibold py-2.5 rounded-lg hover:bg-primary-dark">
                  <Settings className="w-4 h-4" /> Manage flight booking
                </Link>
              )}
              <Link to="/profile?tab=bookings"
                className={`flex-1 flex items-center justify-center gap-2 ${
                  booking?.items?.some(i => i.item_type === 'flight')
                    ? 'border text-gray-700 hover:bg-gray-50'
                    : 'bg-primary text-white hover:bg-primary-dark'
                } font-semibold py-2.5 rounded-lg`}>
                {t('confirmation.viewBookings')}
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </>
  )
}
