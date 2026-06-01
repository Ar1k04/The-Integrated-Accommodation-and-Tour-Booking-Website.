import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// i18n: t trả về chính key cho dễ assert. Currency dùng store thật (USD).
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (k) => k }) }))

import PriceBreakdown from '@/components/common/PriceBreakdown'
import { useUiStore } from '@/store/uiStore'

beforeEach(() => useUiStore.setState({ currency: 'USD', usdToVnd: 25000 }))

describe('PriceBreakdown', () => {
  it('computes subtotal, 10% taxes and total', () => {
    render(<PriceBreakdown pricePerNight={100} nights={2} />)
    expect(screen.getByText('$200')).toBeInTheDocument() // subtotal = 100 × 2
    expect(screen.getByText('$20')).toBeInTheDocument() // taxes = 10%
    expect(screen.getByText('$220')).toBeInTheDocument() // total
  })

  it('subtracts a voucher discount from the total', () => {
    render(<PriceBreakdown pricePerNight={100} nights={2} discount={50} />)
    expect(screen.getByText('-$50')).toBeInTheDocument()
    expect(screen.getByText('$170')).toBeInTheDocument() // 200 + 20 − 50
  })

  it('renders the member tier discount row when provided', () => {
    render(
      <PriceBreakdown
        pricePerNight={100}
        nights={1}
        tierDiscount={10}
        tierName="Gold"
        tierDiscountPct={10}
      />,
    )
    expect(screen.getByText('-$10')).toBeInTheDocument()
  })

  it('hides the discount row when there is no discount', () => {
    render(<PriceBreakdown pricePerNight={100} nights={1} />)
    expect(screen.queryByText('common.discount')).toBeNull()
  })
})
