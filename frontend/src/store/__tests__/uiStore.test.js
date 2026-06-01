import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock phụ thuộc ngoài: API tỉ giá + singleton rateStore.
vi.mock('@/api/exchangeRateApi', () => ({ fetchUsdToVnd: vi.fn().mockResolvedValue(26000) }))
vi.mock('@/utils/rateStore', () => ({ setUsdToVnd: vi.fn(), setDisplayCurrency: vi.fn() }))

import { useUiStore } from '@/store/uiStore'
import { fetchUsdToVnd } from '@/api/exchangeRateApi'
import { setUsdToVnd, setDisplayCurrency } from '@/utils/rateStore'

beforeEach(() => {
  vi.clearAllMocks()
  useUiStore.setState({ currency: 'USD', locale: 'en', usdToVnd: 25000, rateLastFetchedAt: null })
})

describe('uiStore', () => {
  it('setCurrency updates the store and mirrors to the rateStore singleton', () => {
    useUiStore.getState().setCurrency('VND')
    expect(useUiStore.getState().currency).toBe('VND')
    expect(setDisplayCurrency).toHaveBeenCalledWith('VND')
  })

  it('setLocale updates the locale', () => {
    useUiStore.getState().setLocale('vi')
    expect(useUiStore.getState().locale).toBe('vi')
  })

  it('initExchangeRate fetches a fresh rate when the persisted rate is the default fallback', async () => {
    await useUiStore.getState().initExchangeRate()
    expect(fetchUsdToVnd).toHaveBeenCalledTimes(1)
    expect(setUsdToVnd).toHaveBeenCalledWith(26000)
    expect(useUiStore.getState().usdToVnd).toBe(26000)
  })

  it('initExchangeRate skips the fetch when the rate is fresh and non-default', async () => {
    useUiStore.setState({ usdToVnd: 26000, rateLastFetchedAt: Date.now() })
    await useUiStore.getState().initExchangeRate()
    expect(fetchUsdToVnd).not.toHaveBeenCalled()
  })
})
