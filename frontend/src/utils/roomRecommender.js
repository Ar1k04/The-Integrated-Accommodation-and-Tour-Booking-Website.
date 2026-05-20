/**
 * Room-combination recommender. Given a hotel's `roomGroups` plus the user's
 * search criteria, returns the cheapest combination of rooms that:
 *   - covers `adults` + `childAges.length` people (respecting per-rate
 *     capacity AND optional supplier `adult_count` / `child_count` ceilings)
 *   - uses ≤ `rooms + maxRoomExpansion` rooms (auto-suggests an extra room
 *     when the requested count cannot fit everyone)
 *   - prefers refundable rates within each room type
 *   - skips rate plans that supplier explicitly marks as "adults only"
 *     (`child_count === 0`) when the party includes children
 *
 * Returns null when no valid combination exists.
 *
 * Algorithm:
 *   1. Build candidates: one per (group, rate) after refundable + adults-only
 *      filtering.
 *   2. For each `roomsToUse ∈ [userRooms .. userRooms + maxRoomExpansion]`,
 *      DFS quantities per candidate (cost-pruned) to find the cheapest
 *      combination whose total capacity covers everyone.
 *   3. Allocate adults + childAges into the picked rooms, packing larger
 *      capacities first (so 4-adult families fill the king suite before the
 *      twin), and round-robining children by age order.
 */
import { distributeOccupancy } from './distributeOccupancy'

/** Build the flat candidate list for one room group (one per rate plan). */
function candidatesForGroup(group, hasChildren) {
  const rates = group.rates || []
  if (rates.length === 0) return []

  // Hide rates the supplier explicitly says are adults-only when the party
  // includes children. When `child_count` is null/undefined LiteAPI did not
  // expose it — trust the request-side filter and keep the rate.
  const occupancyOk = rates.filter((r) => {
    if (!hasChildren) return r.price > 0
    if (r.child_count === 0) return false
    return r.price > 0
  })
  if (occupancyOk.length === 0) return []

  // Refundable preference within a group: when any refundable rate survives
  // the previous filter, drop non-refundable ones (matches Booking.com's
  // "Recommended" panel UX).
  const refundable = occupancyOk.filter((r) => r.refundable)
  const pool = refundable.length > 0 ? refundable : occupancyOk

  return pool.map((rate) => ({
    group,
    rate,
    capacity: Math.max(1, rate.max_occupancy || group.max_guests || 1),
    perRoomNight: rate.price,
    perRoomTaxes: rate.taxes != null ? rate.taxes : 0,
  }))
}

/**
 * Pack adults + childAges into the picked rooms. Returns null if any room
 * would exceed its per-rate limits.
 *
 * Strategy: sort picked rooms by descending capacity, place adults greedily
 * into the largest rooms first (so big-bed suites get the adults), then
 * distribute children by age order across rooms that still have headroom.
 */
function allocateSlots(items, adults, childAges) {
  const flatSlots = []
  items.forEach((item, itemIdx) => {
    for (let u = 0; u < item.quantity; u += 1) {
      const cap = item.rate.max_occupancy || item.group.max_guests || 1
      flatSlots.push({
        itemIdx,
        unitIdx: u,
        capacity: cap,
        adultCap: item.rate.adult_count != null ? item.rate.adult_count : cap,
        childCap: item.rate.child_count != null ? item.rate.child_count : cap,
        adults: 0,
        childAges: [],
      })
    }
  })
  if (flatSlots.length === 0) return null

  flatSlots.sort((a, b) => b.capacity - a.capacity)

  // Adults first, larger rooms first.
  let aLeft = adults
  for (const slot of flatSlots) {
    if (aLeft <= 0) break
    const take = Math.min(slot.adultCap, slot.capacity, aLeft)
    slot.adults = take
    aLeft -= take
  }
  if (aLeft > 0) return null

  // Children round-robin in age order, skipping slots already at capacity.
  for (const age of childAges) {
    let placed = false
    for (const slot of flatSlots) {
      if (slot.adults + slot.childAges.length >= slot.capacity) continue
      if (slot.childAges.length >= slot.childCap) continue
      slot.childAges.push(age)
      placed = true
      break
    }
    if (!placed) return null
  }

  // Re-group back to item order so the caller can attach perUnitSlots[].
  flatSlots.sort((a, b) => a.itemIdx - b.itemIdx || a.unitIdx - b.unitIdx)
  const perUnitSlotsByItem = items.map(() => [])
  for (const slot of flatSlots) {
    perUnitSlotsByItem[slot.itemIdx].push({
      adults: slot.adults,
      childAges: slot.childAges.slice(),
    })
  }
  return perUnitSlotsByItem
}

