import { describe, it, expect, beforeEach } from 'vitest'
import { useSearchStore } from '@/store/searchStore'

// Lưu state gốc (gồm cả actions) để reset trước mỗi test.
const initialState = useSearchStore.getState()
beforeEach(() => useSearchStore.setState(initialState, true))

describe('searchStore', () => {
  it('has sensible defaults', () => {
    const s = useSearchStore.getState()
    expect(s.destination).toBe('')
    expect(s.searchType).toBe('hotels')
    expect(s.guests).toEqual({ adults: 2, children: 0, child_ages: [], rooms: 1 })
  })

  it('setDestination updates destination', () => {
    useSearchStore.getState().setDestination('Paris')
    expect(useSearchStore.getState().destination).toBe('Paris')
  })

  it('setDates updates check-in / check-out', () => {
    useSearchStore.getState().setDates('2026-06-01', '2026-06-05')
    const s = useSearchStore.getState()
    expect(s.checkIn).toBe('2026-06-01')
    expect(s.checkOut).toBe('2026-06-05')
  })

  it('setGuests replaces the occupancy object', () => {
    useSearchStore.getState().setGuests({ adults: 3, children: 1, child_ages: [5], rooms: 2 })
    expect(useSearchStore.getState().guests.adults).toBe(3)
    expect(useSearchStore.getState().guests.child_ages).toEqual([5])
  })

  it('setSearchType switches the tab', () => {
    useSearchStore.getState().setSearchType('tours')
    expect(useSearchStore.getState().searchType).toBe('tours')
  })

  it('resetSearch clears fields but keeps the chosen searchType', () => {
    const s = useSearchStore.getState()
    s.setDestination('Tokyo')
    s.setSearchType('flights')
    s.resetSearch()
    const after = useSearchStore.getState()
    expect(after.destination).toBe('')
    expect(after.guests).toEqual({ adults: 2, children: 0, child_ages: [], rooms: 1 })
    expect(after.searchType).toBe('flights') // resetSearch không đụng searchType
  })
})
