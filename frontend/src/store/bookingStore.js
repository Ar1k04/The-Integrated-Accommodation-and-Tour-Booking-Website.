import { create } from 'zustand'

export const useBookingStore = create((set) => ({
  selectedRoom: null,
  selectedRoomGroup: null,
  selectedItems: null,
  hotel: null,
  checkIn: null,
  checkOut: null,
  adults: 2,
  childAges: [],
  rooms: 1,
  // Back-compat: `guests` is kept as a derived count so older components keep working.
  guests: 2,
  selectedTour: null,
  tourDate: null,
  selectedFlight: null,

  setBookingData: (data) => {
    const next = { ...data }
    if (next.adults != null || next.childAges != null) {
      const a = next.adults != null ? next.adults : 2
      const c = Array.isArray(next.childAges) ? next.childAges : []
      next.adults = a
      next.childAges = c
      next.guests = a + c.length
    }
    set(next)
  },
  clearBooking: () =>
    set({
      selectedRoom: null,
      selectedRoomGroup: null,
      selectedItems: null,
      hotel: null,
      checkIn: null,
      checkOut: null,
      adults: 2,
      childAges: [],
      guests: 2,
      rooms: 1,
      selectedTour: null,
      tourDate: null,
      selectedFlight: null,
    }),
}))

export const isLiteapiRoom = (room) => Boolean(room?.liteapi_rate_id)
