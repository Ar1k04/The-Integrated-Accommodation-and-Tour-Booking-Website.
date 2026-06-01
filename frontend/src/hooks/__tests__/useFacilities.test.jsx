import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createElement } from 'react'

vi.mock('@/api/facilitiesApi', () => ({ facilitiesApi: { list: vi.fn() } }))

import { useFacilities } from '@/hooks/useFacilities'
import { facilitiesApi } from '@/api/facilitiesApi'

function wrapper({ children }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return createElement(QueryClientProvider, { client: qc }, children)
}

beforeEach(() => vi.clearAllMocks())

describe('useFacilities', () => {
  it('filters out facilities whose id is not in the local mapping', async () => {
    facilitiesApi.list.mockResolvedValue({
      data: [
        { id: 107, name: 'WiFi' },
        { id: 301, name: 'Pool' },
        { id: 99999, name: 'Unmapped' },
      ],
    })
    const { result } = renderHook(() => useFacilities(), { wrapper })
    await waitFor(() => expect(result.current.isLoading).toBe(false))
    const ids = result.current.facilities.map((f) => f.id)
    expect(ids).not.toContain(99999) // id không map bị loại
    expect(result.current.isError).toBe(false)
  })

  it('exposes isError when the request fails', async () => {
    facilitiesApi.list.mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useFacilities(), { wrapper })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.facilities).toEqual([])
  })
})
