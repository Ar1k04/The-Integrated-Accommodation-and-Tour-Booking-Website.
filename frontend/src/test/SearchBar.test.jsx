import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import SearchBar from '@/components/common/SearchBar'

vi.mock('@/store/searchStore', () => ({
  useSearchStore: vi.fn(() => ({
    destination: '',
    checkIn: null,
    checkOut: null,
    guests: { adults: 2, children: 0, rooms: 1 },
    searchType: 'hotels',
    setDestination: vi.fn(),
    setDates: vi.fn(),
    setGuests: vi.fn(),
    setSearchType: vi.fn(),
  })),
}))

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

function renderComponent(props = {}) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SearchBar {...props} />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('SearchBar', () => {
  it('renders the destination input', () => {
    renderComponent()
    expect(screen.getByPlaceholderText('Where are you going?')).toBeInTheDocument()
  })

  it('renders search button', () => {
    renderComponent()
    const btn = screen.getByRole('button', { name: /search/i })
    expect(btn).toBeInTheDocument()
  })

  it('shows hotel/tour tabs in hero variant', () => {
    renderComponent({ variant: 'hero' })
    expect(screen.getByText('Hotels')).toBeInTheDocument()
    expect(screen.getByText('Tours & Activities')).toBeInTheDocument()
  })

  it('allows typing in destination', () => {
    renderComponent()
    const input = screen.getByPlaceholderText('Where are you going?')
    fireEvent.change(input, { target: { value: 'Paris' } })
    expect(input.value).toBe('Paris')
  })
})
