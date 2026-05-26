import { formatDate } from '@/utils/formatters'

// Builds a branded, invoice-style PDF for a booking and triggers download.
// Used from the confirmation page and from the My Bookings list — both pass
// the same booking shape returned by `bookingsApi.get` / `bookingsApi.list`.
//
// `fmt` is the user's currency formatter (USD or VND depending on preference).
export async function downloadBookingPdf(booking, fmt) {
  if (!booking?.id) return
  const { default: jsPDF } = await import('jspdf')
  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const id = booking.id

  const PAGE_W = doc.internal.pageSize.getWidth()
  const PAGE_H = doc.internal.pageSize.getHeight()
  const M = 16
  const CONTENT_W = PAGE_W - M * 2

  const C_PRIMARY = [0, 53, 128]
  const C_PRIMARY_LIGHT = [0, 85, 160]
  const C_ACCENT = [255, 107, 53]
  const C_SUCCESS = [16, 185, 129]
  const C_TEXT = [30, 41, 59]
  const C_MUTED = [100, 116, 139]
  const C_BORDER = [226, 232, 240]
  const C_SURFACE = [248, 250, 252]

  const setFill = (rgb) => doc.setFillColor(rgb[0], rgb[1], rgb[2])
  const setText = (rgb) => doc.setTextColor(rgb[0], rgb[1], rgb[2])
  const setDraw = (rgb) => doc.setDrawColor(rgb[0], rgb[1], rgb[2])

  // ---------- Header band ----------
  setFill(C_PRIMARY)
  doc.rect(0, 0, PAGE_W, 32, 'F')
  setFill(C_PRIMARY_LIGHT)
  doc.rect(0, 32, PAGE_W, 2, 'F')
  setFill(C_ACCENT)
  doc.rect(0, 34, PAGE_W, 1, 'F')

  setText([255, 255, 255])
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(20)
  doc.text('TravelBooking', M, 16)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(10)
  doc.text('Your trip, confirmed.', M, 22)

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(13)
  doc.text('BOOKING CONFIRMATION', PAGE_W - M, 16, { align: 'right' })
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(9)
  doc.text(`Issued: ${formatDate(new Date().toISOString())}`, PAGE_W - M, 22, { align: 'right' })

  let y = 48

  // ---------- Status + booking reference card ----------
  const status = (booking?.status || 'pending').toLowerCase()
  const isConfirmed = status === 'confirmed' || status === 'completed' || status === 'paid'
  const isCancelled = status === 'cancelled' || status === 'canceled' || status === 'failed'
  const statusColor = isConfirmed ? C_SUCCESS : isCancelled ? [239, 68, 68] : [245, 158, 11]
  const statusLabel = status.toUpperCase()

  setFill(C_SURFACE)
  setDraw(C_BORDER)
  doc.roundedRect(M, y, CONTENT_W, 28, 3, 3, 'FD')

  setText(C_MUTED)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8)
  doc.text('BOOKING REFERENCE', M + 6, y + 8)
  setText(C_PRIMARY)
  doc.setFont('courier', 'bold')
  doc.setFontSize(18)
  doc.text(id.slice(0, 8).toUpperCase(), M + 6, y + 19)
  setText(C_MUTED)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(7)
  doc.text(`Full ID: ${id}`, M + 6, y + 24)

  doc.setFont('helvetica', 'bold')
  doc.setFontSize(9)
  const pillW = doc.getTextWidth(statusLabel) + 10
  const pillX = PAGE_W - M - 6 - pillW
  const pillY = y + 6
  setFill(statusColor)
  doc.roundedRect(pillX, pillY, pillW, 7, 3.5, 3.5, 'F')
  setText([255, 255, 255])
  doc.text(statusLabel, pillX + pillW / 2, pillY + 5, { align: 'center' })

  setText(C_MUTED)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8)
  if (booking?.created_at) {
    doc.text(`Booked on ${formatDate(booking.created_at)}`, PAGE_W - M - 6, pillY + 14, { align: 'right' })
  }

  y += 36

  // ---------- Helpers ----------
  const sectionTitle = (label, accent = C_PRIMARY) => {
    setFill(accent)
    doc.rect(M, y, 1.2, 6, 'F')
    setText(C_TEXT)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(12)
    doc.text(label, M + 4, y + 5)
    y += 9
  }

  const ensureSpace = (needed) => {
    if (y + needed > PAGE_H - 28) {
      doc.addPage()
      y = M + 4
    }
  }

  const drawDetailGrid = (cells) => {
    const colW = (CONTENT_W - 4) / 2
    const rowH = 14
    for (let i = 0; i < cells.length; i += 2) {
      ensureSpace(rowH + 4)
      const row = [cells[i], cells[i + 1]].filter(Boolean)
      row.forEach((cell, idx) => {
        const x = M + idx * (colW + 4)
        setFill([255, 255, 255])
        setDraw(C_BORDER)
        doc.roundedRect(x, y, colW, rowH, 2, 2, 'FD')
        setText(C_MUTED)
        doc.setFont('helvetica', 'normal')
        doc.setFontSize(7.5)
        doc.text(cell.label.toUpperCase(), x + 4, y + 5)
        setText(C_TEXT)
        doc.setFont('helvetica', 'bold')
        doc.setFontSize(10)
        const valueLines = doc.splitTextToSize(String(cell.value ?? '—'), colW - 8)
        doc.text(valueLines[0] || '—', x + 4, y + 11)
      })
      y += rowH + 3
    }
  }

  // ---------- Per-item sections ----------
  const items = booking?.items || []

  items.forEach((item, idx) => {
    ensureSpace(60)

    if (item.item_type === 'room') {
      const hotelName = item.hotel?.name || item.hotel_name || 'Hotel stay'
      const location = [item.hotel?.city, item.hotel?.country].filter(Boolean).join(', ')

      sectionTitle(`Hotel · Item ${idx + 1}`, C_PRIMARY)

      setFill([255, 255, 255])
      setDraw(C_BORDER)
      doc.roundedRect(M, y, CONTENT_W, location ? 18 : 14, 2, 2, 'FD')
      setText(C_TEXT)
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(13)
      const nameLines = doc.splitTextToSize(hotelName, CONTENT_W - 10)
      doc.text(nameLines[0], M + 5, y + 8)
      if (location) {
        setText(C_MUTED)
        doc.setFont('helvetica', 'normal')
        doc.setFontSize(9)
        doc.text(location, M + 5, y + 14)
      }
      y += (location ? 18 : 14) + 4

      const checkIn = item.check_in ? new Date(item.check_in) : null
      const checkOut = item.check_out ? new Date(item.check_out) : null
      const nights = checkIn && checkOut
        ? Math.max(1, Math.round((checkOut - checkIn) / (1000 * 60 * 60 * 24)))
        : null
      const adults = item.adults_count ?? null
      const children = item.children_count ?? 0
      const guestsLine = adults != null
        ? `${adults} adult${adults === 1 ? '' : 's'}${children > 0 ? ` · ${children} child${children === 1 ? '' : 'ren'}` : ''}`
        : `${item.quantity} guest${item.quantity === 1 ? '' : 's'}`

      drawDetailGrid([
        { label: 'Check-in', value: item.check_in ? formatDate(item.check_in, 'EEE, MMM dd, yyyy') : '—' },
        { label: 'Check-out', value: item.check_out ? formatDate(item.check_out, 'EEE, MMM dd, yyyy') : '—' },
        { label: 'Nights', value: nights != null ? `${nights} night${nights === 1 ? '' : 's'}` : '—' },
        { label: 'Rooms', value: `${item.quantity}` },
        { label: 'Guests', value: guestsLine },
        { label: 'Room type', value: item.room?.name || item.room?.room_type || '—' },
      ])

      const infoLines = []
      if (item.refundable === true) {
        infoLines.push({ text: 'Free cancellation available', color: C_SUCCESS })
        if (item.cancellation_deadline) {
          infoLines.push({
            text: `Cancel by ${formatDate(item.cancellation_deadline)} for a full refund.`,
            color: C_MUTED,
          })
        }
      } else if (item.refundable === false) {
        infoLines.push({ text: 'Non-refundable booking', color: [239, 68, 68] })
        infoLines.push({ text: 'This rate cannot be cancelled or modified.', color: C_MUTED })
      }
      if (item.liteapi_booking_id) {
        infoLines.push({ text: `Supplier reference: ${item.liteapi_booking_id}`, color: C_MUTED })
      }
      if (infoLines.length) {
        ensureSpace(infoLines.length * 5 + 8)
        const boxH = infoLines.length * 5 + 6
        setFill([255, 251, 235])
        setDraw([254, 215, 170])
        doc.roundedRect(M, y, CONTENT_W, boxH, 2, 2, 'FD')
        let iy = y + 5
        infoLines.forEach((ln) => {
          setText(ln.color)
          doc.setFont('helvetica', ln.color === C_MUTED ? 'normal' : 'bold')
          doc.setFontSize(9)
          doc.text(ln.text, M + 5, iy)
          iy += 5
        })
        y += boxH + 4
      }
    } else if (item.item_type === 'tour') {
      sectionTitle(`Tour · Item ${idx + 1}`, C_ACCENT)
      const tourName = item.tour?.name || item.tour_name || 'Tour experience'
      setFill([255, 255, 255])
      setDraw(C_BORDER)
      doc.roundedRect(M, y, CONTENT_W, 14, 2, 2, 'FD')
      setText(C_TEXT)
      doc.setFont('helvetica', 'bold')
      doc.setFontSize(12)
      doc.text(doc.splitTextToSize(tourName, CONTENT_W - 10)[0], M + 5, y + 9)
      y += 18
      drawDetailGrid([
        { label: 'Tour date', value: item.check_in ? formatDate(item.check_in, 'EEE, MMM dd, yyyy') : '—' },
        { label: 'Travellers', value: `${item.quantity}` },
      ])
    } else if (item.item_type === 'flight') {
      sectionTitle(`Flight · Item ${idx + 1}`, C_PRIMARY_LIGHT)
      const flight = item.flight_booking
      if (flight) {
        setFill([255, 255, 255])
        setDraw(C_BORDER)
        doc.roundedRect(M, y, CONTENT_W, 18, 2, 2, 'FD')
        setText(C_TEXT)
        doc.setFont('helvetica', 'bold')
        doc.setFontSize(12)
        doc.text(`${flight.airline_name} · ${flight.flight_number}`, M + 5, y + 8)
        setText(C_MUTED)
        doc.setFont('helvetica', 'normal')
        doc.setFontSize(9)
        doc.text(`${flight.departure_airport} → ${flight.arrival_airport}`, M + 5, y + 14)
        y += 22
        drawDetailGrid([
          { label: 'Departure', value: flight.departure_at ? formatDate(flight.departure_at, 'EEE, MMM dd, HH:mm') : '—' },
          { label: 'Arrival', value: flight.arrival_at ? formatDate(flight.arrival_at, 'EEE, MMM dd, HH:mm') : '—' },
          { label: 'Cabin', value: flight.cabin_class || 'Economy' },
          { label: 'PNR', value: flight.duffel_booking_ref || '—' },
        ])
      }
    }

    ensureSpace(10)
    setText(C_MUTED)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(9)
    doc.text('Item subtotal', M, y + 5)
    setText(C_TEXT)
    doc.setFont('helvetica', 'bold')
    doc.text(fmt(item.subtotal), PAGE_W - M, y + 5, { align: 'right' })
    setDraw(C_BORDER)
    doc.line(M, y + 8, PAGE_W - M, y + 8)
    y += 12
  })

  // ---------- Payment summary ----------
  ensureSpace(60)
  sectionTitle('Payment summary', C_PRIMARY)

  const rows = []
  if (booking?.subtotal > 0) rows.push(['Subtotal', fmt(booking.subtotal), false])
  if (booking?.taxes > 0) rows.push(['Taxes & fees', fmt(booking.taxes), false])
  if (booking?.tier_discount > 0) rows.push(['Member discount', `−${fmt(booking.tier_discount)}`, 'discount'])
  if (booking?.discount_amount > 0) rows.push(['Voucher discount', `−${fmt(booking.discount_amount)}`, 'discount'])

  const summaryH = rows.length * 7 + 16
  setFill(C_SURFACE)
  setDraw(C_BORDER)
  doc.roundedRect(M, y, CONTENT_W, summaryH, 2, 2, 'FD')

  let ry = y + 7
  rows.forEach(([label, value, kind]) => {
    setText(C_MUTED)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(10)
    doc.text(label, M + 5, ry)
    setText(kind === 'discount' ? C_SUCCESS : C_TEXT)
    doc.setFont('helvetica', 'normal')
    doc.text(value, PAGE_W - M - 5, ry, { align: 'right' })
    ry += 7
  })

  setDraw(C_BORDER)
  doc.line(M + 5, ry - 2, PAGE_W - M - 5, ry - 2)
  setText(C_TEXT)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(11)
  doc.text('TOTAL PAID', M + 5, ry + 5)
  setText(C_PRIMARY)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(14)
  doc.text(fmt(booking?.total_price), PAGE_W - M - 5, ry + 5, { align: 'right' })

  y += summaryH + 6

  // ---------- Thank-you note ----------
  ensureSpace(20)
  setFill([239, 246, 255])
  setDraw([191, 219, 254])
  doc.roundedRect(M, y, CONTENT_W, 16, 2, 2, 'FD')
  setText(C_PRIMARY)
  doc.setFont('helvetica', 'bold')
  doc.setFontSize(10)
  doc.text('Thank you for booking with TravelBooking!', M + 5, y + 7)
  setText(C_MUTED)
  doc.setFont('helvetica', 'normal')
  doc.setFontSize(8.5)
  doc.text('Show this confirmation at check-in. Manage your booking anytime from your account.', M + 5, y + 12)
  y += 20

  // ---------- Footer ----------
  const pageCount = doc.internal.getNumberOfPages()
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i)
    setDraw(C_BORDER)
    doc.line(M, PAGE_H - 14, PAGE_W - M, PAGE_H - 14)
    setText(C_MUTED)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(8)
    doc.text('TravelBooking · support@travelbooking.example', M, PAGE_H - 8)
    doc.text(`Page ${i} of ${pageCount}`, PAGE_W - M, PAGE_H - 8, { align: 'right' })
  }

  doc.save(`booking-${id.slice(0, 8)}.pdf`)
}
