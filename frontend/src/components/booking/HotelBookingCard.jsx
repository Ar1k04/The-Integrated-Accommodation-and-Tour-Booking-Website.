import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import {
  Calendar, Users, ChevronDown, MapPin, Hotel as HotelIcon,
  ExternalLink, FileText, Hash, Download,
} from 'lucide-react'
import { toast } from 'sonner'
import BookingStatusBadge from '@/components/common/BookingStatusBadge'
import CancellationPolicyBadge from './CancellationPolicyBadge'
import { hotelsApi } from '@/api/hotelsApi'
import { formatDate, nightsBetween } from '@/utils/formatters'
import { downloadBookingPdf } from '@/utils/bookingPdf'

// Resolves the right detail-page URL for a hotel booking item. Falls back from
// the local DB hotel id to the LiteAPI hotel id, mirroring the routing in
// frontend/src/router/index.jsx. Returns null when neither is available — we
// hide the "View hotel" CTA in that case rather than producing a dead link.
function hotelHref(item) {
  if (item.hotel?.id) return `/hotels/${item.hotel.id}`
  const liteapiId = item.hotel?.liteapi_hotel_id || item.liteapi_hotel_id
  if (liteapiId) return `/hotels/liteapi/${liteapiId}`
  return null
}

export default function HotelBookingCard({ booking, fmt, canCancel, onCancel }) {
  const { t } = useTranslation('profile')
  const [expanded, setExpanded] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const roomItem = booking.items?.find((i) => i.item_type === 'room')
  if (!roomItem) return null

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

  const href = hotelHref(roomItem)
  const hotelName = roomItem.hotel?.name || roomItem.hotel_name || roomItem.room?.name || t('bookings.hotelRoom')
  const nights = roomItem.check_in && roomItem.check_out
    ? nightsBetween(roomItem.check_in, roomItem.check_out)
    : null

  // Image: prefer the URL persisted at booking time (DB hotel `images[0]` or
  // the LiteAPI image we now stash on the booking item). Older bookings made
  // before that column existed have neither — for those, lazy-fetch the
  // LiteAPI hotel detail once and cache for 24h via react-query so the same
  // hotel isn't re-fetched per card render.
  const persistedImage = roomItem.hotel?.image_url
  const liteapiId = roomItem.hotel?.liteapi_hotel_id || roomItem.liteapi_hotel_id
  const { data: fetchedImage } = useQuery({
    queryKey: ['booking-card-hotel-image', liteapiId],
    enabled: Boolean(!persistedImage && liteapiId),
    staleTime: 24 * 60 * 60 * 1000,
    retry: false,
    queryFn: () => hotelsApi.getLiteapi(liteapiId).then((r) => r.data?.images?.[0] || null),
  })
  const image = persistedImage || fetchedImage

  return (
    <div className="bg-white rounded-xl border overflow-hidden transition-shadow hover:shadow-sm">
      {/* Collapsed header — click anywhere except the title link to toggle. */}
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
            <HotelIcon className="w-8 h-8 text-gray-400" />
          )}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <p className="font-semibold text-sm truncate max-w-[18rem]">{hotelName}</p>
            <BookingStatusBadge status={booking.status} />
          </div>
          {roomItem.hotel?.city && (
            <p className="text-xs text-gray-500 flex items-center gap-1 mb-1.5">
              <MapPin className="w-3 h-3" />
              {[roomItem.hotel.city, roomItem.hotel.country].filter(Boolean).join(', ')}
            </p>
          )}
          <div className="flex flex-wrap gap-3 text-xs text-gray-500">
            {roomItem.check_in && roomItem.check_out && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {formatDate(roomItem.check_in)} — {formatDate(roomItem.check_out)}
                {nights ? ` · ${nights} ${nights === 1 ? t('bookings.night') : t('bookings.nights')}` : ''}
              </span>
            )}
            {(roomItem.adults_count || roomItem.quantity) && (
              <span className="flex items-center gap-1">
                <Users className="w-3 h-3" />
                {roomItem.adults_count || 1} {t('bookings.adults')}
                {roomItem.children_count ? ` · ${roomItem.children_count} ${t('bookings.children')}` : ''}
                {roomItem.quantity > 1 ? ` · ${roomItem.quantity} ${t('bookings.rooms')}` : ''}
              </span>
            )}
          </div>
          <div className="mt-2">
            <CancellationPolicyBadge
              refundable={roomItem.refundable}
              deadline={roomItem.cancellation_deadline}
            />
          </div>
        </div>
        <div className="flex flex-col items-end justify-between shrink-0">
          <p className="font-bold text-primary text-base">{fmt(booking.total_price)}</p>
          <ChevronDown
            className={`w-5 h-5 text-gray-400 transition-transform ${expanded ? 'rotate-180' : ''}`}
          />
        </div>
      </button>

      {/* Expanded detail panel. */}
      {expanded && (
        <div className="border-t bg-gray-50/60 p-4 md:p-5 space-y-4 text-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <p className="font-medium text-gray-900">{t('bookings.stayDetails')}</p>
              {(roomItem.room?.name || roomItem.hotel_name) && (
                <p className="text-gray-700">{roomItem.room?.name || roomItem.room?.room_type}</p>
              )}
              {roomItem.check_in && roomItem.check_out && (
                <p className="text-gray-600 text-xs">
                  {t('bookings.checkIn')}: {formatDate(roomItem.check_in)}<br />
                  {t('bookings.checkOut')}: {formatDate(roomItem.check_out)}
                </p>
              )}
              {(roomItem.adults_count || roomItem.children_count) && (
                <p className="text-gray-600 text-xs">
                  {roomItem.adults_count || 0} {t('bookings.adults')}
                  {roomItem.children_count
                    ? ` · ${roomItem.children_count} ${t('bookings.children')}${(roomItem.children_ages?.length ? ' (' + roomItem.children_ages.join(', ') + ')' : '')}`
                    : ''}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <p className="font-medium text-gray-900">{t('bookings.priceBreakdown')}</p>
              <div className="text-xs text-gray-600 space-y-0.5">
                <div className="flex justify-between">
                  <span>{t('bookings.subtotal')}</span>
                  <span>{fmt(booking.subtotal || roomItem.subtotal)}</span>
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
            {roomItem.liteapi_booking_id && (
              <div className="flex items-center gap-1.5">
                <FileText className="w-3 h-3" />
                <span className="font-mono">{roomItem.liteapi_booking_id}</span>
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
                {t('bookings.viewHotel')}
              </Link>
            )}
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
