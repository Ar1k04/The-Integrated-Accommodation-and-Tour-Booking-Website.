import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import HotelCard from '@/components/hotel/HotelCard'

const mockHotel = {
  id: '123',
  name: 'Grand Palace Hotel',
  city: 'Bangkok',
  country: 'Thailand',
  min_room_price: 120,
  star_rating: 5,
  avg_rating: 9.2,
  total_reviews: 45,
  property_type: 'resort',
  amenities: ['wifi', 'pool', 'gym', 'spa', 'parking', 'restaurant'],
  images: ['https://placehold.co/400x300'],
}

function renderWithRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('HotelCard', () => {
  it('renders the hotel name', () => {
    renderWithRouter(<HotelCard hotel={mockHotel} />)
    expect(screen.getByText('Grand Palace Hotel')).toBeInTheDocument()
  })

  it('renders the location', () => {
    renderWithRouter(<HotelCard hotel={mockHotel} />)
    expect(screen.getByText('Bangkok, Thailand')).toBeInTheDocument()
  })

  it('displays the price', () => {
    renderWithRouter(<HotelCard hotel={mockHotel} />)
    expect(screen.getByText('$120')).toBeInTheDocument()
  })

  it('shows rating badge', () => {
    renderWithRouter(<HotelCard hotel={mockHotel} />)
    expect(screen.getByText('9.2')).toBeInTheDocument()
  })

  it('shows property type', () => {
    renderWithRouter(<HotelCard hotel={mockHotel} />)
    expect(screen.getByText('resort')).toBeInTheDocument()
  })

  it('shows max 5 amenities + overflow', () => {
    renderWithRouter(<HotelCard hotel={mockHotel} />)
    expect(screen.getByText('+1 more')).toBeInTheDocument()
  })

  it('links to hotel detail page', () => {
    renderWithRouter(<HotelCard hotel={mockHotel} />)
    const links = screen.getAllByRole('link')
    const hotelLinks = links.filter(l => l.getAttribute('href')?.includes('/hotels/123'))
    expect(hotelLinks.length).toBeGreaterThan(0)
  })
})
