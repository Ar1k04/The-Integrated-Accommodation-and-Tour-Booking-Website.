import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import DateRangeCalendar from '@/components/common/DateRangeCalendar'
import {
  formatCalendarPrice,
  formatCalendarPriceVnd,
  getCalendarPriceEstimate,
} from '@/utils/calendarPrice'
import { useUiStore } from '@/store/uiStore'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key, optionsOrDefault) => {
      if (typeof optionsOrDefault === 'string') return optionsOrDefault
      return optionsOrDefault?.defaultValue || _key
    },
  }),
}))

describe('DateRangeCalendar price hints', () => {
  const juneFirst = new Date(2026, 5, 1)

  beforeEach(() => {
    useUiStore.setState({ currency: 'USD', usdToVnd: 25_000 })
  })

  it('does not show price hints without a reference price', () => {
    render(
      <DateRangeCalendar
        checkIn={juneFirst}
        checkOut={null}
        minDate={juneFirst}
        onChange={vi.fn()}
      />
    )

    expect(screen.queryByText(/Estimated price/i)).not.toBeInTheDocument()
    expect(screen.getByText('June 2026')).toBeInTheDocument()
    expect(screen.getByText('July 2026')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '2026-06-02' })).toBeInTheDocument()
  })

  it('shows USD price hints when the selected currency is USD', () => {
    render(
      <DateRangeCalendar
        checkIn={juneFirst}
        checkOut={null}
        minDate={juneFirst}
        onChange={vi.fn()}
        priceBaseUsd={42}
      />
    )

    expect(screen.getByText(/Estimated price per night/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /2026-06-02, estimated \$/i })).toBeInTheDocument()
    expect(screen.getAllByText(/^\$/).length).toBeGreaterThan(0)
  })

  it('shows compact VND price hints when the selected currency is VND', () => {
    useUiStore.setState({ currency: 'VND', usdToVnd: 25_000 })

    render(
      <DateRangeCalendar
        checkIn={juneFirst}
        checkOut={null}
        minDate={juneFirst}
        onChange={vi.fn()}
        priceBaseUsd={42}
      />
    )

    expect(screen.getByRole('button', { name: /2026-06-02, estimated .+K/i })).toBeInTheDocument()
    expect(screen.getAllByText(/K$/).length).toBeGreaterThan(0)
  })

  it('formats the calendar price in the requested currency', () => {
    expect(formatCalendarPrice(42, 'USD', 25_000)).toBe('$42')
    expect(formatCalendarPrice(42, 'VND', 25_000)).toBe('1.050K')
    expect(formatCalendarPriceVnd(42, 25_000)).toBe('1.050K')
    expect(getCalendarPriceEstimate(42, juneFirst)).toBeGreaterThan(0)
  })
})
