/**
 * Centralized mock factories for Vitest tests.
 * Import from here to keep test files lean.
 */
import { vi } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

// ── useAuth mock factory ──────────────────────────────────────────────────────
export const mockUseAuth = (overrides = {}) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  isStaff: false,
  isAdmin: false,
  isPartner: false,
  isSuperAdmin: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  refreshToken: vi.fn(),
  updateProfile: vi.fn(),
  ...overrides,
})

// ── i18n mock — t returns the key so assertions are readable ─────────────────
export const mockUseTranslation = (ns = 'common') => ({
  t: (key) => key,
  i18n: {
    changeLanguage: vi.fn().mockResolvedValue(undefined),
    language: 'en',
  },
})

// ── React Query wrapper ───────────────────────────────────────────────────────
function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

export function renderWithProviders(ui, { route = '/', queryClient } = {}) {
  const qc = queryClient || makeQueryClient()
  return render(
    createElement(MemoryRouter, { initialEntries: [route] },
      createElement(QueryClientProvider, { client: qc }, ui)
    )
  )
}

// ── Minimal authenticated user fixtures ──────────────────────────────────────
export const CUSTOMER_USER = {
  id: 'user-1',
  email: 'user@test.com',
  full_name: 'Test User',
  role: 'user',
  loyalty_points: 100,
}

export const PARTNER_USER = {
  id: 'partner-1',
  email: 'partner@test.com',
  full_name: 'Test Partner',
  role: 'partner',
  loyalty_points: 0,
}

export const ADMIN_USER = {
  id: 'admin-1',
  email: 'admin@test.com',
  full_name: 'Test Admin',
  role: 'admin',
  loyalty_points: 0,
}
