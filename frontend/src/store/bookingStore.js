import { create } from 'zustand'

export const useBookingStore = create((set) => ({
  selectedRoom: null,
  hotel: null,
  checkIn: null,
  checkOut: null,
  guests: 1,
  selectedTour: null,
  tourDate: null,
  selectedFlight: null,

  setBookingData: (data) => set(data),
  clearBooking: () =>
    set({
      selectedRoom: null,
      hotel: null,
      checkIn: null,
      checkOut: null,
      guests: 1,
      selectedTour: null,
      tourDate: null,
      selectedFlight: null,
    }),
}))

export const isLiteapiRoom = (room) => Boolean(room?.liteapi_rate_id)
