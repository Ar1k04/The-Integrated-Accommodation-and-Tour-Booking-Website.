import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ProtectedRoute from './ProtectedRoute'
import { mockUseAuth, CUSTOMER_USER, PARTNER_USER, ADMIN_USER } from '@/test/mocks'

vi.mock('@/hooks/useAuth')
import { useAuth } from '@/hooks/useAuth'

function setup(authOverrides, routeProps = {}, initialPath = '/protected') {
  useAuth.mockReturnValue(mockUseAuth(authOverrides))
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/protected" element={
          <ProtectedRoute {...routeProps}>
            <div>Protected Content</div>
          </ProtectedRoute>
        } />
        <Route path="/login" element={<div>Login Page</div>} />
        <Route path="/" element={<div>Home Page</div>} />
        <Route path="/admin" element={<div>Admin Page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('shows spinner while auth is loading', () => {
    setup({ isLoading: true })
    expect(document.querySelector('.animate-spin')).toBeInTheDocument()
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('redirects unauthenticated user to /login', () => {
    setup({ isAuthenticated: false, isLoading: false })
    expect(screen.getByText('Login Page')).toBeInTheDocument()
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('renders children for authenticated user with no special requirements', () => {
    setup({ isAuthenticated: true, user: CUSTOMER_USER })
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('requireStaff: blocks customer user and redirects to /', () => {
    setup(
      { isAuthenticated: true, user: CUSTOMER_USER, isStaff: false },
      { requireStaff: true }
    )
    expect(screen.getByText('Home Page')).toBeInTheDocument()
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('requireStaff: allows partner user', () => {
    setup(
      { isAuthenticated: true, user: PARTNER_USER, isStaff: true, isAdmin: false },
      { requireStaff: true }
    )
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('requireAdmin: blocks partner user and redirects to /admin', () => {
    setup(
      { isAuthenticated: true, user: PARTNER_USER, isStaff: true, isAdmin: false },
      { requireAdmin: true }
    )
    expect(screen.getByText('Admin Page')).toBeInTheDocument()
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('requireAdmin: allows admin user', () => {
    setup(
      { isAuthenticated: true, user: ADMIN_USER, isStaff: true, isAdmin: true },
      { requireAdmin: true }
    )
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })

  it('userOnly: redirects staff user to /admin', () => {
    setup(
      { isAuthenticated: true, user: PARTNER_USER, isStaff: true },
      { userOnly: true }
    )
    expect(screen.getByText('Admin Page')).toBeInTheDocument()
    expect(screen.queryByText('Protected Content')).not.toBeInTheDocument()
  })

  it('userOnly: allows regular customer', () => {
    setup(
      { isAuthenticated: true, user: CUSTOMER_USER, isStaff: false },
      { userOnly: true }
    )
    expect(screen.getByText('Protected Content')).toBeInTheDocument()
  })
})
