import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { SearchX, PackageOpen, Heart, Star, CalendarOff } from 'lucide-react'

const ICONS = {
  search: SearchX,
  empty: PackageOpen,
  wishlist: Heart,
  reviews: Star,
  bookings: CalendarOff,
}

export default function EmptyState({
  icon = 'empty',
  title = 'Nothing here yet',
  description,
  actionLabel,
  actionTo,
}) {
  const Icon = ICONS[icon] || PackageOpen

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="text-center py-16 px-4"
    >
      <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-5">
        <Icon className="w-10 h-10 text-gray-300" />
      </div>
      <h3 className="font-heading text-lg font-bold text-gray-700 mb-1">{title}</h3>
      {description && <p className="text-sm text-gray-400 max-w-sm mx-auto mb-6">{description}</p>}
      {actionLabel && actionTo && (
        <Link
          to={actionTo}
          className="inline-flex items-center gap-2 bg-primary hover:bg-primary-dark text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors"
        >
          {actionLabel}
        </Link>
      )}
    </motion.div>
  )
}
