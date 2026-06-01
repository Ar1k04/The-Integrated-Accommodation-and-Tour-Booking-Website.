import { describe, it, expect, beforeEach } from 'vitest'
import { useBookingStore, isLiteapiRoom } from '@/store/bookingStore'

const initialState = useBookingStore.getState()
beforeEach(() => useBookingStore.setState(initialState, true))

describe('bookingStore', () => {
  it('has sensible defaults', () => {
    const s = useBookingStore.getState()
    expect(s.adults).toBe(2)
    expect(s.guests).toBe(2)
    expect(s.childAges).toEqual([])
    expect(s.rooms).toBe(1)
    expect(s.hotel).toBeNull()
  })

  it('setBookingData derives guests = adults + childAges.length', () => {
    useBookingStore.getState().setBookingData({ adults: 3, childAges: [5, 7] })
    const s = useBookingStore.getState()
    expect(s.adults).toBe(3)
    expect(s.childAges).toEqual([5, 7])
    expect(s.guests).toBe(5)
  })

  it('setBookingData defaults adults to 2 when only childAges provided', () => {
    useBookingStore.getState().setBookingData({ childAges: [4] })
    const s = useBookingStore.getState()
    expect(s.adults).toBe(2)
    expect(s.guests).toBe(3)
  })

  it('setBookingData passes through non-occupancy fields without touching guests', () => {
    useBookingStore.getState().setBookingData({ hotel: { id: 'h1' } })
    const s = useBookingStore.getState()
    expect(s.hotel).toEqual({ id: 'h1' })
    expect(s.guests).toBe(2) // không đổi vì không truyền adults/childAges
  })

  it('clearBooking resets everything to defaults', () => {
    const s = useBookingStore.getState()
    s.setBookingData({ adults: 4, childAges: [1], hotel: { id: 'x' } })
    s.clearBooking()
    const after = useBookingStore.getState()
    expect(after.adults).toBe(2)
    expect(after.guests).toBe(2)
    expect(after.hotel).toBeNull()
    expect(after.selectedRoom).toBeNull()
  })
})

describe('isLiteapiRoom', () => {
  it('is true when the room carries a liteapi_rate_id', () => {
    expect(isLiteapiRoom({ liteapi_rate_id: 'rate-1' })).toBe(true)
  })

  it('is false for local rooms or nullish input', () => {
    expect(isLiteapiRoom({ id: 'r1' })).toBe(false)
    expect(isLiteapiRoom(null)).toBe(false)
    expect(isLiteapiRoom(undefined)).toBe(false)
  })
})
