import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'

export const useBookingStore = create(persist((set) => ({
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
}), {
  // FE-04: survive a page reload mid-checkout (sessionStorage, not local —
  // the selection should not outlive the browser tab). clearBooking() still
  // resets everything after a successful booking.
  name: 'booking-flow',
  storage: createJSONStorage(() => sessionStorage),
  partialize: (s) => ({
    selectedRoom: s.selectedRoom,
    selectedRoomGroup: s.selectedRoomGroup,
    selectedItems: s.selectedItems,
    hotel: s.hotel,
    checkIn: s.checkIn,
    checkOut: s.checkOut,
    adults: s.adults,
    childAges: s.childAges,
    rooms: s.rooms,
    guests: s.guests,
    selectedTour: s.selectedTour,
    tourDate: s.tourDate,
    selectedFlight: s.selectedFlight,
  }),
}))

export const isLiteapiRoom = (room) => Boolean(room?.liteapi_rate_id)
