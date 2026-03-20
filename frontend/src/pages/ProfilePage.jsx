import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { useAuth } from '@/hooks/useAuth'
import { bookingsApi } from '@/api/bookingsApi'
import { toursApi } from '@/api/toursApi'
import { reviewsApi } from '@/api/reviewsApi'
import { adminApi } from '@/api/adminApi'
import { authApi } from '@/api/authApi'
import BookingStatusBadge from '@/components/common/BookingStatusBadge'
import ReviewCard from '@/components/review/ReviewCard'
import Skeleton from '@/components/common/Skeleton'
import { formatDate, formatCurrency } from '@/utils/formatters'
import {
  User, Briefcase, Star, Heart, Award, Shield,
  Camera, Trash2, MapPin, Clock, Calendar, Eye,
} from 'lucide-react'

const TABS = [
  { key: 'profile', label: 'Profile', icon: User },
  { key: 'bookings', label: 'My Bookings', icon: Briefcase },
  { key: 'reviews', label: 'My Reviews', icon: Star },
  { key: 'wishlist', label: 'Wishlist', icon: Heart },
  { key: 'loyalty', label: 'Loyalty Points', icon: Award },
  { key: 'security', label: 'Security', icon: Shield },
]

export default function ProfilePage() {
  const [params, setParams] = useSearchParams()
  const activeTab = params.get('tab') || 'profile'
  const setTab = (t) => setParams({ tab: t })

  return (
    <>
      <Helmet><title>My Profile — TravelBooking</title></Helmet>
      <div className="bg-surface min-h-screen">
        <div className="max-w-6xl mx-auto px-4 py-8">
          <h1 className="font-heading text-2xl font-bold text-gray-900 mb-6">My Account</h1>

          <div className="flex gap-2 overflow-x-auto pb-4 mb-6 border-b">
            {TABS.map((t) => {
              const Icon = t.icon
              return (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors ${
                    activeTab === t.key
                      ? 'bg-primary text-white'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {t.label}
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
  const [subTab, setSubTab] = useState('hotels')
  const qc = useQueryClient()

  const { data: hotelBookings, isLoading: loadingHotel } = useQuery({
    queryKey: ['my-bookings'],
    queryFn: () => bookingsApi.list({ per_page: 50 }),
    select: (res) => res.data?.items || [],
  })

  const { data: tourBookings, isLoading: loadingTour } = useQuery({
    queryKey: ['my-tour-bookings'],
    queryFn: () => toursApi.listBookings({ per_page: 50 }),
    select: (res) => res.data?.items || [],
  })

  const cancelHotel = useMutation({
    mutationFn: (id) => bookingsApi.cancel(id),
    onSuccess: () => { toast.success('Booking cancelled'); qc.invalidateQueries({ queryKey: ['my-bookings'] }) },
    onError: () => toast.error('Failed to cancel'),
  })

  const cancelTour = useMutation({
    mutationFn: (id) => toursApi.cancelBooking(id),
    onSuccess: () => { toast.success('Tour booking cancelled'); qc.invalidateQueries({ queryKey: ['my-tour-bookings'] }) },
    onError: () => toast.error('Failed to cancel'),
  })

  return (
    <div>
      <div className="flex gap-2 mb-6">
        <button onClick={() => setSubTab('hotels')}
          className={`px-4 py-2 rounded-lg text-sm font-medium ${subTab === 'hotels' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}`}>
          Hotel Bookings
        </button>
        <button onClick={() => setSubTab('tours')}
          className={`px-4 py-2 rounded-lg text-sm font-medium ${subTab === 'tours' ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}`}>
          Tour Bookings
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
                  <div className="flex items-center gap-2 mb-1">
                    <p className="font-semibold text-sm truncate">{b.room?.name || 'Room'}</p>
                    <BookingStatusBadge status={b.status} />
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                    <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{formatDate(b.check_in)} — {formatDate(b.check_out)}</span>
                    <span>{b.guests_count} guest{b.guests_count > 1 ? 's' : ''}</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <p className="font-bold text-primary">{formatCurrency(b.total_price)}</p>
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
            {tourBookings.map((b) => (
              <div key={b.id} className="bg-white rounded-xl border p-5 flex flex-col md:flex-row md:items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <p className="font-semibold text-sm truncate">{b.tour?.name || 'Tour'}</p>
                    <BookingStatusBadge status={b.status} />
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                    <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{formatDate(b.tour_date)}</span>
                    <span>{b.participants_count} participant{b.participants_count > 1 ? 's' : ''}</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <p className="font-bold text-primary">{formatCurrency(b.total_price)}</p>
                  {b.status === 'pending' && (
                    <button onClick={() => cancelTour.mutate(b.id)}
                      className="text-error text-xs hover:underline">Cancel</button>
                  )}
                </div>
              </div>
            ))}
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

function LoyaltyTab() {
  const { user } = useAuth()
  const points = user?.loyalty_points || 0

  const tiers = [
    { name: 'Bronze', min: 0, color: 'bg-amber-600' },
    { name: 'Silver', min: 500, color: 'bg-gray-400' },
    { name: 'Gold', min: 1500, color: 'bg-yellow-500' },
    { name: 'Platinum', min: 5000, color: 'bg-purple-500' },
  ]

  const currentTier = tiers.filter((t) => points >= t.min).pop()
  const nextTier = tiers.find((t) => t.min > points)

  return (
    <div className="max-w-2xl space-y-6">
      <div className="bg-white rounded-xl border p-6 text-center">
        <div className={`w-16 h-16 rounded-full ${currentTier?.color} text-white flex items-center justify-center mx-auto mb-3`}>
          <Award className="w-8 h-8" />
        </div>
        <p className="text-sm text-gray-500">Current Tier</p>
        <p className="font-heading text-2xl font-bold">{currentTier?.name}</p>
        <p className="text-4xl font-bold text-primary mt-4">{points.toLocaleString()}</p>
        <p className="text-sm text-gray-500">loyalty points</p>
        {nextTier && (
          <div className="mt-6">
            <div className="flex justify-between text-xs text-gray-500 mb-1">
              <span>{currentTier?.name}</span>
              <span>{nextTier.name}</span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full transition-all"
                style={{ width: `${Math.min(((points - currentTier.min) / (nextTier.min - currentTier.min)) * 100, 100)}%` }}
              />
            </div>
            <p className="text-xs text-gray-500 mt-1">{nextTier.min - points} points to {nextTier.name}</p>
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl border p-6">
        <h3 className="font-heading font-bold mb-3">How to Earn Points</h3>
        <ul className="space-y-2 text-sm text-gray-600">
          <li className="flex items-center gap-2"><Star className="w-4 h-4 text-warning" />1 point per $1 spent on bookings</li>
          <li className="flex items-center gap-2"><Star className="w-4 h-4 text-warning" />50 bonus points for writing a review</li>
          <li className="flex items-center gap-2"><Star className="w-4 h-4 text-warning" />100 bonus points for referring a friend</li>
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
