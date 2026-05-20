/**
 * Mirror of backend `liteapi_service.get_rates` occupancy split so the
 * frontend recommender and UI describe the same per-room composition that
 * the backend actually sends to LiteAPI.
 *
 * Algorithm:
 *   - Adults: evenly divided across rooms; the remainder lands in the first
 *     N rooms (so a 5-adults / 2-rooms split is [3, 2]).
 *   - Children: assigned by index, round-robin (`children_per_room[idx % rooms]`)
 *     — children[0] → room 0, children[1] → room 1, children[2] → room 0, …
 *
 * Keep this in lockstep with `backend/app/services/liteapi_service.py::get_rates`.
 *
 * @param {object} opts
 * @param {number} opts.adults     Number of adults (≥1).
 * @param {number[]} [opts.childAges=[]] Ages of each child (0–17).
 * @param {number} opts.rooms      Number of rooms to split into (≥1).
 * @returns {Array<{adults:number, childAges:number[]}>} length === rooms.
 */
export function distributeOccupancy({ adults, childAges = [], rooms }) {
  const r = Math.max(1, Math.floor(rooms || 1))
  // Mirror backend invariant: at least one adult per room.
  const adultsTotal = Math.max(r, Math.floor(adults || 0))

  const baseAdults = Math.floor(adultsTotal / r)
  const extraAdults = adultsTotal - baseAdults * r

  const slots = []
  for (let i = 0; i < r; i += 1) {
    slots.push({
      adults: baseAdults + (i < extraAdults ? 1 : 0),
      childAges: [],
    })
  }
  const ages = Array.isArray(childAges) ? childAges : []
  for (let idx = 0; idx < ages.length; idx += 1) {
    slots[idx % r].childAges.push(Math.floor(ages[idx]))
  }
  return slots
}
