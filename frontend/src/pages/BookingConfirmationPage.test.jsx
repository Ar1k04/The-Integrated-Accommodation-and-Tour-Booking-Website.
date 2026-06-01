import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import BookingConfirmationPage from './BookingConfirmationPage'

vi.mock('@/api/bookingsApi', () => ({ bookingsApi: { get: vi.fn() } }))
vi.mock('@/hooks/useFormatCurrency', () => ({ useFormatCurrency: () => (n) => `$${n}` }))
vi.mock('@/utils/bookingPdf', () => ({ downloadBookingPdf: vi.fn() }))
vi.mock('react-helmet-async', () => ({ Helmet: () => null }))
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (k) => k }) }))
vi.mock('sonner', () => ({ toast: { success: vi.fn() } }))
vi.mock('framer-motion', () => ({
  motion: new Proxy({}, { get: () => ({ children }) => <div>{children}</div> }),
}))

import { bookingsApi } from '@/api/bookingsApi'

function setup(status) {
  bookingsApi.get.mockResolvedValue({ data: { id: 'abc12345', status, items: [], total_price: 100 } })
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/bookings/abc12345/confirmation']}>
        <Routes>
          <Route path="/bookings/:id/confirmation" element={<BookingConfirmationPage />} />
          <Route path="/bookings/:id/failure" element={<div>FAILURE PAGE</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('BookingConfirmationPage (FE-01)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('shows a finalizing state while the booking is still pending', async () => {
    setup('pending')
    expect(await screen.findByText('confirmation.finalizingTitle')).toBeInTheDocument()
    // The success heading must NOT be shown yet.
    expect(screen.queryByText('confirmation.title')).not.toBeInTheDocument()
  })

  it('redirects a cancelled booking to the failure page', async () => {
    setup('cancelled')
    expect(await screen.findByText('FAILURE PAGE')).toBeInTheDocument()
  })
})
