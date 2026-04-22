import { useMemo, useState } from 'react'
import {
  addDays,
  addMonths,
  endOfMonth,
  endOfWeek,
  format,
  isBefore,
  isSameDay,
  isWithinInterval,
  startOfDay,
  startOfMonth,
  startOfWeek,
} from 'date-fns'

export default function DateRangeCalendar({
  checkIn,
  checkOut,
  minDate = new Date(),
  onChange,
}) {
  const today = useMemo(() => startOfDay(new Date()), [])
  const min = useMemo(() => startOfDay(minDate || today), [minDate, today])

  const initialViewMonth = useMemo(() => {
    const d = checkIn || today
    return startOfMonth(d)
  }, [checkIn, today])

  const [viewMonth, setViewMonth] = useState(initialViewMonth)

  // Keep view month stable when checkIn changes from outside.
  // (We only change it on explicit navigation buttons.)

  const from = checkIn ? startOfDay(checkIn) : null
  const to = checkOut ? startOfDay(checkOut) : null

  const monthStart = startOfMonth(viewMonth)
  const monthEnd = endOfMonth(viewMonth)
  const gridStart = startOfWeek(monthStart, { weekStartsOn: 0 })
  const gridEnd = endOfWeek(monthEnd, { weekStartsOn: 0 })

  const days = useMemo(() => {
    const arr = []
    let d = gridStart
    while (d <= gridEnd) {
      arr.push(d)
      d = addDays(d, 1)
    }
    return arr
  }, [gridStart, gridEnd])

  const isDisabled = (day) => isBefore(startOfDay(day), min)

  const handleDayClick = (day) => {
    const clicked = startOfDay(day)

    if (isDisabled(clicked)) return

    // If range is complete, start a new selection.
    if (!from || to) {
      onChange(clicked, null)
      return
    }

    // If user clicks before the current start, reset start.
    if (isBefore(clicked, from)) {
      onChange(clicked, null)
      return
    }

    // Otherwise set end date.
    onChange(from, clicked)
  }

  const selectedClass = 'bg-primary text-white font-bold'
  const rangeStartClass = 'bg-primary text-white font-bold'
  const rangeEndClass = 'bg-primary text-white font-bold'
  const rangeMiddleClass = 'bg-primary/15 text-primary font-bold'

  const canGoPrev = startOfMonth(addMonths(viewMonth, -1)) >= startOfMonth(min)

  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
  const minYear = min.getFullYear()
  const maxYearNum = minYear + 10

  const years = useMemo(() => {
    const list = []
    for (let y = minYear; y <= maxYearNum; y++) list.push(y)
    return list
  }, [minYear, maxYearNum])

  return (
    <div className="w-[320px] bg-white border rounded-xl shadow-lg p-3">
      <div className="flex items-center justify-between mb-2">
        <button
          type="button"
          onClick={() => canGoPrev && setViewMonth((m) => startOfMonth(addMonths(m, -1)))}
          className="px-2 py-1 rounded-lg hover:bg-gray-100 disabled:opacity-30"
          disabled={!canGoPrev}
          aria-label="Previous month"
        >
          ‹
        </button>

        <div className="flex items-center gap-2">
          <select
            value={viewMonth.getMonth()}
            onChange={(e) => {
              const nextMonth = Number(e.target.value)
              setViewMonth(startOfMonth(new Date(viewMonth.getFullYear(), nextMonth, 1)))
            }}
            className="text-sm font-semibold text-gray-900 border border-gray-200 rounded-lg px-2 py-1"
            aria-label="Month"
          >
            {monthNames.map((name, idx) => (
              <option key={name} value={idx}>
                {name.slice(0, 3)}
              </option>
            ))}
          </select>
          <select
            value={viewMonth.getFullYear()}
            onChange={(e) => {
              const nextYear = Number(e.target.value)
              setViewMonth(startOfMonth(new Date(nextYear, viewMonth.getMonth(), 1)))
            }}
            className="text-sm font-semibold text-gray-900 border border-gray-200 rounded-lg px-2 py-1"
            aria-label="Year"
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </div>

        <button
          type="button"
          onClick={() => setViewMonth((m) => startOfMonth(addMonths(m, 1)))}
          className="px-2 py-1 rounded-lg hover:bg-gray-100"
          aria-label="Next month"
        >
          ›
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 mb-2 text-xs text-gray-400">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
          <div key={d} className="text-center">
            {d.slice(0, 2)}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {days.map((day) => {
          const inMonth = day.getMonth() === monthStart.getMonth()
          const disabled = isDisabled(day)

          const isFrom = from && isSameDay(day, from)
          const isTo = to && isSameDay(day, to)
          const isMiddle = from && to && !isFrom && !isTo && isWithinInterval(day, { start: from, end: to })

          let className = 'h-9 flex items-center justify-center rounded-lg text-sm'
          if (!inMonth) className += ' text-gray-300'
          else className += disabled ? ' text-gray-300 cursor-not-allowed' : ' hover:bg-gray-100 cursor-pointer'

          if (isMiddle) className += ` ${rangeMiddleClass}`
          else if (isFrom && isTo) className += ` ${selectedClass}`
          else if (isFrom) className += ` ${rangeStartClass}`
          else if (isTo) className += ` ${rangeEndClass}`

          return (
            <button
              key={day.toISOString()}
              type="button"
              onClick={() => handleDayClick(day)}
              disabled={disabled}
              className={className}
              aria-label={format(day, 'yyyy-MM-dd')}
            >
              {format(day, 'd')}
            </button>
          )
        })}
      </div>
    </div>
  )
}

