import { create } from 'zustand'

export const useSearchStore = create((set) => ({
  destination: '',
  checkIn: null,
  checkOut: null,
  // child_ages: integer ages for each child (0–17). length === children counter.
  guests: { adults: 2, children: 0, child_ages: [], rooms: 1 },
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
      guests: { adults: 2, children: 0, child_ages: [], rooms: 1 },
    }),
}))
