import { Star, ThumbsUp } from 'lucide-react'
import { formatDate } from '@/utils/formatters'

export default function ReviewCard({ review }) {
  const initial = review.user?.full_name?.[0]?.toUpperCase() || 'U'

  return (
    <div className="border-b pb-5 last:border-0">
      <div className="flex items-start gap-3">
        <div className="w-10 h-10 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm shrink-0">
          {initial}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-semibold text-sm">{review.user?.full_name || 'Anonymous'}</p>
              <p className="text-xs text-gray-400">{formatDate(review.created_at)}</p>
            </div>
            <div className="flex items-center gap-1 bg-primary text-white px-2 py-0.5 rounded text-sm font-bold">
              <Star className="w-3.5 h-3.5 fill-current" />{review.rating}
            </div>
          </div>
          {review.comment && (
            <p className="mt-2 text-sm text-gray-700 leading-relaxed">{review.comment}</p>
          )}
        </div>
      </div>
    </div>
  )
}
