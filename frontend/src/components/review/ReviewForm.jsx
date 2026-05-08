import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { reviewsApi } from '@/api/reviewsApi'
import { toast } from 'sonner'
import { Star } from 'lucide-react'
import { useTranslation } from 'react-i18next'

export default function ReviewForm({ hotelId, tourId, onDone }) {
  const { t } = useTranslation('hotels')
  const [rating, setRating] = useState(0)
  const [hoverRating, setHoverRating] = useState(0)
  const [comment, setComment] = useState('')
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: (data) => reviewsApi.create(data),
    onSuccess: () => {
      toast.success(t('detail.submitReview'))
      qc.invalidateQueries({ queryKey: ['reviews'] })
      onDone?.()
    },
    onError: (err) => {
      toast.error(err.response?.data?.detail || t('detail.submitting'))
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    if (rating === 0) { toast.error(t('detail.selectRating')); return }
    mutation.mutate({ hotel_id: hotelId || undefined, tour_id: tourId || undefined, rating, comment })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-gray-50 rounded-xl p-5 space-y-4">
      <h3 className="font-heading font-bold text-gray-900">{t('detail.writeReview')}</h3>
      <div className="flex items-center gap-1">
        {Array.from({ length: 5 }, (_, i) => (
          <button key={i} type="button"
            onMouseEnter={() => setHoverRating(i + 1)}
            onMouseLeave={() => setHoverRating(0)}
            onClick={() => setRating(i + 1)}>
            <Star className={`w-7 h-7 transition-colors ${
              (hoverRating || rating) > i ? 'fill-warning text-warning' : 'text-gray-300'
            }`} />
          </button>
        ))}
        <span className="ml-2 text-sm text-gray-500">{rating > 0 ? `${rating}/5` : t('detail.selectRating')}</span>
      </div>
      <textarea value={comment} onChange={(e) => setComment(e.target.value)}
        placeholder={t('detail.experiencePlaceholder')}
        className="w-full border rounded-lg px-4 py-3 text-sm resize-none h-24 focus:outline-none focus:ring-2 focus:ring-primary/30" />
      <button type="submit" disabled={mutation.isPending}
        className="bg-primary hover:bg-primary-dark text-white font-semibold px-6 py-2.5 rounded-lg text-sm transition-colors disabled:opacity-50">
        {mutation.isPending ? t('detail.submitting') : t('detail.submitReview')}
      </button>
    </form>
  )
}
