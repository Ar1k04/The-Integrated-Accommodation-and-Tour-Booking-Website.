import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  Calendar, Users, ChevronDown, MapPin, Compass,
  ExternalLink, FileText, Hash, Download,
} from 'lucide-react'
import { toast } from 'sonner'
import BookingStatusBadge from '@/components/common/BookingStatusBadge'
import { toursApi } from '@/api/toursApi'
import { formatDate } from '@/utils/formatters'
import { downloadBookingPdf } from '@/utils/bookingPdf'

// Mirrors hotelHref in HotelBookingCard — picks the correct detail-page route
// (local tour vs Viator product) so the "View tour" CTA always lands on a real
// page. Returns null when we can't resolve either, and the CTA is hidden.
function tourHref(item) {
  if (item.tour?.id) return `/tours/${item.tour.id}`
  const viatorCode = item.tour?.viator_product_code || item.viator_product_code
  if (viatorCode) return `/tours/viator/${viatorCode}`
  return null
}

export default function TourBookingCard({ booking, fmt, canCancel, onCancel }) {
  const { t } = useTranslation('profile')
  const [expanded, setExpanded] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const tourItem = booking.items?.find((i) => i.item_type === 'tour')

  // Same pattern as HotelBookingCard: persisted URL wins; old Viator bookings
  // without one trigger a single cached fetch of the product detail so the
  // card eventually shows the right thumbnail. Derived with optional chaining
  // and the hook called unconditionally so the early `return null` below never
  // changes the number of hooks (Rules of Hooks).
  const persistedImage = tourItem?.tour?.image_url
  const viatorCode = tourItem?.tour?.viator_product_code || tourItem?.viator_product_code
  const { data: fetchedImage } = useQuery({
    queryKey: ['booking-card-tour-image', viatorCode],
    enabled: Boolean(!persistedImage && viatorCode),
    staleTime: 24 * 60 * 60 * 1000,
    retry: false,
    queryFn: () => toursApi.getViator(viatorCode).then((r) => r.data?.images?.[0] || null),
  })

  if (!tourItem) return null

  const handleDownloadPdf = async (e) => {
    e.stopPropagation()
    if (downloading) return
    setDownloading(true)
    try {
      await downloadBookingPdf(booking, fmt)
    } catch (err) {
      console.error('PDF download failed', err)
      toast.error(t('bookings.pdfFailed', { defaultValue: 'Could not generate PDF' }))
    } finally {
      setDownloading(false)
    }
  }

  const href = tourHref(tourItem)
  const tourName = tourItem.tour?.name || tourItem.tour_name || t('bookings.tour')

  const image = persistedImage || fetchedImage

  return (
    <div className="bg-white rounded-xl border overflow-hidden transition-shadow hover:shadow-sm">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left flex items-stretch gap-4 p-4 md:p-5"
        aria-expanded={expanded}
      >
        <div className="w-24 h-24 md:w-28 md:h-28 rounded-lg overflow-hidden bg-gray-100 shrink-0 flex items-center justify-center">
          {image ? (
            <img src={image} alt="" className="w-full h-full object-cover" />
          ) : (
            <Compass className="w-8 h-8 text-gray-400" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <p className="font-semibold text-sm truncate max-w-[18rem]">{tourName}</p>
            <BookingStatusBadge status={booking.status} />
          </div>
          {tourItem.tour?.city && (
            <p className="text-xs text-gray-500 flex items-center gap-1 mb-1.5">
              <MapPin className="w-3 h-3" />
              {[tourItem.tour.city, tourItem.tour.country].filter(Boolean).join(', ')}
            </p>
          )}
          <div className="flex flex-wrap gap-3 text-xs text-gray-500">
            {tourItem.check_in && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {formatDate(tourItem.check_in)}
              </span>
            )}
            {(tourItem.adults_count || tourItem.quantity) && (
              <span className="flex items-center gap-1">
                <Users className="w-3 h-3" />
                {tourItem.adults_count || 1} {t('bookings.adults')}
                {tourItem.children_count ? ` · ${tourItem.children_count} ${t('bookings.children')}` : ''}
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end justify-between shrink-0">
          <p className="font-bold text-primary text-base">{fmt(booking.total_price)}</p>
          <ChevronDown
            className={`w-5 h-5 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      {expanded && (
        <div className="border-t bg-gray-50/60 p-4 md:p-5 space-y-4 text-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <p className="font-medium text-gray-900">{t('bookings.tourDetails')}</p>
              {tourItem.check_in && (
                <p className="text-gray-600 text-xs">
                  {t('bookings.tourDate')}: {formatDate(tourItem.check_in)}
                </p>
              )}
              {(tourItem.adults_count || tourItem.children_count) && (
                <p className="text-gray-600 text-xs">
                  {tourItem.adults_count || 0} {t('bookings.adults')}
                  {tourItem.children_count
                    ? ` · ${tourItem.children_count} ${t('bookings.children')}${(tourItem.children_ages?.length ? ' (' + tourItem.children_ages.join(', ') + ')' : '')}`
                    : ''}
                </p>
              )}
              <p className="text-gray-600 text-xs">
                {t('bookings.participants')}: {tourItem.quantity}
              </p>
            </div>

            <div className="space-y-2">
              <p className="font-medium text-gray-900">{t('bookings.priceBreakdown')}</p>
              <div className="text-xs text-gray-600 space-y-0.5">
                <div className="flex justify-between">
                  <span>{t('bookings.subtotal')}</span>
                  <span>{fmt(booking.subtotal || tourItem.subtotal)}</span>
                </div>
                {booking.discount_amount > 0 && (
                  <div className="flex justify-between text-success">
                    <span>{t('bookings.discount')}</span>
                    <span>-{fmt(booking.discount_amount)}</span>
                  </div>
                )}
                {booking.taxes > 0 && (
                  <div className="flex justify-between">
                    <span>{t('bookings.taxes')}</span>
                    <span>{fmt(booking.taxes)}</span>
                  </div>
                )}
                <div className="flex justify-between font-semibold text-gray-900 pt-1 border-t">
                  <span>{t('bookings.total')}</span>
                  <span>{fmt(booking.total_price)}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600 pt-2 border-t border-gray-200">
            <div className="flex items-center gap-1.5">
              <Hash className="w-3 h-3" />
              <span className="font-mono">{booking.id.slice(0, 8).toUpperCase()}</span>
            </div>
            {tourItem.viator_booking_ref && (
              <div className="flex items-center gap-1.5">
                <FileText className="w-3 h-3" />
                <span className="font-mono">{tourItem.viator_booking_ref}</span>
              </div>
            )}
            <div>{t('bookings.bookedOn', { date: formatDate(booking.created_at) })}</div>
          </div>

          {booking.special_requests && (
            <div className="bg-white border rounded-lg p-3 text-xs">
              <p className="font-medium text-gray-900 mb-1">{t('bookings.specialRequests')}</p>
              <p className="text-gray-600">{booking.special_requests}</p>
            </div>
          )}

          <div className="flex flex-wrap items-center gap-2 pt-1">
            {href && (
              <Link
                to={href}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-primary text-primary rounded-lg hover:bg-primary hover:text-white transition-colors"
              >
                <ExternalLink className="w-3 h-3" />
                {t('bookings.viewTour')}
              </Link>
            )}
            {['confirmed', 'completed'].includes(String(booking.status).toLowerCase()) && (
              <button
                type="button"
                onClick={handleDownloadPdf}
                disabled={downloading}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-gray-300 text-gray-700 rounded-lg hover:border-primary hover:text-primary transition-colors disabled:opacity-50"
              >
                <Download className="w-3 h-3" />
                {downloading
                  ? t('bookings.downloadingPdf', { defaultValue: 'Preparing PDF…' })
                  : t('bookings.downloadPdf', { defaultValue: 'Download PDF' })}
              </button>
            )}
            {canCancel(booking.status) && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onCancel(booking)
                }}
                className="ml-auto px-3 py-1.5 text-xs font-medium text-error hover:bg-error/10 rounded-lg"
              >
                {t('bookings.cancel')}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
