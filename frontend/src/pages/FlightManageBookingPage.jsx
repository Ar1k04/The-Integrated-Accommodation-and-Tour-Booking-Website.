import { useMemo, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  Download, RefreshCw, X, Ticket, PlaneTakeoff, AlertCircle, ArrowLeft,
} from 'lucide-react'

import { bookingsApi } from '@/api/bookingsApi'
import { flightsApi } from '@/api/flightsApi'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { formatDate } from '@/utils/formatters'
import Breadcrumb from '@/components/common/Breadcrumb'
import BookingStatusBadge from '@/components/common/BookingStatusBadge'
import Skeleton from '@/components/common/Skeleton'
import FlightItineraryBlock from '@/components/flight/FlightItineraryBlock'

export default function FlightManageBookingPage() {
  const { bookingId } = useParams()
  const navigate = useNavigate()
  const { t } = useTranslation(['flights', 'common'])
  const fmt = useFormatCurrency()
  const queryClient = useQueryClient()
  const [confirmingCancel, setConfirmingCancel] = useState(false)

  const { data: booking, isLoading } = useQuery({
    queryKey: ['booking', bookingId],
    queryFn: () => bookingsApi.get(bookingId),
    select: (res) => res.data,
  })

  const flightItem = booking?.items?.find((i) => i.item_type === 'flight')
  const flight = flightItem?.flight_booking
  const details = flight?.passenger_details || {}
  const passengers = details.passengers || []
  const snapshot = details.offer_snapshot || {}
  const documents = details.documents || []

  const syncMutation = useMutation({
    mutationFn: () => flightsApi.syncOrder(flight.duffel_order_id),
    onSuccess: () => {
      toast.success(t('flights:manage.syncSuccess'))
      queryClient.invalidateQueries({ queryKey: ['booking', bookingId] })
    },
    onError: () => toast.error(t('flights:manage.syncFailed')),
  })

  const cancelMutation = useMutation({
    mutationFn: () => bookingsApi.cancel(bookingId),
    onSuccess: () => {
      toast.success('Booking cancelled')
      setConfirmingCancel(false)
      queryClient.invalidateQueries({ queryKey: ['booking', bookingId] })
    },
    onError: (err) => toast.error(err.response?.data?.detail || 'Cancel failed'),
  })

  const handleDownloadETicket = async () => {
    if (!flight) return
    const { default: jsPDF } = await import('jspdf')
    const doc = new jsPDF()
    doc.setFontSize(22)
    doc.text('TravelBooking — E-Ticket', 20, 22)
    doc.setFontSize(12)
    doc.setFont(undefined, 'bold')
    doc.text(flight.airline_name || '', 20, 40)
    doc.setFont(undefined, 'normal')

    doc.setFontSize(14)
    doc.text(`PNR: ${flight.duffel_booking_ref || '—'}`, 20, 52)

    doc.setFontSize(11)
    let y = 70
    doc.text('Itinerary:', 20, y); y += 8
    const slices = snapshot.slices || []
    if (slices.length === 0) {
      // Fallback to single-segment from FlightBooking columns
      doc.text(`${flight.departure_airport} → ${flight.arrival_airport}`, 24, y); y += 6
      doc.text(`Depart: ${formatDate(flight.departure_at)}`, 24, y); y += 6
      doc.text(`Arrive: ${formatDate(flight.arrival_at)}`, 24, y); y += 8
    } else {
      slices.forEach((sl, si) => {
        doc.text(`${si === 0 ? 'Outbound' : 'Return'}: ${sl.origin} → ${sl.destination}`, 24, y); y += 6
        ;(sl.segments || []).forEach((seg) => {
          doc.text(`  ${seg.flight_number || ''}  ${seg.origin_iata} ${seg.departure_at?.slice(0, 16)} → ${seg.destination_iata} ${seg.arrival_at?.slice(0, 16)}`, 24, y)
          y += 6
        })
        y += 2
      })
    }

    y += 4
    doc.text('Passengers:', 20, y); y += 8
    if (passengers.length === 0) {
      doc.text(`${flight.passenger_name}`, 24, y); y += 6
    } else {
      passengers.forEach((p, i) => {
        doc.text(`  ${i + 1}. ${(p.title || '').toUpperCase()}. ${p.first_name || ''} ${p.last_name || ''}`, 24, y)
        y += 6
      })
    }

    y += 4
    doc.setFont(undefined, 'bold')
    doc.text(`Total: ${flight.currency} ${Number(flight.total_amount || 0).toFixed(2)}`, 20, y)
    doc.setFont(undefined, 'normal')

    doc.setFontSize(9)
    doc.text('Please present this document along with valid ID at check-in.', 20, 280)
    doc.text('Online check-in opens 24 hours before departure.', 20, 286)

    doc.save(`eticket-${flight.duffel_booking_ref || flight.id.slice(0, 8)}.pdf`)
  }

  const refundInfo = useMemo(() => {
    if (booking?.status !== 'cancelled') return null
    const ref = booking?.refund_info
    if (!ref) return null
    return ref
  }, [booking])

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-4">
        <Skeleton className="h-32 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  if (!booking || !flight) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <AlertCircle className="w-12 h-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500 mb-6">{t('flights:manage.noBooking')}</p>
        <button
          onClick={() => navigate('/profile?tab=bookings')}
          className="text-primary hover:underline"
        >
          ← Back to bookings
        </button>
      </div>
    )
  }

  const canCancel = booking.status !== 'cancelled' && booking.status !== 'completed'

  return (
    <>
      <Helmet><title>{t('flights:manage.title')}</title></Helmet>
      <div className="max-w-4xl mx-auto px-4 py-6">
        <Breadcrumb items={[
          { label: 'Home', to: '/' },
          { label: 'My Bookings', to: '/profile?tab=bookings' },
          { label: t('flights:manage.heading') },
        ]} />

        <div className="flex items-center gap-3 mt-4 mb-6">
          <button
            onClick={() => navigate(-1)}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="font-heading text-2xl font-bold">{t('flights:manage.heading')}</h1>
        </div>

        {/* Hero card */}
        <div className="bg-white border rounded-2xl p-6 mb-6 shadow-sm">
          <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
            <div className="flex items-center gap-3">
              <PlaneTakeoff className="w-8 h-8 text-primary" />
              <div>
                <h2 className="font-heading font-bold text-xl">{flight.airline_name}</h2>
                <p className="text-sm text-gray-500">
                  {flight.flight_number} · {flight.departure_airport} → {flight.arrival_airport}
                </p>
              </div>
            </div>
            <BookingStatusBadge status={booking.status} />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
                {t('flights:manage.pnr')}
              </p>
              <code className="font-mono text-lg font-bold text-primary tracking-widest">
                {flight.duffel_booking_ref || '—'}
              </code>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
                {t('flights:manage.totalPaid')}
              </p>
              <p className="font-bold text-lg">{fmt(flight.total_amount, flight.currency)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">
                {t('flights:manage.passengers')}
              </p>
              <p className="font-bold text-lg">{passengers.length || 1}</p>
            </div>
          </div>

          {refundInfo && (
            <div className="mt-4 p-3 bg-amber-50 border border-amber-100 rounded-lg text-sm text-amber-800">
              <strong>{t('flights:manage.refundInfo')}:</strong>{' '}
              {refundInfo.refund_amount != null
                ? `Refund ${fmt(refundInfo.refund_amount, refundInfo.currency)}`
                : 'Refund details pending'}
              {refundInfo.cancellation_fee != null && (
                <span className="ml-2">· Fee {fmt(refundInfo.cancellation_fee, refundInfo.currency)}</span>
              )}
            </div>
          )}
        </div>

        {/* Itinerary */}
        {snapshot.slices?.length > 0 && (
          <div className="bg-white border rounded-2xl p-6 mb-6">
            <h3 className="font-heading font-bold text-lg mb-4">Itinerary</h3>
            <FlightItineraryBlock slices={snapshot.slices} cabinClass={flight.cabin_class} compact />
          </div>
        )}

        {/* Passengers */}
        <div className="bg-white border rounded-2xl p-6 mb-6">
          <h3 className="font-heading font-bold text-lg mb-4">
            {t('flights:manage.passengers')} ({passengers.length || 1})
          </h3>
          {passengers.length === 0 ? (
            <p className="text-sm text-gray-500">{flight.passenger_name}</p>
          ) : (
            <ul className="space-y-2">
              {passengers.map((p, i) => (
                <li key={i} className="flex items-center gap-3 text-sm">
                  <Ticket className="w-4 h-4 text-gray-400" />
                  <span className="font-medium">
                    {(p.title || '').toUpperCase()}. {p.first_name} {p.last_name}
                  </span>
                  {p.email && <span className="text-gray-400 text-xs">· {p.email}</span>}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Documents */}
        {documents.length > 0 && (
          <div className="bg-white border rounded-2xl p-6 mb-6">
            <h3 className="font-heading font-bold text-lg mb-4">{t('flights:manage.documents')}</h3>
            <ul className="space-y-2 text-sm">
              {documents.map((d, i) => (
                <li key={i} className="flex items-center gap-2">
                  <Ticket className="w-4 h-4 text-primary" />
                  <span className="font-medium">{d.type}</span>
                  {d.unique_identifier && (
                    <span className="font-mono text-xs bg-gray-100 px-1.5 rounded">{d.unique_identifier}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-3">
          {flight.duffel_order_id && (
            <button
              onClick={() => syncMutation.mutate()}
              disabled={syncMutation.isPending}
              className="flex items-center gap-2 border border-primary text-primary font-semibold px-4 py-2.5 rounded-lg hover:bg-primary/5 transition-colors disabled:opacity-60"
            >
              <RefreshCw className={`w-4 h-4 ${syncMutation.isPending ? 'animate-spin' : ''}`} />
              {syncMutation.isPending
                ? t('flights:manage.syncing')
                : t('flights:manage.syncFromAirline')}
            </button>
          )}
          <button
            onClick={handleDownloadETicket}
            className="flex items-center gap-2 bg-primary text-white font-semibold px-4 py-2.5 rounded-lg hover:bg-primary/90 transition-colors"
          >
            <Download className="w-4 h-4" />
            {t('flights:manage.downloadETicket')}
          </button>
          {canCancel && (
            <button
              onClick={() => setConfirmingCancel(true)}
              className="flex items-center gap-2 border border-error text-error font-semibold px-4 py-2.5 rounded-lg hover:bg-error/5 transition-colors"
            >
              <X className="w-4 h-4" />
              {t('flights:manage.cancelBooking')}
            </button>
          )}
        </div>

        <p className="text-xs text-gray-400 mt-6 text-center">
          <Link to="/profile?tab=bookings" className="hover:underline">← Back to bookings</Link>
        </p>
      </div>

      {/* Cancel confirm modal */}
      {confirmingCancel && (
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onClick={() => setConfirmingCancel(false)}>
          <div className="bg-white rounded-2xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start gap-3 mb-4">
              <AlertCircle className="w-6 h-6 text-error shrink-0 mt-0.5" />
              <div>
                <h3 className="font-heading font-bold text-lg">{t('flights:manage.cancelBooking')}</h3>
                <p className="text-sm text-gray-600 mt-1">{t('flights:manage.cancelConfirm')}</p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setConfirmingCancel(false)}
                className="px-4 py-2 rounded-lg text-sm font-medium text-gray-600 hover:bg-gray-100"
              >
                Back
              </button>
              <button
                onClick={() => cancelMutation.mutate()}
                disabled={cancelMutation.isPending}
                className="bg-error hover:bg-error/90 text-white font-semibold px-5 py-2 rounded-lg text-sm disabled:opacity-60"
              >
                {cancelMutation.isPending ? t('flights:manage.cancelling') : t('flights:manage.cancelBooking')}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
