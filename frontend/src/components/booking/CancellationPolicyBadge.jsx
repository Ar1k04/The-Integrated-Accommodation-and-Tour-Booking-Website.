import { CheckCircle2, AlertTriangle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { formatDate } from '@/utils/formatters'

// Renders the rate's cancellation policy as we received it from LiteAPI at
// prebook time. We show three states because the backend persists three signals:
//   - `refundable` flag (refundableTag !== "NRFN")
//   - `cancellation_deadline` (cancelPolicyInfos[0].cancelTime)
//   - and "now" relative to that deadline
//
// "Cancel within 1 hour" is NOT a thing on this platform — the LiteAPI rate is
// the only source of truth. If you see something hinting at it, that's wrong.
export default function CancellationPolicyBadge({ refundable, deadline, size = 'sm' }) {
  const { t } = useTranslation('profile')
  const sizing = size === 'lg'
    ? 'px-3 py-1.5 text-sm'
    : 'px-2 py-1 text-xs'

  // Non-refundable rate (NRFN) — explicit "no" from LiteAPI.
  if (refundable === false) {
    return (
      <span className={`inline-flex items-center gap-1 ${sizing} rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-medium`}>
        <AlertTriangle className="w-3 h-3" />
        {t('bookings.nonRefundable')}
      </span>
    )
  }

  // Refundable with a known deadline.
  if (deadline) {
    const d = new Date(deadline)
    const past = d.getTime() < Date.now()
    if (past) {
      return (
        <span className={`inline-flex items-center gap-1 ${sizing} rounded-full bg-gray-100 text-gray-600 border border-gray-200 font-medium`}>
          <AlertTriangle className="w-3 h-3" />
          {t('bookings.cancellationWindowClosed', { date: formatDate(deadline) })}
        </span>
      )
    }
    return (
      <span className={`inline-flex items-center gap-1 ${sizing} rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium`}>
        <CheckCircle2 className="w-3 h-3" />
        {t('bookings.freeCancellationUntil', { date: formatDate(deadline) })}
      </span>
    )
  }

  // Refundable but no deadline came back from the supplier — show a neutral
  // fallback so the user knows the rate isn't non-refundable, without
  // implying a window we can't promise.
  if (refundable === true) {
    return (
      <span className={`inline-flex items-center gap-1 ${sizing} rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 font-medium`}>
        <CheckCircle2 className="w-3 h-3" />
        {t('bookings.freeCancellation')}
      </span>
    )
  }

  return null
}
