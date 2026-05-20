import { useRef, useEffect, useState } from 'react'
import { Users } from 'lucide-react'
import { useTranslation } from 'react-i18next'

/**
 * Compact dropdown to pick adults, children (with per-child age) and rooms.
 * Used on both hotel detail pages so LiteAPI rates and local rooms accept
 * the same occupancy shape.
 *
 * Props:
 *   adults        number
 *   childAges     number[]  (length === children count)
 *   rooms         number
 *   onChange({ adults, childAges, rooms })
 */
export default function OccupancySelector({ adults, childAges, rooms, onChange, maxAdults = 16, maxChildren = 8, maxRooms = 8 }) {
  const { t } = useTranslation('common')
  const [open, setOpen] = useState(false)
  const wrapRef = useRef(null)

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

  const summary = `${adults} ${t('common.adults', 'adults')}${
    childAges.length ? ` · ${childAges.length} ${t('common.children', 'children')}` : ''
  } · ${rooms} ${t('searchBar.rooms', 'rooms')}`

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
          {[
            { label: t('searchBar.adults', 'Adults'), key: 'adults', val: adults, min: 1, max: maxAdults, onChange: (v) => set({ adults: v }) },
            { label: t('searchBar.children', 'Children'), key: 'children', val: childAges.length, min: 0, max: maxChildren, onChange: setChildCount },
            { label: t('searchBar.rooms', 'Rooms'), key: 'rooms', val: rooms, min: 1, max: maxRooms, onChange: (v) => set({ rooms: v }) },
          ].map(({ label, key, val, min, max, onChange }) => (
            <div key={key} className="flex items-center justify-between py-2">
              <span className="text-sm">{label}</span>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => onChange(Math.max(min, val - 1))}
                  className="w-8 h-8 rounded-full border flex items-center justify-center hover:bg-gray-100 text-sm"
                >-</button>
                <span className="w-6 text-center text-sm font-medium">{val}</span>
                <button
                  onClick={() => onChange(Math.min(max, val + 1))}
                  className="w-8 h-8 rounded-full border flex items-center justify-center hover:bg-gray-100 text-sm"
                >+</button>
              </div>
            </div>
          ))}

          {childAges.length > 0 && (
            <div className="border-t pt-2 mt-1 space-y-2">
              <p className="text-xs text-gray-500">Age of each child at check-in</p>
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
