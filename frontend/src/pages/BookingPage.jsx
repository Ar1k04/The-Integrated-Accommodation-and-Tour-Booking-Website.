import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import { bookingsApi } from '@/api/bookingsApi'
import { paymentsApi } from '@/api/paymentsApi'
import { adminApi } from '@/api/adminApi'
import PriceBreakdown from '@/components/common/PriceBreakdown'
import Breadcrumb from '@/components/common/Breadcrumb'
import { nightsBetween, formatDate, formatCurrency } from '@/utils/formatters'
import { format } from 'date-fns'
import { Calendar, Users, CreditCard, Tag } from 'lucide-react'

export default function BookingPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { selectedRoom, hotel, checkIn, checkOut, guests, promoCode, discount, applyPromo, clearBooking } = useBookingStore()

  const [form, setForm] = useState({
    full_name: user?.full_name || '',
    email: user?.email || '',
    phone: user?.phone || '',
    special_requests: '',
  })
  const [promoInput, setPromoInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [dateRange, setDateRange] = useState({
    checkIn: checkIn ? format(new Date(checkIn), 'yyyy-MM-dd') : '',
    checkOut: checkOut ? format(new Date(checkOut), 'yyyy-MM-dd') : '',
  })

  const effectiveCheckIn = dateRange.checkIn || (checkIn ? format(new Date(checkIn), 'yyyy-MM-dd') : '')
  const effectiveCheckOut = dateRange.checkOut || (checkOut ? format(new Date(checkOut), 'yyyy-MM-dd') : '')
  const nights = nightsBetween(effectiveCheckIn, effectiveCheckOut) || 1

  if (!selectedRoom || !hotel) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <h2 className="text-xl font-bold text-gray-900 mb-2">No room selected</h2>
        <p className="text-gray-500 mb-6">Please select a room from a hotel page first.</p>
        <button onClick={() => navigate('/hotels/search')} className="bg-primary text-white px-6 py-2 rounded-lg">
          Browse Hotels
        </button>
      </div>
    )
  }

  const handleValidatePromo = async () => {
    if (!promoInput) return
    try {
      const res = await adminApi.validatePromoCode({ code: promoInput, booking_amount: selectedRoom.price_per_night * nights })
      if (res.data.valid) {
        const disc = (selectedRoom.price_per_night * nights * res.data.discount_percent) / 100
        applyPromo(promoInput, disc)
        toast.success(res.data.message)
      } else {
        toast.error(res.data.message)
      }
    } catch {
      toast.error('Failed to validate promo code')
    }
  }

  const handleBook = async () => {
    if (!effectiveCheckIn || !effectiveCheckOut) {
      toast.error('Please select check-in and check-out dates')
      return
    }
    setLoading(true)
    try {
      const bookingRes = await bookingsApi.create({
        room_id: selectedRoom.id,
        check_in: effectiveCheckIn,
        check_out: effectiveCheckOut,
        guests_count: guests || 1,
        special_requests: form.special_requests || undefined,
        promo_code: promoCode || undefined,
      })
      const bookingId = bookingRes.data.id
      clearBooking()
      toast.success('Booking confirmed!')
      navigate(`/bookings/${bookingId}/confirmation`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Booking failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Helmet><title>Complete Booking — TravelBooking</title></Helmet>
      <div className="max-w-6xl mx-auto px-4 py-6">
        <Breadcrumb items={[{ label: 'Home', to: '/' }, { label: hotel.name, to: `/hotels/${hotel.id}` }, { label: 'Booking' }]} />

        <h1 className="font-heading text-2xl font-bold mb-6">Complete Your Booking</h1>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-xl border p-6 space-y-5">
              <h2 className="font-heading font-bold text-lg">Guest Details</h2>
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
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Special Requests</label>
                <textarea value={form.special_requests} onChange={(e) => setForm({ ...form, special_requests: e.target.value })}
                  className="w-full border rounded-lg px-4 py-3 text-sm resize-none h-20 focus:outline-none focus:ring-2 focus:ring-primary/30"
                  placeholder="Any special requests? (optional)" />
              </div>
            </div>

            <div className="bg-white rounded-xl border p-6 space-y-4">
              <h2 className="font-heading font-bold text-lg flex items-center gap-2"><Calendar className="w-5 h-5" /> Stay Dates</h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Check-in</label>
                  <input type="date" value={dateRange.checkIn}
                    onChange={(e) => setDateRange({ ...dateRange, checkIn: e.target.value })}
                    min={format(new Date(), 'yyyy-MM-dd')}
                    className="w-full border rounded-lg px-4 py-2.5 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Check-out</label>
                  <input type="date" value={dateRange.checkOut}
                    onChange={(e) => setDateRange({ ...dateRange, checkOut: e.target.value })}
                    min={dateRange.checkIn || format(new Date(), 'yyyy-MM-dd')}
                    className="w-full border rounded-lg px-4 py-2.5 text-sm" />
                </div>
              </div>
            </div>

            <div className="bg-blue-50 rounded-xl p-4 text-sm text-primary">
              <strong>Free cancellation</strong> — Cancel before check-in and get a full refund.
            </div>
          </div>

          {/* Right summary */}
          <div className="lg:col-span-1">
            <div className="sticky top-20 bg-white border rounded-xl p-5 space-y-5">
              <div className="flex gap-3">
                <img src={hotel.images?.[0] || 'https://placehold.co/80x80?text=Hotel'}
                  alt={hotel.name} className="w-20 h-20 rounded-lg object-cover" />
                <div className="min-w-0">
                  <p className="font-bold text-sm line-clamp-1">{hotel.name}</p>
                  <p className="text-xs text-gray-500">{selectedRoom.name}</p>
                  <p className="text-xs text-gray-400">{hotel.city}, {hotel.country}</p>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-gray-400" />
                  <span>{effectiveCheckIn ? formatDate(effectiveCheckIn) : '---'} — {effectiveCheckOut ? formatDate(effectiveCheckOut) : '---'}</span>
                </div>
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-gray-400" />
                  <span>{guests || 1} guest{(guests || 1) > 1 ? 's' : ''}</span>
                </div>
              </div>

              <hr />

              <PriceBreakdown pricePerNight={selectedRoom.price_per_night} nights={nights} discount={discount} />

              <div className="flex gap-2">
                <input value={promoInput} onChange={(e) => setPromoInput(e.target.value)}
                  placeholder="Promo code" className="flex-1 border rounded-lg px-3 py-2 text-sm" />
                <button onClick={handleValidatePromo}
                  className="bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded-lg text-sm font-medium flex items-center gap-1">
                  <Tag className="w-4 h-4" /> Apply
                </button>
              </div>

              <button onClick={handleBook} disabled={loading}
                className="w-full bg-accent hover:bg-accent-dark disabled:bg-gray-300 text-white font-bold py-3.5 rounded-lg transition-colors flex items-center justify-center gap-2">
                <CreditCard className="w-5 h-5" />
                {loading ? 'Processing...' : 'Complete Booking'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
