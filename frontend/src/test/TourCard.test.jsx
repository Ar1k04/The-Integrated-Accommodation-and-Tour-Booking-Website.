import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import TourCard from '@/components/tour/TourCard'

const mockTour = {
  id: 'tour-1',
  name: 'Ancient Temples Tour',
  city: 'Kyoto',
  duration_days: 3,
  max_participants: 15,
  price_per_person: 250,
  avg_rating: 4.8,
  total_reviews: 32,
  category: 'cultural',
  images: ['https://placehold.co/400x300'],
}

function renderWithRouter(ui) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('TourCard', () => {
  it('renders tour name', () => {
    renderWithRouter(<TourCard tour={mockTour} />)
    expect(screen.getByText('Ancient Temples Tour')).toBeInTheDocument()
  })

  it('shows city', () => {
    renderWithRouter(<TourCard tour={mockTour} />)
    expect(screen.getByText('Kyoto')).toBeInTheDocument()
  })

  it('shows duration', () => {
    renderWithRouter(<TourCard tour={mockTour} />)
    expect(screen.getByText('3 days')).toBeInTheDocument()
  })

  it('shows max participants', () => {
    renderWithRouter(<TourCard tour={mockTour} />)
    expect(screen.getByText('Max 15')).toBeInTheDocument()
  })

  it('shows price per person', () => {
    renderWithRouter(<TourCard tour={mockTour} />)
    expect(screen.getByText('$250')).toBeInTheDocument()
  })

  it('shows category badge', () => {
    renderWithRouter(<TourCard tour={mockTour} />)
    expect(screen.getByText('cultural')).toBeInTheDocument()
  })

  it('shows rating', () => {
    renderWithRouter(<TourCard tour={mockTour} />)
    expect(screen.getByText('4.8')).toBeInTheDocument()
  })

  it('links to tour detail', () => {
    renderWithRouter(<TourCard tour={mockTour} />)
    const links = screen.getAllByRole('link')
    const tourLinks = links.filter(l => l.getAttribute('href')?.includes('/tours/tour-1'))
    expect(tourLinks.length).toBeGreaterThan(0)
  })
})
