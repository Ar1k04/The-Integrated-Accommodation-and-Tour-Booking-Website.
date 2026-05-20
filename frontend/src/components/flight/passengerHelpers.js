import { format } from 'date-fns'

export const emptyPassenger = () => ({
  first_name: '',
  last_name: '',
  email: '',
  gender: 'M',
  born_on: format(new Date(1990, 0, 1), 'yyyy-MM-dd'),
  title: 'mr',
  phone_number: '',
})

export function isPassengerComplete(p) {
  return !!(p?.first_name && p?.last_name && p?.email && p?.born_on)
}

export function arePassengersComplete(passengers, count) {
  if (!Array.isArray(passengers) || passengers.length < count) return false
  return passengers.slice(0, count).every(isPassengerComplete)
}
