export function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

export function isStrongPassword(password) {
  return password && password.length >= 8
}

export function isValidPhone(phone) {
  return !phone || /^\+?[\d\s-]{7,15}$/.test(phone)
}

export function validateBookingDates(checkIn, checkOut) {
  if (!checkIn || !checkOut) return 'Both check-in and check-out dates are required'
  const now = new Date()
  now.setHours(0, 0, 0, 0)
  if (new Date(checkIn) < now) return 'Check-in date cannot be in the past'
  if (new Date(checkOut) <= new Date(checkIn)) return 'Check-out must be after check-in'
  const nights = Math.ceil((new Date(checkOut) - new Date(checkIn)) / 86400000)
  if (nights > 30) return 'Maximum stay is 30 nights'
  return null
}
