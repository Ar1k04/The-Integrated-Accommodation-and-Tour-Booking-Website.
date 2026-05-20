import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
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
import { ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react'
import { useUiStore } from '@/store/uiStore'
import { formatCalendarPrice, getCalendarPriceEstimate } from '@/utils/calendarPrice'

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const WEEKDAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function getMonthGridDays(month) {
  const monthStart = startOfMonth(month)
  const monthEnd = endOfMonth(month)
  const gridStart = startOfWeek(monthStart, { weekStartsOn: 1 })
  const gridEnd = endOfWeek(monthEnd, { weekStartsOn: 1 })

  const days = []
  let d = gridStart
  while (d <= gridEnd) {
    days.push(d)
    d = addDays(d, 1)
  }
  return days
}

function getMonthRangeLabel(startMonth) {
  const nextMonth = addMonths(startMonth, 1)
  const left = format(startMonth, 'MMM yyyy')
  const right = format(nextMonth, startMonth.getFullYear() === nextMonth.getFullYear() ? 'MMM' : 'MMM yyyy')
  return `${left} - ${right}`
}

export default function DateRangeCalendar({
  checkIn,
  checkOut,
  minDate = new Date(),
  onChange,
  priceBaseUsd,
  priceLoading = false,
}) {
  const { t } = useTranslation('hotels')
  const currency = useUiStore((s) => s.currency)
  const usdToVnd = useUiStore((s) => s.usdToVnd)
  const today = useMemo(() => startOfDay(new Date()), [])
  const min = useMemo(() => startOfDay(minDate || today), [minDate, today])

  const initialViewMonth = useMemo(() => {
    const d = checkIn || today
    return startOfMonth(d)
  }, [checkIn, today])

  const [viewMonth, setViewMonth] = useState(initialViewMonth)
  const [showMonthPicker, setShowMonthPicker] = useState(false)
  const [pickerYear, setPickerYear] = useState(initialViewMonth.getFullYear())

  // Keep view month stable when checkIn changes from outside.
  // (We only change it on explicit navigation buttons.)

  const from = checkIn ? startOfDay(checkIn) : null
  const to = checkOut ? startOfDay(checkOut) : null

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
  const showPriceHints = Number.isFinite(Number(priceBaseUsd)) && Number(priceBaseUsd) > 0

  const minYear = min.getFullYear()
  const maxYearNum = minYear + 10
  const visibleMonths = useMemo(() => [viewMonth, addMonths(viewMonth, 1)], [viewMonth])
  const monthRangeLabel = getMonthRangeLabel(viewMonth)
  const canPickerGoPrev = pickerYear > minYear
  const canPickerGoNext = pickerYear < maxYearNum

  const handleMonthPick = (monthIndex) => {
    const next = startOfMonth(new Date(pickerYear, monthIndex, 1))
    if (next < startOfMonth(min)) return
    setViewMonth(next)
    setShowMonthPicker(false)
  }

  return (
    <div className="w-[720px] max-w-[calc(100vw-2rem)] bg-white border border-gray-200 rounded-2xl shadow-xl p-4">
      <div className="relative mb-4 flex items-center justify-between">
        <button
          type="button"
          onClick={() => canGoPrev && setViewMonth((m) => startOfMonth(addMonths(m, -1)))}
          className="h-9 w-9 rounded-full border border-gray-200 text-gray-700 flex items-center justify-center hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
          disabled={!canGoPrev}
          aria-label="Previous month"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>

        <div className="relative">
          <button
            type="button"
            onClick={() => {
              setPickerYear(viewMonth.getFullYear())
              setShowMonthPicker((s) => !s)
            }}
            className="h-9 min-w-[190px] rounded-full border border-gray-200 bg-gray-50 px-4 text-sm font-semibold text-gray-900 flex items-center justify-center gap-2 hover:bg-gray-100"
            aria-label="Choose month and year"
            aria-expanded={showMonthPicker}
          >
            {monthRangeLabel}
            <ChevronDown className={`h-4 w-4 text-gray-500 transition-transform ${showMonthPicker ? 'rotate-180' : ''}`} />
          </button>

          {showMonthPicker && (
            <div className="absolute left-1/2 top-11 z-20 w-[300px] -translate-x-1/2 rounded-2xl border border-gray-200 bg-white p-3 shadow-xl">
              <div className="flex items-center justify-between border-b border-gray-100 pb-3">
                <button
                  type="button"
                  onClick={() => canPickerGoPrev && setPickerYear((y) => y - 1)}
                  disabled={!canPickerGoPrev}
                  className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
                  aria-label="Previous year"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-sm font-bold text-gray-900">{pickerYear}</span>
                <button
                  type="button"
                  onClick={() => canPickerGoNext && setPickerYear((y) => y + 1)}
                  disabled={!canPickerGoNext}
                  className="h-8 w-8 rounded-full flex items-center justify-center hover:bg-gray-50 disabled:opacity-30 disabled:cursor-not-allowed"
                  aria-label="Next year"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2">
                {MONTH_NAMES.map((name, idx) => {
                  const monthDate = startOfMonth(new Date(pickerYear, idx, 1))
                  const disabled = monthDate < startOfMonth(min)
                  const selected = viewMonth.getFullYear() === pickerYear && viewMonth.getMonth() === idx
                  return (
                    <button
                      key={name}
                      type="button"
                      onClick={() => handleMonthPick(idx)}
                      disabled={disabled}
                      className={`h-9 rounded-xl text-sm font-semibold transition-colors ${
                        selected
                          ? 'bg-primary text-white'
                          : disabled
                            ? 'text-gray-300 cursor-not-allowed'
                            : 'text-gray-700 hover:bg-blue-50 hover:text-primary'
                      }`}
                    >
                      {name.slice(0, 3)}
                    </button>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={() => setViewMonth((m) => startOfMonth(addMonths(m, 1)))}
          className="h-9 w-9 rounded-full border border-gray-200 text-gray-700 flex items-center justify-center hover:bg-gray-50"
          aria-label="Next month"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {visibleMonths.map((month) => {
          const monthStart = startOfMonth(month)
          const days = getMonthGridDays(month)

          return (
            <div key={month.toISOString()} className="min-w-0">
              <h3 className="mb-3 text-center text-base font-bold text-gray-900">
                {format(monthStart, 'MMMM yyyy')}
              </h3>

              <div className="grid grid-cols-7 gap-1 mb-2 text-xs font-semibold text-gray-400">
                {WEEKDAY_LABELS.map((d) => (
                  <div key={d} className="text-center">
                    {d.slice(0, 2)}
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-7 gap-1">
                {days.map((day) => {
                  const inMonth = day.getMonth() === monthStart.getMonth()
                  if (!inMonth) {
                    return <div key={day.toISOString()} className={showPriceHints ? 'h-12' : 'h-9'} aria-hidden="true" />
                  }

                  const disabled = isDisabled(day)
                  const isFrom = from && isSameDay(day, from)
                  const isTo = to && isSameDay(day, to)
                  const isMiddle = from && to && !isFrom && !isTo && isWithinInterval(day, { start: from, end: to })
                  const dailyPrice = showPriceHints && !disabled ? getCalendarPriceEstimate(priceBaseUsd, day) : null
                  const priceLabel = dailyPrice ? formatCalendarPrice(dailyPrice, currency, usdToVnd) : null
                  const priceToneClass = isFrom || isTo
                    ? 'text-white/90'
                    : isMiddle
                      ? 'text-primary/80'
                      : dailyPrice <= Number(priceBaseUsd)
                        ? 'text-emerald-600'
                        : 'text-slate-500'

                  let className = `${showPriceHints ? 'h-12 flex-col gap-0.5 py-1' : 'h-9'} flex items-center justify-center rounded-xl text-sm transition-colors`
                  className += disabled ? ' text-gray-300 cursor-not-allowed' : ' hover:bg-gray-100 cursor-pointer'

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
                      aria-label={priceLabel
                        ? `${format(day, 'yyyy-MM-dd')}, ${t('search.calendarPriceAria', { price: priceLabel, defaultValue: `estimated ${priceLabel}` })}`
                        : format(day, 'yyyy-MM-dd')}
                      title={priceLabel ? `${format(day, 'yyyy-MM-dd')} · ${priceLabel}` : undefined}
                    >
                      <span className="leading-none">{format(day, 'd')}</span>
                      {priceLabel && (
                        <span className={`text-[10px] font-semibold leading-none ${priceToneClass}`}>
                          {priceLabel}
                        </span>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>

      {showPriceHints ? (
        <p className="mt-3 px-1 text-xs font-semibold leading-snug text-slate-500">
          {t('search.calendarPriceCaption', 'Estimated price per night for a 3-star stay in the searched destination')}
        </p>
      ) : priceLoading ? (
        <p className="mt-3 px-1 text-xs font-medium text-slate-400">
          {t('search.calendarPriceLoading', 'Loading 3-star price estimates...')}
        </p>
      ) : null}
    </div>
  )
}
