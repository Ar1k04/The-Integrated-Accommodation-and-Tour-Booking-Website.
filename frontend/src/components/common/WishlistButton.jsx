import { useNavigate, useLocation } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Heart } from 'lucide-react'
import { toast } from 'sonner'
import { adminApi } from '@/api/adminApi'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

/**
 * Toggle a hotel or tour in the signed-in user's wishlist.
 *
 * Supports both internal (DB-backed) and external listings. Pass exactly one of:
 *   - `hotelId`            — internal hotel (FK hotels.id)
 *   - `tourId`             — internal tour (FK tours.id)
 *   - `liteapiHotelId`     — external LiteAPI hotel
 *   - `viatorProductCode`  — external Viator tour
 * For external listings also pass a display snapshot (`name`, `city`, `country`,
 * `image`) so the wishlist tab can render and link the item without re-fetching.
 *
 * `variant="icon"` renders a floating heart for cards; the default renders a
 * labelled pill for detail headers.
 */
export default function WishlistButton({
  hotelId,
  tourId,
  liteapiHotelId,
  viatorProductCode,
  name,
  city,
  country,
  image,
  variant = 'button',
  className,
}) {
  const { isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const qc = useQueryClient()

  const hasTarget = Boolean(hotelId || tourId || liteapiHotelId || viatorProductCode)

  const { data: wishlists } = useQuery({
    queryKey: ['my-wishlists'],
    queryFn: () => adminApi.listWishlists({ per_page: 100 }),
    select: (res) => res.data?.items || [],
    enabled: isAuthenticated && hasTarget,
    staleTime: 60_000,
  })

  const entry = (wishlists || []).find((w) => {
    if (hotelId) return w.hotel_id === hotelId
    if (tourId) return w.tour_id === tourId
    if (liteapiHotelId) return w.liteapi_hotel_id === liteapiHotelId
    return w.viator_product_code === viatorProductCode
  })
  const saved = Boolean(entry)

  const buildPayload = () => {
    if (hotelId) return { hotel_id: hotelId }
    if (tourId) return { tour_id: tourId }
    const snapshot = { item_name: name, item_city: city, item_country: country, item_image: image }
    if (liteapiHotelId) return { liteapi_hotel_id: liteapiHotelId, ...snapshot }
    return { viator_product_code: viatorProductCode, ...snapshot }
  }

  const addMut = useMutation({
    mutationFn: () => adminApi.addToWishlist(buildPayload()),
    onSuccess: () => {
      toast.success('Saved to wishlist')
      qc.invalidateQueries({ queryKey: ['my-wishlists'] })
    },
    onError: (err) => {
      if (err?.response?.status === 409) {
        qc.invalidateQueries({ queryKey: ['my-wishlists'] })
        return
      }
      toast.error('Could not save to wishlist')
    },
  })

  const removeMut = useMutation({
    mutationFn: () => adminApi.removeFromWishlist(entry.id),
    onSuccess: () => {
      toast.success('Removed from wishlist')
      qc.invalidateQueries({ queryKey: ['my-wishlists'] })
    },
    onError: () => toast.error('Could not remove from wishlist'),
  })

  const busy = addMut.isPending || removeMut.isPending

  // Nothing to reference → render nothing.
  if (!hasTarget) return null

  const handleClick = (e) => {
    e.preventDefault()
    e.stopPropagation()
    if (!isAuthenticated) {
      toast.error('Please sign in to save to your wishlist')
      navigate('/login', { state: { from: location } })
      return
    }
    if (busy) return
    if (saved) removeMut.mutate()
    else addMut.mutate()
  }

  const label = saved ? 'Remove from wishlist' : 'Save to wishlist'

  if (variant === 'icon') {
    return (
      <button
        type="button"
        onClick={handleClick}
        disabled={busy}
        aria-label={label}
        title={label}
        className={cn(
          'absolute top-3 right-3 z-10 grid place-items-center w-9 h-9 rounded-full',
          'bg-white/90 backdrop-blur shadow-sm hover:bg-white transition-colors',
          'disabled:opacity-60',
          className,
        )}
      >
        <Heart className={cn('w-5 h-5 transition-colors', saved ? 'fill-error text-error' : 'text-gray-600')} />
      </button>
    )
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      aria-label={label}
      className={cn(
        'inline-flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-semibold transition-colors',
        saved
          ? 'border-error/30 bg-error/5 text-error hover:bg-error/10'
          : 'border-gray-200 text-gray-700 hover:bg-gray-50',
        'disabled:opacity-60',
        className,
      )}
    >
      <Heart className={cn('w-4 h-4', saved && 'fill-error text-error')} />
      {saved ? 'Saved' : 'Save'}
    </button>
  )
}
