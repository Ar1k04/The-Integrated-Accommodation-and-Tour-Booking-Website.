import { describe, it, expect } from 'vitest'
import { isValidEmail, isStrongPassword, isValidPhone, validateBookingDates } from '@/utils/validators'

describe('isValidEmail', () => {
  it('accepts valid email', () => {
    expect(isValidEmail('test@example.com')).toBe(true)
    expect(isValidEmail('user+tag@domain.co.uk')).toBe(true)
  })

  it('rejects invalid email', () => {
    expect(isValidEmail('not-an-email')).toBe(false)
    expect(isValidEmail('')).toBe(false)
  })
})

describe('isStrongPassword', () => {
  it('accepts passwords 8+ chars', () => {
    expect(isStrongPassword('MyP@ssw0rd!')).toBe(true)
    expect(isStrongPassword('12345678')).toBe(true)
  })

  it('rejects short passwords', () => {
    expect(isStrongPassword('short')).toBe(false)
    expect(isStrongPassword('')).toBeFalsy()
  })
})

describe('isValidPhone', () => {
  it('accepts valid phone numbers', () => {
    expect(isValidPhone('+1234567890')).toBe(true)
    expect(isValidPhone('0901234567')).toBe(true)
  })

  it('treats empty/null as valid (optional field)', () => {
    expect(isValidPhone('')).toBe(true)
    expect(isValidPhone(null)).toBe(true)
    expect(isValidPhone(undefined)).toBe(true)
  })

  it('rejects invalid phones', () => {
    expect(isValidPhone('abc')).toBe(false)
    expect(isValidPhone('12')).toBe(false)
  })
})

describe('validateBookingDates', () => {
  it('returns null for valid future dates', () => {
    expect(validateBookingDates('2027-04-01', '2027-04-05')).toBeNull()
  })

  it('returns error when check-out before check-in', () => {
    const result = validateBookingDates('2027-04-05', '2027-04-01')
    expect(result).toBeTruthy()
    expect(result).toContain('after')
  })

  it('returns error for same dates', () => {
    const result = validateBookingDates('2027-04-01', '2027-04-01')
    expect(result).toBeTruthy()
  })

  it('returns error when dates are missing', () => {
    expect(validateBookingDates(null, null)).toBeTruthy()
    expect(validateBookingDates('2027-04-01', null)).toBeTruthy()
  })

  it('returns error for stays longer than 30 nights', () => {
    const result = validateBookingDates('2027-04-01', '2027-06-01')
    expect(result).toBeTruthy()
    expect(result).toContain('30')
  })
})
