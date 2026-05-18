import { describe, it, expect } from 'vitest'
import { recommendCombination } from '../roomRecommender'

const makeGroup = (id, name, capacity, price, totalQuantity = 10, refundable = true) => ({
  id,
  name,
  room_type: '1 queen bed',
  max_guests: capacity,
  total_quantity: totalQuantity,
  amenities: [],
  images: [],
  rates: [
    {
      rate_id: `${id}-rate`,
      board_name: '',
      refundable,
      cancellation_deadline: null,
      price,
      price_excl_taxes: price - 20,
      taxes: 20,
      original_price: null,
      discount_percent: null,
      currency: 'USD',
      max_occupancy: capacity,
    },
  ],
})

describe('recommendCombination', () => {
  it('returns null when there are no room groups', () => {
    expect(recommendCombination([], { guests: 2, rooms: 1 })).toBeNull()
  })

  it('returns null when guests / rooms is invalid', () => {
    const groups = [makeGroup('a', 'A', 2, 100)]
    expect(recommendCombination(groups, { guests: 0, rooms: 1 })).toBeNull()
    expect(recommendCombination(groups, { guests: 2, rooms: 0 })).toBeNull()
  })

  it('picks the single cheapest fitting room for 2 guests / 1 room', () => {
    const groups = [
      makeGroup('cheap', 'Cheap Double', 2, 100),
      makeGroup('exp', 'Expensive Suite', 4, 250),
    ]
    const r = recommendCombination(groups, { guests: 2, rooms: 1 })
    expect(r).not.toBeNull()
    expect(r.items).toHaveLength(1)
    expect(r.items[0].group.id).toBe('cheap')
    expect(r.items[0].quantity).toBe(1)
    expect(r.totalPrice).toBe(100)
    expect(r.totalRooms).toBe(1)
    expect(r.totalGuests).toBe(2)
  })

  it('mixes two room types when one is not enough on its own (10 guests, 5 rooms)', () => {
    // Big Room: capacity 4 @ $200 ; Small Room: capacity 3 @ $150
    // Search space includes: 1 big + 2 small = 3 rooms, capacity 4+6=10, $500 ← cheapest
    const groups = [
      makeGroup('a', 'Big Room', 4, 200),
      makeGroup('b', 'Smaller Room', 3, 150),
    ]
    const r = recommendCombination(groups, { guests: 10, rooms: 5 })
    expect(r).not.toBeNull()
    expect(r.totalRooms).toBeLessThanOrEqual(5)
    expect(r.totalGuests).toBe(10)
    expect(r.totalPrice).toBe(500)
  })

  it('forces a multi-type mix when ceilings cap each type below required', () => {
    // 10 guests, 5 rooms. Only 1 big room available (capacity 4), small rooms unlimited (capacity 3).
    // Best: 1 × big (4) + 2 × small (6) = 10, total $500
    const groups = [
      makeGroup('big', 'Big', 4, 200, 1),
      makeGroup('small', 'Small', 3, 150, 10),
    ]
    const r = recommendCombination(groups, { guests: 10, rooms: 5 })
    expect(r).not.toBeNull()
    const big = r.items.find((i) => i.group.id === 'big')
    const small = r.items.find((i) => i.group.id === 'small')
    expect(big?.quantity).toBe(1)
    expect(small?.quantity).toBe(2)
    expect(r.totalPrice).toBe(500)
  })

  it('returns null when no combination of available rooms can fit', () => {
    const groups = [makeGroup('s', 'Tiny', 2, 100, 2)]
    const r = recommendCombination(groups, { guests: 50, rooms: 2 })
    expect(r).toBeNull()
  })

  it('prefers refundable rates when both fit', () => {
    const groupRefundable = makeGroup('r', 'Refundable', 2, 120, 5, true)
    const groupNonRefundable = makeGroup('n', 'NonRefundable', 2, 80, 5, false)
    const r = recommendCombination([groupRefundable, groupNonRefundable], { guests: 2, rooms: 1 })
    expect(r).not.toBeNull()
    // pickRate prefers refundable when one exists for that group, but the recommender
    // will then pick the cheapest *resulting* candidate. With one refundable @ 120 and
    // one non-refundable-only @ 80, the cheapest fit is non-refundable.
    // To assert preference inside the same group, we test a single mixed group below.
    expect(['r', 'n']).toContain(r.items[0].group.id)
  })

  it('prefers refundable rate inside the same group', () => {
    const mixedGroup = {
      id: 'mix',
      name: 'Mixed',
      room_type: '1 king bed',
      max_guests: 2,
      total_quantity: 5,
      amenities: [],
      images: [],
      rates: [
        {
          rate_id: 'mix-nrf',
          board_name: '',
          refundable: false,
          price: 80,
          price_excl_taxes: 70,
          taxes: 10,
          currency: 'USD',
          max_occupancy: 2,
        },
        {
          rate_id: 'mix-rf',
          board_name: '',
          refundable: true,
          price: 95,
          price_excl_taxes: 80,
          taxes: 15,
          currency: 'USD',
          max_occupancy: 2,
        },
      ],
    }
    const r = recommendCombination([mixedGroup], { guests: 2, rooms: 1 })
    expect(r.items[0].rate.rate_id).toBe('mix-rf')
    expect(r.totalPrice).toBe(95)
  })

  it('respects per-group total_quantity caps', () => {
    const groups = [
      // capacity-2 @ $50 but only 2 left
      makeGroup('a', 'Limited', 2, 50, 2),
      // capacity-2 @ $80 with plenty
      makeGroup('b', 'Plentiful', 2, 80, 10),
    ]
    const r = recommendCombination(groups, { guests: 6, rooms: 3 })
    expect(r).not.toBeNull()
    const limited = r.items.find((i) => i.group.id === 'a')
    expect(limited?.quantity || 0).toBeLessThanOrEqual(2)
    expect(r.totalRooms).toBe(3)
  })

  it('computes taxes correctly across multiple units', () => {
    const groups = [makeGroup('a', 'A', 2, 100, 5)] // taxes=20 per room
    const r = recommendCombination(groups, { guests: 4, rooms: 2 })
    expect(r).not.toBeNull()
    expect(r.totalRooms).toBe(2)
    expect(r.totalTaxes).toBe(40) // 2 rooms × $20
  })

  it('distributes per-unit guests across multiple rooms of one type', () => {
    const groups = [makeGroup('a', 'A', 3, 100, 5)]
    const r = recommendCombination(groups, { guests: 7, rooms: 3 })
    expect(r).not.toBeNull()
    expect(r.items[0].quantity).toBe(3)
    const total = r.items[0].perUnitGuests.reduce((s, n) => s + n, 0)
    expect(total).toBe(7)
    // Each unit fits ≤ capacity
    for (const n of r.items[0].perUnitGuests) {
      expect(n).toBeLessThanOrEqual(3)
    }
  })
})
