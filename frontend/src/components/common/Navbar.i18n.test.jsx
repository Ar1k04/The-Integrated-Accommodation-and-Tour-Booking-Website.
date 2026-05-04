import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { mockUseAuth, CUSTOMER_USER } from '@/test/mocks'

vi.mock('@/hooks/useAuth')
// Stable shared spy so both the mock and test assertions reference the same fn
const changeLanguageMock = vi.fn().mockResolvedValue(undefined)

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key, fallback) => fallback || key,
    i18n: { changeLanguage: changeLanguageMock, language: 'en' },
  }),
}))
vi.mock('@/api/authApi', () => ({
  authApi: { updateMe: vi.fn().mockResolvedValue({}) },
}))
vi.mock('@/utils/constants', () => ({
  CURRENCIES: [
    { code: 'USD', symbol: '$', name: 'US Dollar' },
    { code: 'VND', symbol: '₫', name: 'Vietnamese Dong' },
  ],
}))

// Zustand store — use the real store but reset between tests
vi.mock('@/store/uiStore', async () => {
  const { create } = await import('zustand')
  const store = create((set) => ({
    currency: 'USD',
    locale: 'en',
    setCurrency: (currency) => set({ currency }),
    setLocale: (locale) => set({ locale }),
  }))
  return { useUiStore: store }
})

import { useAuth } from '@/hooks/useAuth'
import { authApi } from '@/api/authApi'
import { useUiStore } from '@/store/uiStore'
import Navbar from './Navbar'

function renderNavbar(authOverrides = {}) {
  useAuth.mockReturnValue(mockUseAuth(authOverrides))
  return render(
    <MemoryRouter>
      <Navbar />
    </MemoryRouter>
  )
}

describe('Navbar dropdowns — aria-expanded', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset Zustand store
    useUiStore.setState({ currency: 'USD', locale: 'en' })
  })

  it('currency button has aria-expanded=false initially', () => {
    renderNavbar()
    const btn = screen.getByRole('button', { name: /currency/i })
    expect(btn).toHaveAttribute('aria-expanded', 'false')
  })

  it('currency button aria-expanded becomes true when open', async () => {
    renderNavbar()
    const btn = screen.getByRole('button', { name: /currency/i })
    await userEvent.click(btn)
    expect(btn).toHaveAttribute('aria-expanded', 'true')
  })

  it('language button has aria-expanded=false initially', () => {
    renderNavbar()
    const btn = screen.getByRole('button', { name: /language/i })
    expect(btn).toHaveAttribute('aria-expanded', 'false')
  })

  it('language button aria-expanded becomes true when open', async () => {
    renderNavbar()
    const btn = screen.getByRole('button', { name: /language/i })
    await userEvent.click(btn)
    expect(btn).toHaveAttribute('aria-expanded', 'true')
  })

  it('user menu button has aria-expanded when authenticated', async () => {
    renderNavbar({ isAuthenticated: true, user: CUSTOMER_USER })
    const btn = screen.getByRole('button', { name: /user menu/i })
    expect(btn).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(btn)
    expect(btn).toHaveAttribute('aria-expanded', 'true')
  })
})

describe('Navbar — currency/language persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useUiStore.setState({ currency: 'USD', locale: 'en' })
  })

  it('selecting VND updates the Zustand store', async () => {
    renderNavbar()
    await userEvent.click(screen.getByRole('button', { name: /currency/i }))
    await userEvent.click(screen.getByText(/VND/))
    expect(useUiStore.getState().currency).toBe('VND')
  })

  it('currency change does NOT call authApi.updateMe when logged out', async () => {
    renderNavbar({ isAuthenticated: false })
    await userEvent.click(screen.getByRole('button', { name: /currency/i }))
    await userEvent.click(screen.getByText(/VND/))
    expect(authApi.updateMe).not.toHaveBeenCalled()
  })

  it('currency change calls authApi.updateMe when logged in', async () => {
    renderNavbar({ isAuthenticated: true, user: CUSTOMER_USER })
    await userEvent.click(screen.getByRole('button', { name: /currency/i }))
    await userEvent.click(screen.getByText(/VND/))
    expect(authApi.updateMe).toHaveBeenCalledWith(expect.objectContaining({ preferred_currency: 'VND' }))
  })

  it('selecting VI locale calls i18n.changeLanguage', async () => {
    renderNavbar()
    await userEvent.click(screen.getByRole('button', { name: /language/i }))
    await userEvent.click(screen.getByText('Tiếng Việt'))
    expect(changeLanguageMock).toHaveBeenCalledWith('vi')
  })

  it('locale change calls authApi.updateMe when logged in', async () => {
    renderNavbar({ isAuthenticated: true, user: CUSTOMER_USER })
    await userEvent.click(screen.getByRole('button', { name: /language/i }))
    await userEvent.click(screen.getByText('Tiếng Việt'))
    expect(authApi.updateMe).toHaveBeenCalledWith(expect.objectContaining({ preferred_locale: 'vi' }))
  })
})