/**
 * Inner DFS — find the cheapest set of (candidate, quantity) tuples that
 * together cover `totalGuests` people using ≤ `roomsToUse` rooms, respecting
 * each group's `total_quantity` cap across rate-plan candidates that share
 * the same group.
 *
 * Returns { cost, picks: number[] } aligned with the candidates array, or null.
 */
function dfsBestForRoomCount(candidates, roomsToUse, totalGuests) {
  let best = null
  const groupUsage = new Map()

  function dfs(idx, remRooms, remGuests, runCost, picks) {
    if (best && runCost >= best.cost) return
    if (remGuests <= 0 && remRooms >= 0) {
      if (!best || runCost < best.cost) {
        best = { cost: runCost, picks: picks.slice() }
      }
      return
    }
    if (idx >= candidates.length || remRooms <= 0) return

    const c = candidates[idx]
    const used = groupUsage.get(c.group.id) || 0
    const groupCap = c.group.total_quantity != null ? c.group.total_quantity : roomsToUse
    const maxHere = Math.min(groupCap - used, remRooms)

    for (let q = maxHere; q >= 0; q -= 1) {
      const newCost = runCost + q * c.perRoomNight
      const newRem = remGuests - q * c.capacity
      const newRooms = remRooms - q
      picks.push(q)
      groupUsage.set(c.group.id, used + q)
      dfs(idx + 1, newRooms, newRem, newCost, picks)
      groupUsage.set(c.group.id, used)
      picks.pop()
    }
  }
  dfs(0, roomsToUse, totalGuests, 0, [])
  return best
}

export function recommendCombination(roomGroups, opts) {
  if (!Array.isArray(roomGroups) || roomGroups.length === 0) return null
  const {
    rooms,
    nights = 1,
    maxRoomExpansion = 3,
  } = opts || {}

  // Back-compat: callers can pass either `{adults, childAges}` (new) or
  // `{guests}` (old, treats everyone as adult).
  const adults = opts.adults != null ? opts.adults : opts.guests
  const childAges = Array.isArray(opts.childAges) ? opts.childAges.slice() : []
  if (!adults || adults < 1 || !rooms || rooms < 1) return null

  const totalGuests = adults + childAges.length
  const hasChildren = childAges.length > 0

  // Build flat candidates (group × surviving rates).
  const candidates = []
  for (const g of roomGroups) {
    candidates.push(...candidatesForGroup(g, hasChildren))
  }
  if (candidates.length === 0) return null

  // Sort by descending capacity then ascending price — same heuristic the old
  // recommender used; helps cost-pruning find a good upper bound quickly.
  candidates.sort((a, b) =>
    b.capacity - a.capacity || a.perRoomNight - b.perRoomNight
  )

  // Try the user's room count first, then auto-expand when overflow happens.
  let overall = null
  for (let extra = 0; extra <= maxRoomExpansion; extra += 1) {
    const roomsToUse = rooms + extra
    const picked = dfsBestForRoomCount(candidates, roomsToUse, totalGuests)
    if (!picked) continue

    // Materialise items, then allocate per-unit slots.
    const items = []
    for (let i = 0; i < candidates.length; i += 1) {
      const qty = picked.picks[i] || 0
      if (qty === 0) continue
      items.push({
        group: candidates[i].group,
        rate: candidates[i].rate,
        quantity: qty,
      })
    }
    const slotsByItem = allocateSlots(items, adults, childAges)
    if (!slotsByItem) continue // per-rate capacity broke — try one more room

    items.forEach((item, idx) => {
      item.perUnitSlots = slotsByItem[idx]
      item.perUnitGuests = slotsByItem[idx].map((s) => s.adults + s.childAges.length)
    })

    const totalRooms = items.reduce((s, it) => s + it.quantity, 0)
    const cost = picked.cost
    // Prefer cheaper; tie-break: fewer rooms used.
    if (
      !overall ||
      cost < overall.cost ||
      (cost === overall.cost && totalRooms < overall.totalRooms)
    ) {
      let totalPrice = 0
      let totalTaxes = 0
      let currency = items[0]?.rate.currency || 'USD'
      for (const item of items) {
        totalPrice += item.quantity * item.rate.price
        totalTaxes += item.quantity * (item.rate.taxes || 0)
        currency = item.rate.currency || currency
      }
      overall = {
        cost,
        items,
        totalPrice,
        totalTaxes,
        totalRooms,
        totalGuests,
        currency,
        nights,
        expandedFromRooms: extra > 0 ? rooms : null,
        roomsUsed: totalRooms,
      }
    }
  }

  if (!overall) return null
  const { cost: _, roomsUsed: __, ...result } = overall
  return result
}

// Exported for tests + future reuse from the booking payload builder.
export { distributeOccupancy }
