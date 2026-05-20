import { describe, it, expect } from 'vitest'
import { distributeOccupancy } from '../distributeOccupancy'

describe('distributeOccupancy', () => {
  it('puts everyone in one room when rooms=1', () => {
    expect(distributeOccupancy({ adults: 2, childAges: [8], rooms: 1 })).toEqual([
      { adults: 2, childAges: [8] },
    ])
  })

  it('matches backend round-robin: 5A + [5,8,12] across 2 rooms', () => {
    // Mirrors backend tests/test_liteapi.py::test_get_rates_forwards_child_ages_round_robin
    // Backend output for adults=5, children=[5,8,12], rooms=2:
    //   adults_per_room = [3, 2]
    //   children_per_room = [[5, 12], [8]]
    expect(distributeOccupancy({ adults: 5, childAges: [5, 8, 12], rooms: 2 })).toEqual([
      { adults: 3, childAges: [5, 12] },
      { adults: 2, childAges: [8] },
    ])
  })

  it('matches backend: 4 adults + [11,8,4] across 2 rooms', () => {
    // Mirrors backend test test_get_rates_forwards_child_ages_round_robin
    expect(distributeOccupancy({ adults: 4, childAges: [11, 8, 4], rooms: 2 })).toEqual([
      { adults: 2, childAges: [11, 4] },
      { adults: 2, childAges: [8] },
    ])
  })

  it('empty childAges behaves like adults-only', () => {
    expect(distributeOccupancy({ adults: 7, childAges: [], rooms: 3 })).toEqual([
      { adults: 3, childAges: [] },
      { adults: 2, childAges: [] },
      { adults: 2, childAges: [] },
    ])
  })

  it('clamps adults to at least one per room', () => {
    // 1 adult + 2 rooms is illegal upstream, but the helper must never produce
    // a room with 0 adults — it bumps the total up.
    const slots = distributeOccupancy({ adults: 1, childAges: [], rooms: 2 })
    expect(slots).toHaveLength(2)
    expect(slots.every((s) => s.adults >= 1)).toBe(true)
  })

  it('handles missing rooms / adults gracefully', () => {
    expect(distributeOccupancy({ adults: 0, childAges: [], rooms: 0 })).toEqual([
      { adults: 1, childAges: [] },
    ])
  })

  it('floors fractional adults and ages', () => {
    expect(distributeOccupancy({ adults: 2.7, childAges: [5.9], rooms: 1 })).toEqual([
      { adults: 2, childAges: [5] },
    ])
  })
})
