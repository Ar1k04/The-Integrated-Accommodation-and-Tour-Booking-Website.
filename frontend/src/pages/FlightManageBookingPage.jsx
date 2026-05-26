import { useMemo, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  Download, RefreshCw, X, Ticket, PlaneTakeoff, AlertCircle, ArrowLeft,
  Edit3, History, ArrowRightLeft,
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

    // jsPDF's built-in Helvetica font only supports Latin-1 (ISO-8859-1). Any
    // unicode glyph — ✈, →, •, em-dash, or Vietnamese diacritics like Nguyễn —
    // renders as garbled boxes. We strip everything down to safe ASCII before
    // calling `doc.text()`. Combining marks come off via NFD + regex, the
    // common symbols get replaced inline, anything still outside ASCII is
    // dropped. Backend already normalises passenger names this way for IATA
    // compliance — this just keeps the PDF consistent.
    const toAscii = (s) => {
      if (s == null) return '-'
      return String(s)
        // NFD splits Vietnamese/European letters into base+combining mark,
        // then we drop the combining marks (Unicode block U+0300..U+036F).
        .normalize('NFD').replace(/[̀-ͯ]/g, '')
        // `đ`/`Đ` are not decomposable so we map them explicitly.
        .replace(/[đ]/g, 'd').replace(/[Đ]/g, 'D')
        // Common typography substitutions back to ASCII.
        .replace(/[–—]/g, '-')       // en-dash, em-dash
        .replace(/[‘’ʻ]/g, "'") // smart single quotes
        .replace(/[“”]/g, '"')       // smart double quotes
        .replace(/[•●]/g, '-')       // bullets
        .replace(/[→]/g, '->')            // right arrow
        .replace(/[^\x20-\x7E]/g, '')          // drop anything still non-ASCII
        .trim() || '-'
    }

    // All-English fallback labels — never reach into i18n which could return Vietnamese.
    const T = (k) => k

    // Local date/time formatters — jsPDF runs in browser so we can rely on
    // `Intl`. Use en-GB locale so weekday/month names are always ASCII.
    const fmtTime = (iso) => {
      if (!iso) return '-'
      try {
        return new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false })
      } catch { return '-' }
    }
    const fmtDate = (iso) => {
      if (!iso) return '-'
      try {
        return new Date(iso).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
      } catch { return '-' }
    }

    // ── Layout constants ─────────────────────────────────────────────────
    const doc = new jsPDF({ unit: 'mm', format: 'a4' })
    const PAGE_W = 210
    const PAGE_H = 297
    const M = 14           // outer margin
    const PRIMARY = [30, 64, 175]   // brand blue
    const ACCENT  = [217, 119, 6]   // amber
    const TEXT    = [31, 41, 55]
    const MUTED   = [107, 114, 128]
    const LIGHT   = [243, 244, 246]
    const BORDER  = [209, 213, 219]

    const setColor = (rgb) => doc.setTextColor(rgb[0], rgb[1], rgb[2])
    const setFill  = (rgb) => doc.setFillColor(rgb[0], rgb[1], rgb[2])
    const setDraw  = (rgb) => doc.setDrawColor(rgb[0], rgb[1], rgb[2])

    // ── Header bar (brand color band) ───────────────────────────────────
    setFill(PRIMARY); doc.rect(0, 0, PAGE_W, 26, 'F')
    setColor([255, 255, 255])
    doc.setFont('helvetica', 'bold'); doc.setFontSize(20)
    doc.text('TravelBooking', M, 13)
    doc.setFont('helvetica', 'normal'); doc.setFontSize(9)
    doc.text('E-TICKET / ITINERARY RECEIPT', M, 19)
    // Right-aligned: issue date
    doc.setFontSize(8)
    const issued = new Date().toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
    doc.text(toAscii(`Issued: ${issued}`), PAGE_W - M, 13, { align: 'right' })
    doc.text('travelbooking.example.com', PAGE_W - M, 19, { align: 'right' })

    // ── PNR card (highlighted box) ───────────────────────────────────────
    let y = 36
    setFill([255, 255, 255]); setDraw(PRIMARY)
    doc.setLineWidth(0.6); doc.roundedRect(M, y, PAGE_W - M * 2, 22, 2, 2, 'D')
    doc.setLineWidth(0.2)
    setColor(MUTED); doc.setFontSize(8)
    doc.text('BOOKING REFERENCE (PNR)', M + 5, y + 7)
    setColor(PRIMARY); doc.setFont('helvetica', 'bold'); doc.setFontSize(22)
    doc.text(toAscii(flight.duffel_booking_ref || '-'), M + 5, y + 17)
    // Right side: airline + booking ID
    setColor(MUTED); doc.setFont('helvetica', 'normal'); doc.setFontSize(8)
    doc.text('AIRLINE', PAGE_W - M - 5, y + 7, { align: 'right' })
    setColor(TEXT); doc.setFont('helvetica', 'bold'); doc.setFontSize(11)
    doc.text(toAscii(flight.airline_name || '-'), PAGE_W - M - 5, y + 13, { align: 'right' })
    setColor(MUTED); doc.setFont('helvetica', 'normal'); doc.setFontSize(7)
    doc.text(toAscii(`Order: ${(flight.duffel_order_id || flight.id || '').slice(0, 22)}`), PAGE_W - M - 5, y + 19, { align: 'right' })

    // ── Flight / Itinerary section ──────────────────────────────────────
    y += 30
    setColor(TEXT); doc.setFont('helvetica', 'bold'); doc.setFontSize(11)
    doc.text('FLIGHT ITINERARY', M, y)
    setDraw(BORDER); doc.setLineWidth(0.2)
    doc.line(M, y + 1.5, PAGE_W - M, y + 1.5)
    y += 7

    const slices = snapshot.slices?.length
      ? snapshot.slices
      : [{
          origin: flight.departure_airport,
          destination: flight.arrival_airport,
          segments: [{
            flight_number: flight.flight_number,
            origin_iata: flight.departure_airport,
            destination_iata: flight.arrival_airport,
            departure_at: flight.departure_at,
            arrival_at: flight.arrival_at,
          }],
        }]

    slices.forEach((sl, sliceIdx) => {
      const segs = sl.segments || []
      // Slice header strip
      setFill(LIGHT)
      doc.rect(M, y, PAGE_W - M * 2, 7, 'F')
      setColor(PRIMARY); doc.setFont('helvetica', 'bold'); doc.setFontSize(9)
      const label = slices.length > 1
        ? `LEG ${sliceIdx + 1} OF ${slices.length}`
        : 'ITINERARY'
      doc.text(label, M + 3, y + 4.8)
      setColor(MUTED); doc.setFont('helvetica', 'normal').setFontSize(9)
      const sliceFrom = toAscii(sl.origin || segs[0]?.origin_iata || '')
      const sliceTo = toAscii(sl.destination || segs[segs.length - 1]?.destination_iata || '')
      doc.text(`${sliceFrom}  ->  ${sliceTo}`, PAGE_W - M - 3, y + 4.8, { align: 'right' })
      y += 10

      segs.forEach((seg, segIdx) => {
        // Segment card
        const cardH = 28
        setFill([255, 255, 255]); setDraw(BORDER)
        doc.setLineWidth(0.3)
        doc.roundedRect(M, y, PAGE_W - M * 2, cardH, 1.5, 1.5, 'D')

        // Flight number / airline badge (left vertical strip)
        setFill(PRIMARY)
        doc.rect(M, y, 32, cardH, 'F')
        setColor([255, 255, 255])
        doc.setFont('helvetica', 'bold').setFontSize(8)
        doc.text('FLIGHT', M + 16, y + 6, { align: 'center' })
        doc.setFontSize(13)
        doc.text(toAscii(seg.flight_number || '-'), M + 16, y + 14, { align: 'center' })
        doc.setFontSize(7).setFont('helvetica', 'normal')
        doc.text(toAscii(seg.airline_name || flight.airline_name || ''),
          M + 16, y + 20, { align: 'center', maxWidth: 30 })

        // Origin block
        const colX1 = M + 38
        const colX2 = M + 90
        const colX3 = PAGE_W - M - 36
        setColor(MUTED); doc.setFontSize(7)
        doc.text('FROM', colX1, y + 5)
        setColor(TEXT); doc.setFont('helvetica', 'bold').setFontSize(16)
        doc.text(toAscii(seg.origin_iata || '-'), colX1, y + 13)
        setColor(MUTED); doc.setFont('helvetica', 'normal').setFontSize(7)
        const oName = toAscii((seg.origin_name || '').slice(0, 28))
        if (oName && oName !== '-') doc.text(oName, colX1, y + 18)
        setColor(TEXT); doc.setFontSize(9)
        doc.text(fmtTime(seg.departure_at), colX1, y + 24)
        setColor(MUTED); doc.setFontSize(7)
        doc.text(fmtDate(seg.departure_at), colX1, y + 27)

        // Arrow + duration (middle) — drawn with vector primitives instead
        // of unicode glyphs so it never renders as a tofu box.
        setDraw(PRIMARY); setFill(PRIMARY)
        doc.setLineWidth(0.5)
        const arrowY = y + 12
        const arrowStartX = colX2 + 2
        const arrowEndX = colX2 + 28
        // Shaft
        doc.line(arrowStartX, arrowY, arrowEndX - 3, arrowY)
        // Triangle head (filled)
        doc.triangle(arrowEndX - 3, arrowY - 1.5,
                     arrowEndX - 3, arrowY + 1.5,
                     arrowEndX,     arrowY, 'F')
        doc.setLineWidth(0.2)
        setColor(MUTED); doc.setFont('helvetica', 'normal').setFontSize(7)
        if (seg.duration) {
          doc.text(toAscii(seg.duration), colX2 + 15, y + 16.5, { align: 'center' })
        }

        // Destination block
        setColor(MUTED); doc.setFontSize(7)
        doc.text('TO', colX3, y + 5)
        setColor(TEXT); doc.setFont('helvetica', 'bold').setFontSize(16)
        doc.text(toAscii(seg.destination_iata || '-'), colX3, y + 13)
        setColor(MUTED); doc.setFont('helvetica', 'normal').setFontSize(7)
        const dName = toAscii((seg.destination_name || '').slice(0, 28))
        if (dName && dName !== '-') doc.text(dName, colX3, y + 18)
        setColor(TEXT); doc.setFontSize(9)
        doc.text(fmtTime(seg.arrival_at), colX3, y + 24)
        setColor(MUTED); doc.setFontSize(7)
        doc.text(fmtDate(seg.arrival_at), colX3, y + 27)

        // Bottom hint: cabin class / aircraft (use ASCII separator " | ")
        if (flight.cabin_class || seg.aircraft) {
          setColor(MUTED); doc.setFontSize(7)
          const meta = [
            flight.cabin_class && `Cabin: ${flight.cabin_class}`,
            seg.aircraft && `Aircraft: ${seg.aircraft}`,
          ].filter(Boolean).join('  |  ')
          if (meta.length < 60) {
            doc.text(toAscii(meta), PAGE_W - M - 3, y + cardH + 4, { align: 'right' })
            y += 4
          }
        }

        y += cardH + 3
        // Layover hint between segments of same slice
        if (segIdx < segs.length - 1) {
          setColor(ACCENT); doc.setFont('helvetica', 'bold').setFontSize(8)
          doc.text(toAscii(`Layover at ${seg.destination_iata}`), M + 38, y + 3)
          setColor(MUTED); doc.setFont('helvetica', 'normal')
          y += 6
        }
      })
      y += 4
    })

    // ── Passengers section ──────────────────────────────────────────────
    if (y > 230) { doc.addPage(); y = M }
    setColor(TEXT); doc.setFont('helvetica', 'bold').setFontSize(11)
    doc.text('PASSENGERS', M, y)
    setDraw(BORDER); doc.setLineWidth(0.2)
    doc.line(M, y + 1.5, PAGE_W - M, y + 1.5)
    y += 6

    const paxList = passengers.length
      ? passengers
      : [{ first_name: flight.passenger_name?.split(' ')?.[0] || '', last_name: flight.passenger_name?.split(' ').slice(1).join(' ') || '', title: 'mr' }]

    // Table header
    setFill(LIGHT); doc.rect(M, y, PAGE_W - M * 2, 6, 'F')
    setColor(MUTED); doc.setFont('helvetica', 'bold').setFontSize(7)
    doc.text('#', M + 3, y + 4)
    doc.text('NAME', M + 12, y + 4)
    doc.text('TYPE', M + 100, y + 4)
    doc.text('E-TICKET NO.', M + 130, y + 4)
    y += 6

    const documents = details.documents || []
    paxList.forEach((p, i) => {
      setColor(TEXT); doc.setFont('helvetica', 'normal').setFontSize(9)
      doc.text(String(i + 1), M + 3, y + 4)
      // Strip diacritics from displayed names — IATA convention is ASCII-only
      // on tickets anyway, so this matches what the airline actually printed.
      const name = toAscii(`${(p.title || '').toUpperCase()}. ${p.first_name || ''} ${p.last_name || ''}`.trim())
      doc.text(name, M + 12, y + 4)
      const paxType = p.age != null
        ? (p.age < 2 ? 'INFANT' : p.age < 12 ? 'CHILD' : 'ADULT')
        : 'ADULT'
      setColor(MUTED); doc.setFontSize(8)
      doc.text(paxType, M + 100, y + 4)
      // E-ticket number from Duffel documents (one per passenger usually)
      const ticketNo = toAscii(documents[i]?.unique_identifier || '-')
      setColor(TEXT); doc.setFont('helvetica', 'bold').setFontSize(8)
      doc.text(ticketNo, M + 130, y + 4)
      doc.setFont('helvetica', 'normal')
      // Row separator
      setDraw(BORDER); doc.setLineWidth(0.1)
      doc.line(M, y + 6, PAGE_W - M, y + 6)
      y += 7
    })

    // ── Fare summary ────────────────────────────────────────────────────
    y += 5
    if (y > 245) { doc.addPage(); y = M }
    setColor(TEXT); doc.setFont('helvetica', 'bold').setFontSize(11)
    doc.text('FARE SUMMARY', M, y)
    setDraw(BORDER); doc.line(M, y + 1.5, PAGE_W - M, y + 1.5)
    y += 8
    setColor(MUTED); doc.setFont('helvetica', 'normal').setFontSize(9)
    doc.text('Total paid', M, y)
    setColor(PRIMARY); doc.setFont('helvetica', 'bold').setFontSize(14)
    const totalStr = `${flight.currency || 'USD'} ${Number(flight.total_amount || 0).toFixed(2)}`
    doc.text(toAscii(totalStr), PAGE_W - M, y, { align: 'right' })

    // ── Important info footer band ──────────────────────────────────────
    y = PAGE_H - 45
    setFill(LIGHT); doc.rect(0, y, PAGE_W, 45, 'F')
    setColor(PRIMARY); doc.setFont('helvetica', 'bold').setFontSize(9)
    doc.text('IMPORTANT INFORMATION', M, y + 6)
    setColor(TEXT); doc.setFont('helvetica', 'normal').setFontSize(8)
    // Bullets drawn as ASCII '-' to stay within Helvetica's Latin-1 range.
    const notes = [
      '-  Please arrive at the airport at least 2 hours before scheduled departure (3 hours for international flights).',
      '-  Online check-in opens 24 hours before departure and closes 1 hour before scheduled departure.',
      '-  Present this e-ticket (printed or digital) together with a valid government-issued photo ID at check-in.',
      "-  Baggage allowance varies by fare class. Check your booking details or the airline's website.",
      '-  Flight times are local to each airport. Always reconfirm with the airline 24h before departure.',
    ]
    let ny = y + 11
    notes.forEach((line) => {
      doc.text(toAscii(line), M, ny, { maxWidth: PAGE_W - M * 2 })
      ny += 4.5
    })

    // ── Footer line: PNR repeated + page ────────────────────────────────
    setColor(MUTED); doc.setFontSize(7)
    doc.text(toAscii(`PNR: ${flight.duffel_booking_ref || '-'}  |  Generated by TravelBooking`), M, PAGE_H - 5)
    doc.text('Page 1', PAGE_W - M, PAGE_H - 5, { align: 'right' })

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

        {/* Change history */}
        {Array.isArray(details.change_history) && details.change_history.length > 0 && (
          <div className="bg-white border rounded-2xl p-6 mb-6">
            <h3 className="font-heading font-bold text-lg mb-4 flex items-center gap-2">
              <History className="w-5 h-5" /> {t('flights:manage.changeHistory', 'Change history')}
            </h3>
            <ul className="space-y-3">
              {details.change_history.map((entry, i) => (
                <li key={i} className="text-sm border-l-2 border-primary/30 pl-3">
                  <p className="font-medium">
                    {(entry.slices_added || []).map((s) => `${s.origin}→${s.destination}`).join(', ') || 'Itinerary updated'}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {entry.occurred_at?.slice(0, 16).replace('T', ' ')}
                    {entry.total_diff != null && (
                      <span className="ml-2">
                        {entry.total_diff > 0
                          ? `· Charged ${fmt(entry.total_diff, entry.currency)}`
                          : entry.total_diff < 0
                            ? `· Refunded ${fmt(Math.abs(entry.total_diff), entry.currency)}`
                            : '· No charge'}
                      </span>
                    )}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        )}

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
          {canCancel && flight.duffel_order_id && (
            <button
              onClick={() => navigate(`/flights/bookings/${bookingId}/change`)}
              className="flex items-center gap-2 border border-accent text-accent font-semibold px-4 py-2.5 rounded-lg hover:bg-accent/5 transition-colors"
            >
              <ArrowRightLeft className="w-4 h-4" />
              {t('flights:manage.changeFlight', 'Change flight')}
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
