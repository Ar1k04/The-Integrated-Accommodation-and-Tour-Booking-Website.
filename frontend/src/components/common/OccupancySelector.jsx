import { useRef, useEffect, useState } from 'react'
import { Users } from 'lucide-react'
import { useTranslation } from 'react-i18next'

/**
 * Compact dropdown to pick adults, children (with per-child age) and optionally
 * rooms. Shared across the hotel, tour and flight detail pages so all three
 * surfaces collect the same occupancy shape.
 *
 * Props:
 *   adults       number (required, ≥1)
 *   childAges    number[] (length === children count; ages 0–17)
 *   rooms        number (used + shown when mode='hotel'; ignored otherwise)
 *   onChange     ({ adults, childAges, rooms }) callback
 *   mode         'hotel' | 'tour' | 'flight' — adjusts copy + visibility:
 *                hotel  → "Guests"  + rooms counter
 *                tour   → "Travelers" + no rooms
 *                flight → "Passengers" + no rooms
 *   hideRooms    boolean override (forces no rooms regardless of mode)
 */
export default function OccupancySelector({
  adults,
  childAges,
  rooms = 1,
  onChange,
  maxAdults = 16,
  maxChildren = 8,
  maxRooms = 8,
  mode = 'hotel',
  hideRooms,
}) {
  const { t } = useTranslation('common')
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)

  const showRooms = hideRooms != null ? !hideRooms : mode === 'hotel'

  useEffect(() => {
    if (!open) return
    const onDown = (e) => {
      const el = wrapRef.current
      if (!el || el.contains(e.target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  const set = (patch) => onChange({ adults, childAges, rooms, ...patch })

  const setChildCount = (next) => {
    next = Math.max(0, Math.min(maxChildren, next))
    if (next > childAges.length) {
      const filled = [...childAges, ...Array(next - childAges.length).fill(8)]
      set({ childAges: filled })
    } else {
      set({ childAges: childAges.slice(0, next) })
    }
  }

  const setChildAge = (idx, age) => {
    const next = [...childAges]
    next[idx] = age
    set({ childAges: next })
  }

  // Copy adjusts to the booking type so labels read natural in each context.
  const peopleLabel = mode === 'flight'
    ? t('common.passengers', 'passengers')
    : mode === 'tour'
      ? t('common.travelers', 'travelers')
      : t('common.guests', 'guests')

  const totalPeople = adults + childAges.length
  const summary = `${totalPeople} ${peopleLabel}` +
    (childAges.length ? ` · ${childAges.length} ${t('common.children', 'children')}` : '') +
    (showRooms ? ` · ${rooms} ${t('searchBar.rooms', 'rooms')}` : '')

  const rows = [
    {
      label: t('searchBar.adults', 'Adults'),
      key: 'adults',
      val: adults,
      min: 1,
      max: maxAdults,
      onChange: (v) => set({ adults: v }),
    },
    {
      label: t('searchBar.children', 'Children'),
      key: 'children',
      val: childAges.length,
      min: 0,
      max: maxChildren,
      onChange: setChildCount,
    },
  ]
  if (showRooms) {
    rows.push({
      label: t('searchBar.rooms', 'Rooms'),
      key: 'rooms',
      val: rooms,
      min: 1,
      max: maxRooms,
      onChange: (v) => set({ rooms: v }),
    })
  }

  return (
    <div className="relative" ref={wrapRef}>
      <button
        type="button"
        onClick={() => setOpen((s) => !s)}
        className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-3 text-sm w-full"
      >
        <Users className="w-5 h-5 text-gray-400 shrink-0" />
        <span className="truncate">{summary}</span>
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg z-50 p-4 w-72">
          {rows.map(({ label, key, val, min, max, onChange: onRowChange }) => (
            <div key={key} className="flex items-center justify-between py-2">
              <span className="text-sm">{label}</span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => onRowChange(Math.max(min, val - 1))}
                  className="w-8 h-8 rounded-full border flex items-center justify-center hover:bg-gray-100 text-sm"
                >-</button>
                <span className="w-6 text-center text-sm font-medium">{val}</span>
                <button
                  onClick={() => onRowChange(Math.min(max, val + 1))}
                  className="w-8 h-8 rounded-full border flex items-center justify-center hover:bg-gray-100 text-sm"
                >+</button>
              </div>
            </div>
          ))}

          {childAges.length > 0 && (
            <div className="border-t pt-2 mt-1 space-y-2">
              <p className="text-xs text-gray-500">Age of each child at travel time</p>
              {childAges.map((age, idx) => (
                <div key={idx} className="flex items-center justify-between">
                  <span className="text-sm">Child {idx + 1}</span>
                  <select
                    value={age}
                    onChange={(e) => setChildAge(idx, parseInt(e.target.value, 10))}
                    className="border rounded-md text-sm px-2 py-1"
                  >
                    {Array.from({ length: 18 }, (_, i) => i).map((a) => (
                      <option key={a} value={a}>
                        {a === 0 ? '< 1' : `${a}`}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          )}

          <button
            onClick={() => setOpen(false)}
            className="w-full mt-3 bg-primary text-white rounded-lg py-2 text-sm font-medium"
          >
            {t('common.done', 'Done')}
          </button>
        </div>
      )}
    </div>
  )
}
