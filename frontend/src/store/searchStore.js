import { create } from 'zustand'

export const useSearchStore = create((set) => ({
  destination: '',
  checkIn: null,
  checkOut: null,
  guests: { adults: 2, children: 0, rooms: 1 },
  searchType: 'hotels',

  setDestination: (destination) => set({ destination }),
  setDates: (checkIn, checkOut) => set({ checkIn, checkOut }),
  setGuests: (guests) => set({ guests }),
  setSearchType: (searchType) => set({ searchType }),
  resetSearch: () =>
    set({
      destination: '',
      checkIn: null,
      checkOut: null,
      guests: { adults: 2, children: 0, rooms: 1 },
    }),
}))
