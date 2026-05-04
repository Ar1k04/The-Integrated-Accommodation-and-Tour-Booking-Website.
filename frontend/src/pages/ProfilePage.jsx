import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/hooks/useAuth'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { bookingsApi } from '@/api/bookingsApi'
import { reviewsApi } from '@/api/reviewsApi'
import { adminApi } from '@/api/adminApi'
import { authApi } from '@/api/authApi'
import { loyaltyApi } from '@/api/loyaltyApi'
import BookingStatusBadge from '@/components/common/BookingStatusBadge'
import ReviewCard from '@/components/review/ReviewCard'
import Skeleton from '@/components/common/Skeleton'
import { formatDate } from '@/utils/formatters'
import {
  User, Briefcase, Star, Heart, Award, Shield,
  Camera, Trash2, MapPin, Clock, Calendar, Eye, TrendingUp, TrendingDown,
} from 'lucide-react'

export default function ProfilePage() {
  const { t } = useTranslation('profile')
  const [params, setParams] = useSearchParams()
  const activeTab = params.get('tab') || 'profile'
  const setTab = (key) => setParams({ tab: key })

  const TABS = [
    { key: 'profile', label: t('tabs.profile'), icon: User },
    { key: 'bookings', label: t('tabs.bookings'), icon: Briefcase },
    { key: 'reviews', label: t('tabs.reviews'), icon: Star },
    { key: 'wishlist', label: t('tabs.wishlist'), icon: Heart },
    { key: 'loyalty', label: t('tabs.loyalty'), icon: Award },
    { key: 'security', label: t('tabs.security'), icon: Shield },
  ]

  return (
    <>
      <Helmet><title>My Profile — TravelBooking</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-6xl mx-auto px-4 py-8">
          <h1 className="font-heading text-2xl font-bold text-gray-900 mb-6">My Account</h1>

          <div className="flex gap-2 overflow-x-auto pb-4 mb-6 border-b">
            {TABS.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.key}
                  onClick={() => setTab(tab.key)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                    activeTab === tab.key
                      ? 'bg-primary text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {activeTab === 'profile' && <ProfileTab />}
          {activeTab === 'bookings' && <BookingsTab />}
          {activeTab === 'reviews' && <ReviewsTab />}
          {activeTab === 'wishlist' && <WishlistTab />}
          {activeTab === 'loyalty' && <LoyaltyTab />}
          {activeTab === 'security' && <SecurityTab />}
        </div>
      </div>
    </>
  )
}

function ProfileTab() {
  const { user, updateProfile } = useAuth()
  const [form, setForm] = useState({
    full_name: user?.full_name || '',
    email: user?.email || '',
    phone: user?.phone || '',
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async (e) => {
    e.preventDefault()
    setSaving(true)
    try {
      await updateProfile(form)
      toast.success('Profile updated')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="bg-white rounded-xl border p-6 space-y-6">
        <div className="flex items-center gap-4">
          <div className="relative">
            <div className="w-20 h-20 rounded-full bg-primary/10 text-primary flex items-center justify-center text-2xl font-bold">
              {user?.avatar_url ? (
                <img src={user.avatar_url} alt="" className="w-full h-full rounded-full object-cover" />
              ) : (
                user?.full_name?.[0]?.toUpperCase() || 'U'
              )}
            </div>
            <button className="absolute -bottom-1 -right-1 bg-primary text-white rounded-full p-1.5 shadow" aria-label="Change avatar">
              <Camera className="w-3 h-3" />
            </button>
          </div>
          <div>
            <p className="font-heading font-bold text-lg">{user?.full_name}</p>
            <p className="text-sm text-gray-500">{user?.email}</p>
            <p className="text-xs text-gray-400 mt-1">Member since {formatDate(user?.created_at)}</p>
          </div>
        </div>

        <form onSubmit={handleSave} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
              <input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
              <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
            </div>
          </div>
          <button type="submit" disabled={saving}
            className="bg-primary hover:bg-primary-dark text-white font-semibold px-6 py-2.5 rounded-lg text-sm transition-colors disabled:opacity-50">
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </form>
      </div>
    </div>
  )
}

function BookingsTab() {
  const { t } = useTranslation('profile')
  const fmt = useFormatCurrency()
  const [subTab, setSubTab] = useState('hotels')
  const qc = useQueryClient()

  const { data: allBookings, isLoading: loadingAll } = useQuery({
    queryKey: ['my-bookings'],
    queryFn: () => bookingsApi.list({ per_page: 100 }),
    select: (res) => res.data?.items || [],
  })

  const hotelBookings = allBookings?.filter(b => b.items?.some(i => i.item_type === 'room')) || []
  const tourBookings = allBookings?.filter(b => b.items?.some(i => i.item_type === 'tour')) || []
  const loadingHotel = loadingAll
  const loadingTour = loadingAll

  const cancelHotel = useMutation({
    mutationFn: (id) => bookingsApi.cancel(id),
    onSuccess: () => { toast.success('Booking cancelled'); qc.invalidateQueries({ queryKey: ['my-bookings'] }) },
    onError: () => toast.error('Failed to cancel'),
  })

  const cancelTour = useMutation({
    mutationFn: (id) => bookingsApi.cancel(id),
    onSuccess: () => { toast.success('Tour booking cancelled'); qc.invalidateQueries({ queryKey: ['my-bookings'] }) },
    onError: () => toast.error('Failed to cancel'),
  })

  return (
    <div>
      <div className="flex gap-2 mb-6">
        <button onClick={() => setSubTab('hotels')}
          className={`px-4 py-2 rounded-lg text-sm font-medium ${subTab === 'hotels' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}`}>
          {t('bookings.hotels')}
        </button>
        <button onClick={() => setSubTab('tours')}
          className={`px-4 py-2 rounded-lg text-sm font-medium ${subTab === 'tours' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}`}>
          {t('bookings.tours')}
        </button>
      </div>

      {subTab === 'hotels' && (
        loadingHotel ? (
          <div className="space-y-3">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}</div>
        ) : hotelBookings?.length > 0 ? (
          <div className="space-y-4">
            {hotelBookings.map((b) => (
              <div key={b.id} className="bg-white rounded-xl border p-5 flex flex-col md:flex-row md:items-center gap-4">
                <div className="flex-1 min-w-0">
                  {(() => {
                    const roomItem = b.items?.find(i => i.item_type === 'room')
                    return (
                      <>
                        <div className="flex items-center gap-2 mb-1">
                          <p className="font-semibold text-sm truncate">{roomItem?.room?.name || 'Hotel Room'}</p>
                          <BookingStatusBadge status={b.status} />
                        </div>
                        <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                          {roomItem?.check_in && roomItem?.check_out && (
                            <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{formatDate(roomItem.check_in)} — {formatDate(roomItem.check_out)}</span>
                          )}
                          {roomItem?.quantity && (
                            <span>{roomItem.quantity} room{roomItem.quantity > 1 ? 's' : ''}</span>
                          )}
                        </div>
                      </>
                    )
                  })()}
                </div>
                <div className="flex items-center gap-3">
                  <p className="font-bold text-primary">{fmt(b.total_price)}</p>
                  {b.status === 'pending' && (
                    <button onClick={() => cancelHotel.mutate(b.id)}
                      className="text-error text-xs hover:underline">Cancel</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState message="No hotel bookings yet" />
        )
      )}

      {subTab === 'tours' && (
        loadingTour ? (
          <div className="space-y-3">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-24 rounded-xl" />)}</div>
        ) : tourBookings?.length > 0 ? (
          <div className="space-y-4">
            {tourBookings.map((b) => {
              const tourItem = b.items?.find(i => i.item_type === 'tour')
              return (
                <div key={b.id} className="bg-white rounded-xl border p-5 flex flex-col md:flex-row md:items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <p className="font-semibold text-sm truncate">{tourItem?.viator_tour_name || 'Tour'}</p>
                      <BookingStatusBadge status={b.status} />
                    </div>
                    <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                      {tourItem?.check_in && (
                        <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{formatDate(tourItem.check_in)}</span>
                      )}
                      {tourItem?.quantity && (
                        <span>{tourItem.quantity} participant{tourItem.quantity > 1 ? 's' : ''}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <p className="font-bold text-primary">{fmt(b.total_price)}</p>
                    {b.status === 'pending' && (
                      <button onClick={() => cancelTour.mutate(b.id)}
                        className="text-error text-xs hover:underline">Cancel</button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <EmptyState message="No tour bookings yet" />
        )
      )}
    </div>
  )
}

function ReviewsTab() {
  const { user } = useAuth()
  const qc = useQueryClient()

  const { data: hotelReviews, isLoading: l1 } = useQuery({
    queryKey: ['my-hotel-reviews'],
    queryFn: () => reviewsApi.listHotelReviews('me', { per_page: 50 }),
    select: (res) => res.data?.items || [],
    retry: false,
  })

  const { data: tourReviews, isLoading: l2 } = useQuery({
    queryKey: ['my-tour-reviews'],
    queryFn: () => reviewsApi.listTourReviews('me', { per_page: 50 }),
    select: (res) => res.data?.items || [],
    retry: false,
  })

  const deleteMut = useMutation({
    mutationFn: (id) => reviewsApi.delete(id),
    onSuccess: () => {
      toast.success('Review deleted')
      qc.invalidateQueries({ queryKey: ['my-hotel-reviews'] })
      qc.invalidateQueries({ queryKey: ['my-tour-reviews'] })
    },
    onError: () => toast.error('Failed to delete review'),
  })

  const allReviews = [...(hotelReviews || []), ...(tourReviews || [])]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))

  if (l1 || l2) return <div className="space-y-3">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>

  return allReviews.length > 0 ? (
    <div className="space-y-4 max-w-3xl">
      {allReviews.map((r) => (
        <div key={r.id} className="bg-white rounded-xl border p-5">
          <ReviewCard review={r} />
          <div className="mt-3 flex gap-2">
            <button onClick={() => deleteMut.mutate(r.id)}
              className="text-xs text-error hover:underline flex items-center gap-1">
              <Trash2 className="w-3 h-3" /> Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  ) : (
    <EmptyState message="You haven't written any reviews yet" />
  )
}

function WishlistTab() {
  const qc = useQueryClient()

  const { data: wishlists, isLoading } = useQuery({
    queryKey: ['my-wishlists'],
    queryFn: () => adminApi.listWishlists({ per_page: 50 }),
    select: (res) => res.data?.items || [],
  })

  const removeMut = useMutation({
    mutationFn: (id) => adminApi.removeFromWishlist(id),
    onSuccess: () => { toast.success('Removed from wishlist'); qc.invalidateQueries({ queryKey: ['my-wishlists'] }) },
    onError: () => toast.error('Failed to remove'),
  })

  if (isLoading) return <div className="space-y-3">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-20 rounded-xl" />)}</div>

  return wishlists?.length > 0 ? (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {wishlists.map((w) => (
        <div key={w.id} className="bg-white rounded-xl border p-5 flex items-start gap-4">
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-sm">{w.hotel?.name || w.tour?.name || 'Item'}</p>
            <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
              <MapPin className="w-3 h-3" />{w.hotel?.city || w.tour?.city}
            </p>
          </div>
          <button onClick={() => removeMut.mutate(w.id)} className="text-error hover:bg-error/10 p-2 rounded-lg" aria-label="Remove from wishlist">
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  ) : (
    <EmptyState message="Your wishlist is empty" />
  )
}

const TIER_COLORS = {
  Bronze: { bg: 'bg-amber-600', ring: 'ring-amber-600/30', text: 'text-amber-600' },
  Silver: { bg: 'bg-gray-400', ring: 'ring-gray-400/30', text: 'text-gray-500' },
  Gold: { bg: 'bg-yellow-500', ring: 'ring-yellow-500/30', text: 'text-yellow-600' },
  Platinum: { bg: 'bg-purple-500', ring: 'ring-purple-500/30', text: 'text-purple-600' },
}

function LoyaltyTab() {
  const fmt = useFormatCurrency()
  const { data: loyaltyData, isLoading } = useQuery({
    queryKey: ['loyalty-status'],
    queryFn: () => loyaltyApi.getStatus(),
    select: (res) => res.data,
  })

  if (isLoading) {
    return (
      <div className="max-w-2xl space-y-4">
        {Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
      </div>
    )
  }

  const totalPoints = loyaltyData?.total_points || 0
  const currentTier = loyaltyData?.current_tier
  const nextTier = loyaltyData?.next_tier
  const pointsToNext = loyaltyData?.points_to_next_tier || 0
  const transactions = loyaltyData?.recent_transactions || []
  const tierName = currentTier?.name || 'Bronze'
  const colors = TIER_COLORS[tierName] || TIER_COLORS.Bronze

  const progressPct = nextTier && currentTier
    ? Math.min(
        ((totalPoints - currentTier.min_points) /
          (nextTier.min_points - currentTier.min_points)) * 100,
        100
      )
    : 100

  return (
    <div className="max-w-2xl space-y-6">
      {/* Tier card */}
      <div className="bg-white rounded-xl border p-6 text-center">
        <div className={`w-16 h-16 rounded-full ${colors.bg} text-white flex items-center justify-center mx-auto mb-3 ring-4 ${colors.ring}`}>
          <Award className="w-8 h-8" />
        </div>
        <p className="text-sm text-gray-500">Current Tier</p>
        <p className={`font-heading text-2xl font-bold ${colors.text}`}>{tierName}</p>
        {currentTier?.discount_percent > 0 && (
          <p className="text-xs text-gray-400 mt-1">{currentTier.discount_percent}% tier discount</p>
        )}
        <p className="text-4xl font-bold text-primary mt-4">{totalPoints.toLocaleString()}</p>
        <p className="text-sm text-gray-500">loyalty points</p>
        <p className="text-xs text-gray-400 mt-1">≈ {fmt(totalPoints * 0.01)} redemption value</p>

        {nextTier && (
          <div className="mt-6">
            <div className="flex justify-between text-xs text-gray-500 mb-1.5">
              <span className="font-medium">{tierName}</span>
              <span className="font-medium">{nextTier.name}</span>
            </div>
            <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <p className="text-xs text-gray-500 mt-1.5">
              {pointsToNext.toLocaleString()} more points to reach <strong>{nextTier.name}</strong>
            </p>
          </div>
        )}
        {!nextTier && (
          <p className="text-xs text-success mt-4 font-semibold">🎉 Maximum tier reached!</p>
        )}
      </div>

      {/* Transaction history */}
      {transactions.length > 0 && (
        <div className="bg-white rounded-xl border p-6">
          <h3 className="font-heading font-bold mb-4">Recent Transactions</h3>
          <div className="space-y-3">
            {transactions.map((txn) => (
              <div key={txn.id} className="flex items-center gap-3 py-2 border-b last:border-0">
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                  txn.points > 0 ? 'bg-success/10 text-success' : 'bg-error/10 text-error'
                }`}>
                  {txn.points > 0
                    ? <TrendingUp className="w-4 h-4" />
                    : <TrendingDown className="w-4 h-4" />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{txn.description || (txn.type === 'earn' ? 'Points earned' : 'Points redeemed')}</p>
                  <p className="text-xs text-gray-400">{formatDate(txn.created_at)}</p>
                </div>
                <span className={`text-sm font-bold shrink-0 ${txn.points > 0 ? 'text-success' : 'text-error'}`}>
                  {txn.points > 0 ? '+' : ''}{txn.points} pts
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* How to earn */}
      <div className="bg-white rounded-xl border p-6">
        <h3 className="font-heading font-bold mb-3">How to Earn Points</h3>
        <ul className="space-y-2 text-sm text-gray-600">
          <li className="flex items-center gap-2"><Star className="w-4 h-4 text-warning" />1 point per $1 spent on bookings</li>
          <li className="flex items-center gap-2"><Star className="w-4 h-4 text-warning" />Redeem 100 points = $1 off your next booking</li>
        </ul>
      </div>
    </div>
  )
}

function SecurityTab() {
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' })
  const [saving, setSaving] = useState(false)

  const handleChangePassword = async (e) => {
    e.preventDefault()
    if (form.new_password !== form.confirm_password) {
      toast.error('Passwords do not match')
      return
    }
    if (form.new_password.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }
    setSaving(true)
    try {
      await authApi.changePassword({ current_password: form.current_password, new_password: form.new_password })
      toast.success('Password changed successfully')
      setForm({ current_password: '', new_password: '', confirm_password: '' })
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to change password')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="max-w-lg">
      <div className="bg-white rounded-xl border p-6">
        <h3 className="font-heading font-bold text-lg mb-4">Change Password</h3>
        <form onSubmit={handleChangePassword} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Current Password</label>
            <input type="password" value={form.current_password}
              onChange={(e) => setForm({ ...form, current_password: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">New Password</label>
            <input type="password" value={form.new_password}
              onChange={(e) => setForm({ ...form, new_password: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm New Password</label>
            <input type="password" value={form.confirm_password}
              onChange={(e) => setForm({ ...form, confirm_password: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
          </div>
          <button type="submit" disabled={saving}
            className="bg-primary hover:bg-primary-dark text-white font-semibold px-6 py-2.5 rounded-lg text-sm transition-colors disabled:opacity-50">
            {saving ? 'Changing...' : 'Change Password'}
          </button>
        </form>
      </div>
    </div>
  )
}

function EmptyState({ message }) {
  return (
    <div className="text-center py-16">
      <div className="w-16 h-16 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <Eye className="w-8 h-8 text-gray-300" />
      </div>
      <p className="text-gray-400">{message}</p>
    </div>
  )
}
