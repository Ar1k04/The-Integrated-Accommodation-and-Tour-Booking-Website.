import { create } from 'zustand'

export const useBookingStore = create((set) => ({
  selectedRoom: null,
  hotel: null,
  checkIn: null,
  checkOut: null,
  guests: 1,
  promoCode: '',
  discount: 0,

  setBookingData: (data) => set(data),
  applyPromo: (code, discount) => set({ promoCode: code, discount }),
  clearBooking: () =>
    set({
      selectedRoom: null,
      hotel: null,
      checkIn: null,
      checkOut: null,
      guests: 1,
      promoCode: '',
      discount: 0,
    }),
}))
