import { format, parseISO } from 'date-fns'
import {
  Users,
  Bed,
  CheckCircle,
  XCircle,
  Wifi,
  Tv,
  Bath,
  Coffee,
  Snowflake,
} from 'lucide-react'

/** Repeat person-silhouette icons up to count. */
export function GuestIcons({ count }) {
  const full = Math.min(count, 6)
  return (
    <span className="inline-flex items-center gap-0.5">
      {Array.from({ length: full }).map((_, i) => (
        <Users key={i} className="w-4 h-4 text-gray-700" />
      ))}
      {count > 6 && <span className="text-xs text-gray-500 ml-0.5">×{count}</span>}
    </span>
  )
}

export const AMENITY_ICONS = {
  wifi: Wifi,
  free_wifi: Wifi,
  air_conditioning: Snowflake,
  tv: Tv,
  flat_screen_tv: Tv,
  minibar: Coffee,
  room_service: Coffee,
  ensuite_bathroom: Bath,
  private_bathroom: Bath,
}

/** Bed-type label with a small icon. */
export function BedInfo({ roomType }) {
  if (!roomType) return null
  return (
    <span className="inline-flex items-center gap-1.5 text-sm text-gray-600">
      <Bed className="w-4 h-4 text-gray-400" />
      {roomType}
    </span>
  )
}

/** Render a board name as a friendly i18n string. */
export function BoardBadge({ boardName, t }) {
  const lower = (boardName || '').toLowerCase()
  if (lower.includes('breakfast')) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-green-700 font-medium">
        <Coffee className="w-3.5 h-3.5" /> {t('hotels:detail.breakfastIncluded')}
      </span>
    )
  }
  if (boardName) return <span className="text-xs text-gray-600">{boardName}</span>
  return <span className="text-xs text-gray-500">{t('hotels:detail.roomOnly')}</span>
}

/** Cancellation policy line — green if refundable, orange otherwise. */
export function CancellationLine({ rate, t }) {
  if (!rate.refundable) {
    return (
      <div className="flex items-start gap-1.5">
        <XCircle className="w-3.5 h-3.5 text-orange-500 shrink-0 mt-0.5" />
        <span className="text-xs text-orange-700">{t('hotels:detail.nonRefundableShort')}</span>
      </div>
    )
  }
  let label = t('hotels:detail.freeCancellationAnytime')
  if (rate.cancellation_deadline) {
    try {
      const d = format(parseISO(rate.cancellation_deadline), 'd MMM yyyy')
      label = t('hotels:detail.freeCancellationBefore', { date: d })
    } catch {
      // keep default
    }
  }
  return (
    <div className="flex items-start gap-1.5">
      <CheckCircle className="w-3.5 h-3.5 text-green-600 shrink-0 mt-0.5" />
      <span className="text-xs text-green-700 font-medium">{label}</span>
    </div>
  )
}
