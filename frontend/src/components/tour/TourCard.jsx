import { Link } from 'react-router-dom'
import { Clock, MapPin, Star, User, Users } from 'lucide-react'
import { formatCurrency } from '@/utils/formatters'

export default function TourCard({ tour }) {
  const isViator = tour.source === 'viator'
  const tourHref = isViator
    ? `/tours/viator/${tour.viator_product_code}`
    : `/tours/${tour.id}`

  const mainImage = tour.images?.[0] || 'https://placehold.co/400x300?text=Tour'

  return (
    <div className="bg-white rounded-xl shadow-sm hover:shadow-lg transition-all duration-300 overflow-hidden group">
      <Link to={tourHref} className="block relative overflow-hidden">
        <img
          src={mainImage}
          alt={tour.name}
          className="w-full h-52 object-cover group-hover:scale-105 transition-transform duration-500"
        />
        {tour.category && (
          <span className="absolute top-3 left-3 bg-primary text-white text-xs font-semibold px-3 py-1 rounded-full capitalize">
            {tour.category}
          </span>
        )}
        {isViator && (
          <span className="absolute top-3 right-3 bg-emerald-500 text-white text-xs font-semibold px-2 py-0.5 rounded-full">
            Live
          </span>
        )}
      </Link>

      <div className="p-4">
        <Link to={tourHref} className="font-heading font-bold text-gray-900 hover:text-primary line-clamp-2">
          {tour.name}
        </Link>

        <div className="flex items-center gap-3 mt-2 text-sm text-gray-500">
          <span className="flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5" />{tour.city}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />{tour.duration_days} day{tour.duration_days > 1 ? 's' : ''}
          </span>
          <span className="flex items-center gap-1">
            <Users className="w-3.5 h-3.5" />Max {tour.max_participants}
          </span>
        </div>

        {tour.owner_name && (
          <div className="flex items-center gap-1 mt-2 text-sm text-gray-500">
            <User className="w-3.5 h-3.5" />
            <span>by <span className="font-medium text-gray-700">{tour.owner_name}</span></span>
          </div>
        )}

        {tour.avg_rating > 0 && (
          <div className="flex items-center gap-1.5 mt-2">
            <Star className="w-4 h-4 fill-warning text-warning" />
            <span className="text-sm font-semibold">{tour.avg_rating.toFixed(1)}</span>
            <span className="text-xs text-gray-400">({tour.total_reviews})</span>
          </div>
        )}

        <div className="flex items-end justify-between mt-3 pt-3 border-t border-gray-100">
          <div>
            <p className="text-xl font-bold text-gray-900">{formatCurrency(tour.price_per_person)}</p>
            <p className="text-xs text-gray-500">per person</p>
          </div>
          <Link
            to={tourHref}
            className="bg-accent hover:bg-accent-dark text-white font-semibold px-4 py-2 rounded-lg text-sm transition-colors"
          >
            Book Now
          </Link>
        </div>
      </div>
    </div>
  )
}
