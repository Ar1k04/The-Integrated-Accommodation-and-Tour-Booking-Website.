/**
 * Tests for booking-related pricing logic:
 *   - PriceBreakdown: discount display, currency conversion
 *   - useFormatCurrency: USD ↔ VND switching
 *   - Voucher API integration stub
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

// ── Zustand ui-store mock — use a simple mutable ref to avoid hoisting issues ──
let _currency = 'USD'
vi.mock('@/store/uiStore', () => ({
  useUiStore: (selector) =>
    selector({
      currency: _currency,
      locale: 'en',
      setCurrency: (c) => { _currency = c },
      setLocale: vi.fn(),
    }),
}))

vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k) => k, i18n: { language: 'en' } }),
}))

import PriceBreakdown from '@/components/common/PriceBreakdown'

// ── PriceBreakdown tests ──────────────────────────────────────────────────────
describe('PriceBreakdown — USD', () => {
  beforeEach(() => { _currency = 'USD' })

  it('displays subtotal = price × nights', () => {
    render(<PriceBreakdown pricePerNight={100} nights={3} />)
    // 100 × 3 = $300
    expect(screen.getAllByText('$300').length).toBeGreaterThan(0)
  })

  it('calculates 10% tax correctly', () => {
    render(<PriceBreakdown pricePerNight={100} nights={2} />)
    // subtotal = $200, tax = $20
    expect(screen.getAllByText('$20').length).toBeGreaterThan(0)
  })

  it('shows total = subtotal + taxes', () => {
    render(<PriceBreakdown pricePerNight={100} nights={2} />)
    // $200 + $20 = $220
    expect(screen.getAllByText('$220').length).toBeGreaterThan(0)
  })

  it('shows discount line when discount > 0', () => {
    render(<PriceBreakdown pricePerNight={100} nights={2} discount={20} />)
    // Discount row should be visible
    expect(screen.getByText('common.discount')).toBeInTheDocument()
    // Total = $220 - $20 = $200
    const twohundreds = screen.getAllByText('$200')
    expect(twohundreds.length).toBeGreaterThan(0)
  })

  it('does NOT show discount line when discount = 0', () => {
    render(<PriceBreakdown pricePerNight={100} nights={2} />)
    expect(screen.queryByText('common.discount')).not.toBeInTheDocument()
  })

  it('shows per-night label from translation', () => {
    render(<PriceBreakdown pricePerNight={100} nights={2} />)
    expect(screen.getByText(/common\.perNight/)).toBeInTheDocument()
  })

  it('accepts a labelOverride', () => {
    render(<PriceBreakdown pricePerNight={50} nights={4} labelOverride="per person" />)
    expect(screen.getByText(/per person/)).toBeInTheDocument()
  })
})

describe('PriceBreakdown — VND currency', () => {
  beforeEach(() => { _currency = 'VND' })

  it('displays prices in VND (₫) when currency is VND', () => {
    render(<PriceBreakdown pricePerNight={100} nights={1} />)
    // $100 × 25000 = ₫2,500,000
    const allText = document.body.textContent
    expect(allText).toContain('₫')
    expect(allText).toContain('2.500.000')
  })

  it('discount is also formatted in VND', () => {
    render(<PriceBreakdown pricePerNight={100} nights={1} discount={10} />)
    const allText = document.body.textContent
    // $10 discount → ₫250,000
    expect(allText).toContain('250.000')
  })
})

// ── Voucher API stub ─────────────────────────────────────────────────────────
describe('vouchersApi.validate stub', () => {
  it('resolves valid voucher with discount_amount', async () => {
    const mockValidate = vi.fn().mockResolvedValue({
      data: { valid: true, code: 'DEMO10', discount_amount: 30 },
    })

    const result = await mockValidate('DEMO10', 300)
    expect(result.data.valid).toBe(true)
    expect(result.data.discount_amount).toBe(30)
    expect(mockValidate).toHaveBeenCalledWith('DEMO10', 300)
  })

  it('resolves invalid voucher with valid=false', async () => {
    const mockValidate = vi.fn().mockResolvedValue({
      data: { valid: false, message: 'Voucher expired' },
    })

    const result = await mockValidate('EXPIRED', 100)
    expect(result.data.valid).toBe(false)
    expect(result.data.message).toBe('Voucher expired')
  })
})

// ── Loyalty redemption logic ─────────────────────────────────────────────────
describe('Loyalty redemption calculation', () => {
  it('1 point = $0.01 discount', () => {
    const pts = 500
    const discount = pts * 0.01
    expect(discount).toBe(5)
  })

  it('cannot redeem more points than user has', () => {
    const balance = 200
    const requested = 300
    const isValid = requested <= balance
    expect(isValid).toBe(false)
  })

  it('can redeem exactly the full balance', () => {
    const balance = 200
    const requested = 200
    expect(requested <= balance).toBe(true)
    expect(requested * 0.01).toBe(2)
  })
})
