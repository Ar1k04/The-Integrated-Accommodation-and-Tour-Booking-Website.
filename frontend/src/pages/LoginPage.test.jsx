import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import LoginPage from './LoginPage'
import { mockUseAuth, CUSTOMER_USER, PARTNER_USER } from '@/test/mocks'

// Mock dependencies
vi.mock('@/hooks/useAuth')
vi.mock('react-i18next', () => ({
  useTranslation: () => ({ t: (k) => k, i18n: { language: 'en' } }),
}))
vi.mock('react-helmet-async', () => ({
  Helmet: ({ children }) => children,
  HelmetProvider: ({ children }) => children,
}))
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import { useAuth } from '@/hooks/useAuth'

function setup(authOverrides = {}) {
  useAuth.mockReturnValue(mockUseAuth(authOverrides))
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<div>Home</div>} />
        <Route path="/admin" element={<div>Admin Dashboard</div>} />
        <Route path="/register" element={<div>Register</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('LoginPage', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders email and password fields', () => {
    setup()
    expect(screen.getByPlaceholderText('your@email.com')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Enter your password')).toBeInTheDocument()
  })

  it('renders submit button with translated key', () => {
    setup()
    expect(screen.getByRole('button', { name: 'login.signIn' })).toBeInTheDocument()
  })

  it('error message has role="alert" when error is present', async () => {
    const loginFn = vi.fn().mockRejectedValue({ response: { data: { detail: 'Invalid credentials' } } })
    setup({ login: loginFn })

    await userEvent.type(screen.getByPlaceholderText('your@email.com'), 'bad@test.com')
    await userEvent.type(screen.getByPlaceholderText('Enter your password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'login.signIn' }))

    await waitFor(() => {
      const alert = screen.getByRole('alert')
      expect(alert).toBeInTheDocument()
      expect(alert).toHaveTextContent('Invalid credentials')
    })
  })

  it('password toggle switches input type', async () => {
    setup()
    const passwordInput = screen.getByPlaceholderText('Enter your password')
    expect(passwordInput).toHaveAttribute('type', 'password')

    const toggle = screen.getByLabelText(/toggle password/i)
    await userEvent.click(toggle)
    expect(passwordInput).toHaveAttribute('type', 'text')

    await userEvent.click(toggle)
    expect(passwordInput).toHaveAttribute('type', 'password')
  })

  it('calls login with email and password on submit', async () => {
    const loginFn = vi.fn().mockResolvedValue(CUSTOMER_USER)
    setup({ login: loginFn })

    await userEvent.type(screen.getByPlaceholderText('your@email.com'), 'user@test.com')
    await userEvent.type(screen.getByPlaceholderText('Enter your password'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: 'login.signIn' }))

    await waitFor(() => {
      expect(loginFn).toHaveBeenCalledWith('user@test.com', 'secret')
    })
  })

  it('redirects staff user to /admin after successful login', async () => {
    const loginFn = vi.fn().mockResolvedValue(PARTNER_USER)
    setup({ login: loginFn })

    await userEvent.type(screen.getByPlaceholderText('your@email.com'), 'partner@test.com')
    await userEvent.type(screen.getByPlaceholderText('Enter your password'), 'pass')
    await userEvent.click(screen.getByRole('button', { name: 'login.signIn' }))

    await waitFor(() => {
      expect(screen.getByText('Admin Dashboard')).toBeInTheDocument()
    })
  })

  it('redirects to / after customer login', async () => {
    const loginFn = vi.fn().mockResolvedValue(CUSTOMER_USER)
    setup({ login: loginFn })

    await userEvent.type(screen.getByPlaceholderText('your@email.com'), 'user@test.com')
    await userEvent.type(screen.getByPlaceholderText('Enter your password'), 'pass')
    await userEvent.click(screen.getByRole('button', { name: 'login.signIn' }))

    await waitFor(() => {
      expect(screen.getByText('Home')).toBeInTheDocument()
    })
  })

  it('authenticated staff user is redirected away from login to /admin', () => {
    setup({ isAuthenticated: true, isStaff: true })
    expect(screen.getByText('Admin Dashboard')).toBeInTheDocument()
  })

  it('authenticated customer is redirected to /', () => {
    setup({ isAuthenticated: true, isStaff: false })
    expect(screen.getByText('Home')).toBeInTheDocument()
  })
})
