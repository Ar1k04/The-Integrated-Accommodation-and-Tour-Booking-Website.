import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { MapPin, Star, User } from 'lucide-react'
import StarRating from '@/components/common/StarRating'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { useSearchStore } from '@/store/searchStore'
import { format } from 'date-fns'

export default function HotelCard({ hotel }) {
  const { t } = useTranslation('common')
  const fmt = useFormatCurrency()
  const { checkIn, checkOut, guests } = useSearchStore()

  const isLiteapi = hotel.source === 'liteapi'
  const basePath = isLiteapi
    ? `/hotels/liteapi/${hotel.liteapi_hotel_id}`
    : `/hotels/${hotel.id}`

  const buildHref = () => {
    const params = new URLSearchParams()
    if (checkIn) params.set('check_in', format(checkIn, 'yyyy-MM-dd'))
    if (checkOut) params.set('check_out', format(checkOut, 'yyyy-MM-dd'))
    const totalGuests = (guests.adults || 1) + (guests.children || 0)
    if (totalGuests) params.set('guests', String(totalGuests))
    if (guests.rooms > 1) params.set('rooms', String(guests.rooms))
    const qs = params.toString()
    return qs ? `${basePath}?${qs}` : basePath
  }

  const hotelHref = buildHref()

  const mainImage = hotel.images?.[0] || 'https://placehold.co/400x300?text=Hotel'

  const ratingLabel = (r) => {
    if (r >= 9) return 'Exceptional'
    if (r >= 8) return 'Excellent'
    if (r >= 7) return 'Very Good'
    if (r >= 6) return 'Good'
    return 'Pleasant'
  }

  return (
    <div className="bg-white rounded-xl shadow-sm hover:shadow-lg transition-all duration-300 overflow-hidden flex flex-col md:flex-row group">
      <Link to={hotelHref} className="relative md:w-72 md:h-56 shrink-0 overflow-hidden">
        <img
          src={mainImage}
          alt={hotel.name}
          className="w-full h-48 md:h-56 object-cover group-hover:scale-105 transition-transform duration-500"
        />
        {isLiteapi && (
          <span className="absolute top-2 left-2 bg-emerald-500 text-white text-xs font-semibold px-2 py-0.5 rounded-full">
            Live rates
          </span>
        )}
      </Link>

      <div className="flex-1 p-4 flex flex-col justify-between min-w-0">
        <div>
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <Link to={hotelHref} className="font-heading font-bold text-lg text-gray-900 hover:text-primary line-clamp-1">
                {hotel.name}
              </Link>
              <div className="flex items-center gap-2 mt-1">
                <StarRating rating={hotel.star_rating} size={14} />
                {hotel.property_type && (
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">{hotel.property_type}</span>
                )}
              </div>
            </div>
            {hotel.avg_rating > 0 && (
              <div className="shrink-0 text-right">
                <div className="bg-primary text-white text-sm font-bold px-2 py-1 rounded-lg">
                  {hotel.avg_rating.toFixed(1)}
                </div>
                <p className="text-xs text-gray-500 mt-0.5">{ratingLabel(hotel.avg_rating)}</p>
                <p className="text-xs text-gray-400">{hotel.total_reviews} reviews</p>
              </div>
            )}
          </div>

          <div className="flex items-center gap-1 mt-2 text-gray-500 text-sm">
            <MapPin className="w-3.5 h-3.5" />
            <span>{hotel.city}, {hotel.country}</span>
          </div>

          {hotel.owner_name && (
            <div className="flex items-center gap-1 mt-1 text-gray-500 text-sm">
              <User className="w-3.5 h-3.5" />
              <span>by <span className="font-medium text-gray-700">{hotel.owner_name}</span></span>
            </div>
          )}

          {hotel.amenities?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {hotel.amenities.slice(0, 5).map((a) => (
                <span key={a} className="text-xs bg-blue-50 text-primary px-2 py-0.5 rounded capitalize">{a}</span>
              ))}
              {hotel.amenities.length > 5 && (
                <span className="text-xs text-gray-400">+{hotel.amenities.length - 5} more</span>
              )}
            </div>
          )}
        </div>

        <div className="flex items-end justify-between mt-4 pt-3 border-t border-gray-100">
          <div>
            <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">From</p>
            <p className="text-2xl font-bold text-gray-900">
              {hotel.min_room_price != null ? fmt(hotel.min_room_price) : '—'}
            </p>
            <p className="text-xs text-gray-500">{t('common.perNight')}</p>
          </div>
          <Link
            to={hotelHref}
            className="bg-accent hover:bg-accent-dark text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
          >
            {t('common.bookNow')}
          </Link>
        </div>
      </div>
    </div>
  )
}
