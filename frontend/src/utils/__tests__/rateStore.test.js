import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import {
  getUsdToVnd,
  setUsdToVnd,
  getDisplayCurrency,
  setDisplayCurrency,
} from '@/utils/rateStore'

// rateStore là singleton mutable; lưu & khôi phục để không rò rỉ giữa các test.
let origRate
let origCurrency

beforeEach(() => {
  origRate = getUsdToVnd()
  origCurrency = getDisplayCurrency()
})

afterEach(() => {
  setUsdToVnd(origRate)
  setDisplayCurrency(origCurrency)
})

describe('rateStore', () => {
  it('defaults to 25000 VND/USD and USD display currency', () => {
    expect(getUsdToVnd()).toBe(25000)
    expect(getDisplayCurrency()).toBe('USD')
  })

  it('updates and reads back the USD→VND rate', () => {
    setUsdToVnd(26500)
    expect(getUsdToVnd()).toBe(26500)
  })

  it('updates and reads back the display currency', () => {
    setDisplayCurrency('VND')
    expect(getDisplayCurrency()).toBe('VND')
  })

  it('keeps rate and currency independent', () => {
    setUsdToVnd(30000)
    setDisplayCurrency('VND')
    expect(getUsdToVnd()).toBe(30000)
    expect(getDisplayCurrency()).toBe('VND')
  })
})
