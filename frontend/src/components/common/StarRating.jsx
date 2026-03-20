import { Star } from 'lucide-react'

export default function StarRating({ rating, size = 16, className = '' }) {
  return (
    <div className={`flex items-center gap-0.5 ${className}`}>
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          className={i < rating ? 'fill-warning text-warning' : 'text-gray-300'}
          size={size}
        />
      ))}
    </div>
  )
}
