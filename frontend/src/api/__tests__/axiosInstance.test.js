import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock authStore: getState() trả về một object "sống" mà test có thể chỉnh.
const { mockState } = vi.hoisted(() => ({
  mockState: { accessToken: null, refreshToken: vi.fn() },
}))
vi.mock('@/store/authStore', () => ({ useAuthStore: { getState: () => mockState } }))

import api from '@/api/axiosInstance'

const reqHandler = api.interceptors.request.handlers[0].fulfilled
const errHandler = api.interceptors.response.handlers[0].rejected

function serializer(params) {
  const s = api.defaults.paramsSerializer
  const fn = typeof s === 'function' ? s : s.serialize
  return fn(params)
}

beforeEach(() => {
  mockState.accessToken = null
  mockState.refreshToken = vi.fn()
})

describe('request interceptor — Authorization header', () => {
  it('adds a Bearer token when one is present', () => {
    mockState.accessToken = 'tok123'
    const cfg = reqHandler({ headers: {} })
    expect(cfg.headers.Authorization).toBe('Bearer tok123')
  })

  it('omits Authorization when there is no token', () => {
    const cfg = reqHandler({ headers: {} })
    expect(cfg.headers.Authorization).toBeUndefined()
  })
})

describe('paramsSerializer — repeated array keys for FastAPI', () => {
  it('serializes arrays as repeated keys', () => {
    expect(serializer({ tags: [1, 2], city: 'Paris' })).toBe('tags=1&tags=2&city=Paris')
  })

  it('skips null / undefined / empty values', () => {
    expect(serializer({ a: '', b: null, c: undefined, d: 'x' })).toBe('d=x')
  })
})

describe('response interceptor — 401 refresh handling', () => {
  it('passes non-401 errors straight through', async () => {
    const err = { response: { status: 500 }, config: {} }
    await expect(errHandler(err)).rejects.toBe(err)
    expect(mockState.refreshToken).not.toHaveBeenCalled()
  })

  it('attempts a refresh on 401 and rejects when refresh fails', async () => {
    mockState.refreshToken.mockResolvedValueOnce(null)
    const err = { response: { status: 401 }, config: {} }
    await expect(errHandler(err)).rejects.toBe(err)
    expect(mockState.refreshToken).toHaveBeenCalledTimes(1)
  })

  it('does not refresh again for an already-retried request', async () => {
    const err = { response: { status: 401 }, config: { _retry: true } }
    await expect(errHandler(err)).rejects.toBe(err)
    expect(mockState.refreshToken).not.toHaveBeenCalled()
  })
})
