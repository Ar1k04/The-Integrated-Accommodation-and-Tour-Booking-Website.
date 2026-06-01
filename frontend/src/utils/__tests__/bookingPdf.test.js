import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock jsPDF: ta không kiểm tra việc render PDF thật (nặng, cần canvas) mà
// kiểm tra rằng downloadBookingPdf điều phối đúng — khởi tạo doc, ghi các phần
// chính, gọi fmt cho tiền, và save với tên file đúng. vi.hoisted để mock object
// tồn tại trước khi vi.mock chạy.
const { mockDoc, jsPDFCtor } = vi.hoisted(() => {
  const doc = {
    internal: {
      pageSize: { getWidth: () => 210, getHeight: () => 297 },
      getNumberOfPages: () => 1,
    },
    setFillColor: vi.fn(),
    setTextColor: vi.fn(),
    setDrawColor: vi.fn(),
    setFont: vi.fn(),
    setFontSize: vi.fn(),
    rect: vi.fn(),
    roundedRect: vi.fn(),
    line: vi.fn(),
    text: vi.fn(),
    splitTextToSize: (s) => [String(s)],
    getTextWidth: () => 10,
    addPage: vi.fn(),
    setPage: vi.fn(),
    save: vi.fn(),
  }
  // Hàm thường (không phải arrow) để có thể dùng với `new jsPDF()`.
  return { mockDoc: doc, jsPDFCtor: vi.fn(function () { return doc }) }
})

vi.mock('jspdf', () => ({ default: jsPDFCtor }))

import { downloadBookingPdf } from '@/utils/bookingPdf'

let fmt
beforeEach(() => {
  vi.clearAllMocks()
  fmt = vi.fn((n) => `$${Number(n || 0).toFixed(2)}`)
})

const roomBooking = {
  id: 'abcd1234-5678-90ef',
  status: 'confirmed',
  subtotal: 200,
  taxes: 20,
  total_price: 220,
  created_at: '2026-05-01',
  items: [
    {
      item_type: 'room',
      quantity: 1,
      subtotal: 200,
      check_in: '2026-06-01',
      check_out: '2026-06-03',
      hotel: { name: 'Hotel X', city: 'Paris', country: 'France' },
      room: { name: 'Deluxe' },
      adults_count: 2,
      children_count: 0,
      refundable: true,
    },
  ],
}

describe('downloadBookingPdf — guards', () => {
  it('does nothing for a null booking', async () => {
    await downloadBookingPdf(null, fmt)
    expect(jsPDFCtor).not.toHaveBeenCalled()
  })

  it('does nothing for a booking without an id', async () => {
    await downloadBookingPdf({ status: 'confirmed' }, fmt)
    expect(jsPDFCtor).not.toHaveBeenCalled()
  })
})

describe('downloadBookingPdf — generation', () => {
  it('creates a PDF and saves it with the short-id filename', async () => {
    await downloadBookingPdf(roomBooking, fmt)
    expect(jsPDFCtor).toHaveBeenCalledTimes(1)
    expect(mockDoc.save).toHaveBeenCalledWith('booking-abcd1234.pdf')
  })

  it('renders the branded header and confirmation title', async () => {
    await downloadBookingPdf(roomBooking, fmt)
    const texts = mockDoc.text.mock.calls.map((c) => c[0])
    expect(texts).toContain('TravelBooking')
    expect(texts).toContain('BOOKING CONFIRMATION')
  })

  it('formats monetary values via the supplied formatter', async () => {
    await downloadBookingPdf(roomBooking, fmt)
    expect(fmt).toHaveBeenCalledWith(220) // total_price
    expect(fmt).toHaveBeenCalledWith(200) // item subtotal
  })

  it('handles a mixed tour + flight booking without throwing', async () => {
    const mixed = {
      id: 'ffff0000-1111',
      status: 'pending',
      subtotal: 300,
      total_price: 300,
      items: [
        { item_type: 'tour', quantity: 2, subtotal: 100, check_in: '2026-07-01', tour: { name: 'City Tour' } },
        {
          item_type: 'flight',
          quantity: 1,
          subtotal: 200,
          flight_booking: {
            airline_name: 'Duffel Airways',
            flight_number: 'ZZ100',
            departure_airport: 'SGN',
            arrival_airport: 'HAN',
            departure_at: '2026-07-02T08:00:00Z',
            arrival_at: '2026-07-02T10:00:00Z',
            cabin_class: 'economy',
            duffel_booking_ref: 'PNR123',
          },
        },
      ],
    }
    await downloadBookingPdf(mixed, fmt)
    expect(mockDoc.save).toHaveBeenCalledWith('booking-ffff0000.pdf')
  })
})
