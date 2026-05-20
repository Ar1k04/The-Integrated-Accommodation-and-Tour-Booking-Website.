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

describe('recommendCombination — legacy (guests-only) API', () => {
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
    // No room expansion can rescue 50 guests with only 2 capacity-2 rooms.
    const r = recommendCombination(groups, { guests: 50, rooms: 2 })
    expect(r).toBeNull()
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
      makeGroup('a', 'Limited', 2, 50, 2),
      makeGroup('b', 'Plentiful', 2, 80, 10),
    ]
    const r = recommendCombination(groups, { guests: 6, rooms: 3 })
    expect(r).not.toBeNull()
    const limited = r.items.find((i) => i.group.id === 'a')
    expect(limited?.quantity || 0).toBeLessThanOrEqual(2)
    expect(r.totalRooms).toBe(3)
  })

  it('computes taxes correctly across multiple units', () => {
    const groups = [makeGroup('a', 'A', 2, 100, 5)]
    const r = recommendCombination(groups, { guests: 4, rooms: 2 })
    expect(r).not.toBeNull()
    expect(r.totalRooms).toBe(2)
    expect(r.totalTaxes).toBe(40)
  })

  it('exposes perUnitGuests across multiple rooms of one type (back-compat)', () => {
    const groups = [makeGroup('a', 'A', 3, 100, 5)]
    const r = recommendCombination(groups, { guests: 7, rooms: 3 })
    expect(r).not.toBeNull()
    expect(r.items[0].quantity).toBe(3)
    const total = r.items[0].perUnitGuests.reduce((s, n) => s + n, 0)
    expect(total).toBe(7)
    for (const n of r.items[0].perUnitGuests) {
      expect(n).toBeLessThanOrEqual(3)
    }
  })
})

describe('recommendCombination — children-aware', () => {
  it('puts 2A + 1C in one capacity-3 room and returns slot composition', () => {
    const groups = [makeGroup('std', 'Standard', 3, 120)]
    const r = recommendCombination(groups, { adults: 2, childAges: [8], rooms: 1 })
    expect(r).not.toBeNull()
    expect(r.totalRooms).toBe(1)
    expect(r.items[0].perUnitSlots).toEqual([{ adults: 2, childAges: [8] }])
    expect(r.totalPrice).toBe(120)
    expect(r.expandedFromRooms).toBeNull()
  })

  it('auto-expands rooms when capacity overflows the user request', () => {
    // capacity-2 rooms, user asks for 1 room but party is 2A + 3C → must split
    const groups = [makeGroup('std', 'Standard', 2, 100)]
    const r = recommendCombination(groups, {
      adults: 2,
      childAges: [6, 8, 10],
      rooms: 1,
      maxRoomExpansion: 3,
    })
    expect(r).not.toBeNull()
    expect(r.totalRooms).toBeGreaterThanOrEqual(2)
    expect(r.expandedFromRooms).toBe(1)
    // All 5 people placed across slots
    const placed = r.items[0].perUnitSlots.reduce(
      (s, u) => s + u.adults + u.childAges.length,
      0,
    )
    expect(placed).toBe(5)
  })

  it('filters out adults-only rate plans when the party has children', () => {
    const group = {
      id: 'g',
      name: 'Mixed',
      room_type: '1 king',
      max_guests: 2,
      total_quantity: 5,
      amenities: [],
      images: [],
      rates: [
        // Adults-only rate (supplier marks child_count=0) — should be skipped.
        {
          rate_id: 'adults-only',
          refundable: true,
          price: 80,
          taxes: 10,
          currency: 'USD',
          max_occupancy: 2,
          adult_count: 2,
          child_count: 0,
        },
        // Family-friendly rate.
        {
          rate_id: 'family',
          refundable: true,
          price: 100,
          taxes: 12,
          currency: 'USD',
          max_occupancy: 2,
          adult_count: 1,
          child_count: 1,
        },
      ],
    }
    const r = recommendCombination([group], { adults: 1, childAges: [6], rooms: 1 })
    expect(r).not.toBeNull()
    expect(r.items[0].rate.rate_id).toBe('family')
  })

  it('respects per-rate adult_count and child_count when allocating slots', () => {
    // Rate caps at 2 adults + 1 child even though max_occupancy is 4
    const group = {
      id: 'g',
      name: 'Family Suite',
      room_type: '2 queen beds',
      max_guests: 4,
      total_quantity: 5,
      amenities: [],
      images: [],
      rates: [
        {
          rate_id: 'fam',
          refundable: true,
          price: 200,
          taxes: 20,
          currency: 'USD',
          max_occupancy: 4,
          adult_count: 2,
          child_count: 1,
        },
      ],
    }
    // 1 family-suite holds 2A + 1C; party is 4A + 2C → need ≥ 2 rooms
    const r = recommendCombination([group], {
      adults: 4,
      childAges: [6, 9],
      rooms: 1,
      maxRoomExpansion: 3,
    })
    expect(r).not.toBeNull()
    expect(r.totalRooms).toBeGreaterThanOrEqual(2)
    for (const slot of r.items[0].perUnitSlots) {
      expect(slot.adults).toBeLessThanOrEqual(2)
      expect(slot.childAges.length).toBeLessThanOrEqual(1)
    }
  })

  it('considers multiple rate plans within a room type and picks the cheapest fit', () => {
    // Same room type with two refundable rates (e.g. Room Only vs Breakfast)
    const group = {
      id: 'std',
      name: 'Standard',
      room_type: '1 queen',
      max_guests: 2,
      total_quantity: 5,
      amenities: [],
      images: [],
      rates: [
        { rate_id: 'std-bb', refundable: true, price: 130, taxes: 15, currency: 'USD', max_occupancy: 2 },
        { rate_id: 'std-ro', refundable: true, price: 100, taxes: 12, currency: 'USD', max_occupancy: 2 },
      ],
    }
    const r = recommendCombination([group], { adults: 2, childAges: [], rooms: 1 })
    expect(r.items[0].rate.rate_id).toBe('std-ro')
  })
})
