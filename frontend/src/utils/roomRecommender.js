/**
 * Pure room-combination recommender. Given a hotel's `roomGroups` (the unified
 * shape produced by HotelDetailPage / LiteapiHotelDetailPage) plus the user's
 * search criteria, returns the cheapest combination of rooms that:
 *   - covers `guests` total adults
 *   - uses ≤ `rooms` total rooms
 *   - respects each group's per-type quantity cap
 *
 * Returns null when no valid combination exists (caller should hide the panel).
 *
 * The algorithm is a bounded DFS with cost pruning. The search space is small
 * (typical: ≤ 10 room types × ≤ 10 rooms), so an exhaustive search is fine.
 */

/** Pick a single representative rate plan for a group. Prefers refundable. */
function pickRate(group) {
  const rates = group.rates || []
  if (rates.length === 0) return null
  const refundable = rates.filter((r) => r.refundable && r.price > 0)
  const pool = refundable.length > 0 ? refundable : rates.filter((r) => r.price > 0)
  if (pool.length === 0) return null
  return pool.reduce((best, r) => (best == null || r.price < best.price ? r : best), null)
}

/** Distribute `guests` across `units` rooms of a given capacity, greedy. */
function distributePerUnit(guests, units, capacity) {
  const arr = []
  let remaining = guests
  for (let i = 0; i < units; i += 1) {
    const left = units - i
    const portion = Math.max(1, Math.min(capacity, Math.ceil(remaining / left)))
    const assigned = Math.min(portion, capacity, Math.max(0, remaining)) || 1
    arr.push(assigned)
    remaining -= assigned
  }
  return arr
}

/**
 * @param {Array} roomGroups
 * @param {{guests:number, rooms:number, nights?:number}} opts
 * @returns {object|null}
 */
export function recommendCombination(roomGroups, { guests, rooms, nights = 1 }) {
  if (!Array.isArray(roomGroups) || roomGroups.length === 0) return null
  if (!guests || guests < 1 || !rooms || rooms < 1) return null

  // Reduce each group to (group, chosen rate, capacity, maxQty, perRoomNight, perRoomTaxes).
  const candidates = []
  for (const g of roomGroups) {
    const rate = pickRate(g)
    if (!rate) continue
    const capacity = Math.max(1, rate.max_occupancy || g.max_guests || 1)
    const maxQty = Math.max(1, Math.min(g.total_quantity ?? rooms, rooms))
    candidates.push({
      group: g,
      rate,
      capacity,
      maxQty,
      perRoomNight: rate.price,
      perRoomTaxes: rate.taxes != null ? rate.taxes : 0,
    })
  }
  if (candidates.length === 0) return null

  // Sort by descending capacity then ascending price → helps pruning.
  candidates.sort((a, b) =>
    b.capacity - a.capacity || a.perRoomNight - b.perRoomNight
  )

  let best = null // { cost, picks: number[] (qty per candidate index) }

  function dfs(idx, remRooms, remGuests, runCost, picks) {
    if (best && runCost >= best.cost) return // prune
    if (remGuests <= 0 && remRooms >= 0) {
      if (!best || runCost < best.cost) {
        best = { cost: runCost, picks: picks.slice() }
      }
      return
    }
    if (idx >= candidates.length || remRooms <= 0) return

    // Capacity-based upper bound on this branch (best case = remaining slots × cheapest cost-per-guest).
    const c = candidates[idx]
    const maxHere = Math.min(c.maxQty, remRooms)
    for (let q = maxHere; q >= 0; q -= 1) {
      const newRem = remGuests - q * c.capacity
      const newRooms = remRooms - q
      const newCost = runCost + q * c.perRoomNight
      picks.push(q)
      dfs(idx + 1, newRooms, newRem, newCost, picks)
      picks.pop()
    }
  }

  dfs(0, rooms, guests, 0, [])

  if (!best) return null

  const items = []
  let totalGuests = 0
  let totalRooms = 0
  let totalPrice = 0
  let totalTaxes = 0
  let currency = candidates[0].rate.currency || 'USD'

  for (let i = 0; i < candidates.length; i += 1) {
    const qty = best.picks[i] || 0
    if (qty === 0) continue
    const c = candidates[i]
    const guestsRemaining = guests - totalGuests
    const slots = qty * c.capacity
    const guestsForThisType = Math.min(slots, guestsRemaining)
    const perUnitGuests = distributePerUnit(guestsForThisType, qty, c.capacity)

    items.push({
      group: c.group,
      rate: c.rate,
      quantity: qty,
      perUnitGuests,
    })
    totalGuests += perUnitGuests.reduce((s, n) => s + n, 0)
    totalRooms += qty
    totalPrice += qty * c.perRoomNight
    totalTaxes += qty * c.perRoomTaxes
    currency = c.rate.currency || currency
  }

  return {
    items,
    totalPrice,           // per night, all rooms
    totalTaxes,           // per night, all rooms
    totalGuests,
    totalRooms,
    currency,
    nights,
  }
}
