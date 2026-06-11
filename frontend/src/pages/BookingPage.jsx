import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { loadStripe } from '@stripe/stripe-js'
import {
  Elements,
  PaymentElement,
  useStripe,
  useElements,
} from '@stripe/react-stripe-js'
import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import { bookingsApi } from '@/api/bookingsApi'
import { paymentsApi } from '@/api/paymentsApi'
import { vouchersApi } from '@/api/vouchersApi'
import { loyaltyApi } from '@/api/loyaltyApi'
import PriceBreakdown from '@/components/common/PriceBreakdown'
import Breadcrumb from '@/components/common/Breadcrumb'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { useTranslation } from 'react-i18next'
import { nightsBetween, formatDate } from '@/utils/formatters'
import { format } from 'date-fns'
import {
  Calendar, Users, CreditCard, Tag, Award, ChevronRight,
  ArrowLeft, CheckCircle,
} from 'lucide-react'

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLIC_KEY || '')

export default function BookingPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { user } = useAuth()
  const {
    selectedRoom, hotel, checkIn, checkOut, guests, adults, childAges,
    selectedTour, tourDate, clearBooking,
    selectedItems,
  } = useBookingStore()
  const effectiveAdults = adults || guests || 1
  const effectiveChildAges = childAges || []

  const { t } = useTranslation('booking')
  const { t: tHotel } = useTranslation('hotels')
  const fmt = useFormatCurrency()
  const isViatorTour = Boolean(selectedTour?.viator_product_code)
  const isRegularTour = Boolean(selectedTour && !selectedTour.viator_product_code)
  // Flights use their own checkout (see FlightCheckoutPage). This page only
  // handles hotels + tours; if a flight ever lands here it's a routing bug.
  const isMultiRoom = Array.isArray(selectedItems) && selectedItems.length > 1

  // Multi-room reservations from the recommendation widget aren't supported yet.
  // Show a placeholder + toast so the user can navigate back without a broken flow.
  useEffect(() => {
    if (isMultiRoom) toast.info(tHotel('detail.multiRoomCheckoutComingSoon'))
  }, [isMultiRoom, tHotel])

  const [step, setStep] = useState('details') // 'details' | 'payment'
  const [bookingId, setBookingId] = useState(null)
  const [stripePaymentId, setStripePaymentId] = useState(null)
  const [clientSecret, setClientSecret] = useState(null)

  const [form, setForm] = useState({
    full_name: user?.full_name || '',
    email: user?.email || '',
    phone: user?.phone || '',
    special_requests: '',
  })
  const [dateRange, setDateRange] = useState({
    checkIn: checkIn ? format(new Date(checkIn), 'yyyy-MM-dd') : '',
    checkOut: checkOut ? format(new Date(checkOut), 'yyyy-MM-dd') : '',
  })

  // Voucher state
  const [voucherInput, setVoucherInput] = useState('')
  const [appliedVoucher, setAppliedVoucher] = useState(null) // { code, discount_amount }
  const [voucherLoading, setVoucherLoading] = useState(false)

  // Loyalty state
  const [loyaltyPoints, setLoyaltyPoints] = useState(user?.loyalty_points || 0)
  const [loyaltyTier, setLoyaltyTier] = useState(null) // { name, discount_percent }
  const [pointsToRedeem, setPointsToRedeem] = useState('')
  const [loyaltyDiscount, setLoyaltyDiscount] = useState(0)
  const [pointsApplied, setPointsApplied] = useState(false)

  useEffect(() => {
    loyaltyApi.getStatus().then((res) => {
      const data = res.data
      if (data?.total_points !== undefined) setLoyaltyPoints(data.total_points)
      if (data?.current_tier) setLoyaltyTier(data.current_tier)
    }).catch(() => {})
  }, [])

  // Loading
  const [proceeding, setProceeding] = useState(false)

  const effectiveCheckIn =
    dateRange.checkIn || (checkIn ? format(new Date(checkIn), 'yyyy-MM-dd') : '')
  const effectiveCheckOut =
    dateRange.checkOut || (checkOut ? format(new Date(checkOut), 'yyyy-MM-dd') : '')
  const nights = nightsBetween(effectiveCheckIn, effectiveCheckOut) || 1

  // Sum price × quantity across all selected items (handles multi-room recommendations).
  // Falls back to selectedRoom.price_per_night for legacy single-room bookings.
  const roomRateTotal = selectedItems?.length > 0
    ? selectedItems.reduce((sum, it) => sum + (it.price || 0) * (it.quantity || 1), 0)
    : (selectedRoom?.price_per_night || 0)

  const subtotal = (isViatorTour || isRegularTour)
    ? (selectedTour?.price_per_person || 0) * (guests || 1)
    : roomRateTotal * nights
  const taxes = Math.round(subtotal * 0.1 * 100) / 100
  const tierDiscountPct = loyaltyTier?.discount_percent || 0
  const tierDiscount = tierDiscountPct > 0 ? Math.round(subtotal * tierDiscountPct / 100 * 100) / 100 : 0
  const totalDiscount = tierDiscount + (appliedVoucher?.discount_amount || 0) + loyaltyDiscount
  const finalTotal = Math.max(0, subtotal + taxes - totalDiscount)

  if (!isViatorTour && !isRegularTour && (!selectedRoom || !hotel)) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <h2 className="text-xl font-bold text-gray-900 mb-2">No booking selected</h2>
        <p className="text-gray-500 mb-6">Please select a room or tour first.</p>
        <button
          onClick={() => navigate('/hotels/search')}
          className="bg-primary text-white px-6 py-2 rounded-lg"
        >
          Browse Hotels
        </button>
      </div>
    )
  }

  if (isMultiRoom) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <h2 className="text-xl font-bold text-gray-900 mb-3">{hotel?.name}</h2>
        <p className="text-gray-600 mb-6">{tHotel('detail.multiRoomCheckoutComingSoon')}</p>
        <ul className="text-left max-w-md mx-auto bg-gray-50 rounded-lg p-4 mb-6 text-sm">
          {selectedItems.map((it, i) => (
            <li key={i} className="flex justify-between border-b last:border-b-0 border-gray-200 py-1.5">
              <span>
                {it.quantity} × {it.room_name}
              </span>
              <span className="font-semibold">{fmt((it.price || 0) * it.quantity * nights)}</span>
            </li>
          ))}
        </ul>
        <button
          onClick={() => navigate(-1)}
          className="bg-primary text-white px-6 py-2 rounded-lg"
        >
          <ArrowLeft className="inline w-4 h-4 mr-1" /> Back
        </button>
      </div>
    )
  }

  const handleApplyVoucher = async (codeArg) => {
    const code = (typeof codeArg === 'string' ? codeArg : voucherInput).trim()
    if (!code) return
    setVoucherInput(code)
    setVoucherLoading(true)
    try {
      const res = await vouchersApi.validate(code, subtotal)
      if (res.data?.valid) {
        setAppliedVoucher({
          code: res.data.code,
          discount_amount: res.data.discount_amount,
        })
        toast.success(`Voucher applied — ${fmt(res.data.discount_amount)} off`)
      } else {
        toast.error(res.data?.message || 'Invalid voucher')
      }
    } catch {
      toast.error('Failed to validate voucher')
    } finally {
      setVoucherLoading(false)
    }
  }

  const handleApplyLoyalty = () => {
    const pts = parseInt(pointsToRedeem, 10)
    if (!pts || pts <= 0) { toast.error('Enter a valid number of points'); return }
    if (pts > loyaltyPoints) { toast.error('Insufficient loyalty points'); return }
    const disc = pts * 0.01
    setLoyaltyDiscount(disc)
    setPointsApplied(true)
    toast.success(`${pts} points redeemed — ${fmt(disc)} off`)
  }

  const handleProceedToPayment = async () => {
    // FE-05: validate guest details client-side before creating anything.
    if (!form.full_name?.trim()) {
      toast.error('Please enter the guest full name')
      return
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email?.trim() || '')) {
      toast.error('Please enter a valid email address')
      return
    }
    if (!form.phone?.trim()) {
      toast.error('Please enter a contact phone number')
      return
    }
    if (!isViatorTour && !isRegularTour && (!effectiveCheckIn || !effectiveCheckOut)) {
      toast.error('Please select check-in and check-out dates')
      return
    }
    if (!isViatorTour && !isRegularTour && effectiveCheckOut <= effectiveCheckIn) {
      toast.error('Check-out date must be after check-in date')
      return
    }
    if ((isViatorTour || isRegularTour) && !tourDate) {
      toast.error('Please select a tour date')
      return
    }
    if ((isViatorTour || isRegularTour) && tourDate < format(new Date(), 'yyyy-MM-dd')) {
      toast.error('Tour date cannot be in the past')
      return
    }
    setProceeding(true)
    try {
      // 1. Create booking
      const isLiteapi = !isViatorTour && !isRegularTour && Boolean(selectedRoom?.liteapi_rate_id)
      // Tour occupancy: prefer the explicit adults/childAges set by the
      // detail page; fall back to (guests, 0) for older stored values.
      const tourAdults = effectiveAdults || guests || 1
      const tourChildren = effectiveChildAges
      const bookingPayload = isViatorTour
        ? {
            items: [{
              item_type: 'tour',
              viator_product_code: selectedTour.viator_product_code,
              viator_price: selectedTour.viator_price || selectedTour.price_per_person,
              viator_tour_name: selectedTour.name,
              viator_tour_image_url: selectedTour.images?.[0] || undefined,
              tour_date: tourDate,
              quantity: tourAdults + tourChildren.length,
              adults: tourAdults,
              children_ages: tourChildren,
            }],
            special_requests: form.special_requests || undefined,
            voucher_code: appliedVoucher?.code || undefined,
            points_to_redeem: pointsApplied && parseInt(pointsToRedeem, 10) > 0 ? parseInt(pointsToRedeem, 10) : 0,
          }
        : isRegularTour
        ? {
            items: [{
              item_type: 'tour',
              tour_id: selectedTour.id,
              tour_date: tourDate,
              quantity: tourAdults + tourChildren.length,
              adults: tourAdults,
              children_ages: tourChildren,
            }],
            special_requests: form.special_requests || undefined,
            voucher_code: appliedVoucher?.code || undefined,
            points_to_redeem: pointsApplied && parseInt(pointsToRedeem, 10) > 0 ? parseInt(pointsToRedeem, 10) : 0,
          }
        : isLiteapi
        ? {
            items: [{
              item_type: 'room',
              liteapi_rate_id: selectedRoom.liteapi_rate_id,
              liteapi_hotel_id: selectedRoom.liteapi_hotel_id,
              liteapi_hotel_name: hotel?.name || undefined,
              liteapi_hotel_image_url: hotel?.images?.[0] || undefined,
              liteapi_room_name: selectedRoom.name,
              liteapi_price: selectedRoom.liteapi_price,
              check_in: effectiveCheckIn,
              check_out: effectiveCheckOut,
              guests_count: effectiveAdults + effectiveChildAges.length,
              adults: effectiveAdults,
              children_ages: effectiveChildAges,
              quantity: 1,
            }],
            special_requests: form.special_requests || undefined,
            voucher_code: appliedVoucher?.code || undefined,
            points_to_redeem: pointsApplied && parseInt(pointsToRedeem, 10) > 0 ? parseInt(pointsToRedeem, 10) : 0,
          }
        : {
            items: [{
              item_type: 'room',
              room_id: selectedRoom.id,
              check_in: effectiveCheckIn,
              check_out: effectiveCheckOut,
              guests_count: effectiveAdults + effectiveChildAges.length,
              adults: effectiveAdults,
              children_ages: effectiveChildAges,
              quantity: 1,
            }],
            special_requests: form.special_requests || undefined,
            voucher_code: appliedVoucher?.code || undefined,
            points_to_redeem: pointsApplied && parseInt(pointsToRedeem, 10) > 0 ? parseInt(pointsToRedeem, 10) : 0,
          }
      const bookingRes = await bookingsApi.create(bookingPayload)
      const bId = bookingRes.data?.id || bookingRes.data?.data?.id
      // FE-03: fail loudly instead of silently carrying an undefined id
      // into the payment-intent call.
      if (!bId) throw new Error('Booking creation failed — no booking id returned')
      setBookingId(bId)

      // Loyalty points are redeemed as part of booking creation (points_to_redeem
      // in the payload above): the backend deducts them, applies the discount to
      // booking.total_price so Stripe charges the reduced amount, and reverses
      // them automatically if the pending booking is never paid. No separate
      // redeem call here — that would double-deduct and leave total_price stale.

      // 2. Create Stripe payment intent (for Stripe flow)
      const paymentRes = await paymentsApi.create({
        booking_id: bId,
        currency: 'usd',
      })
      const clientSecret = paymentRes.data?.data?.client_secret
      const stripePaymentId = paymentRes.data?.data?.payment_id
      // FE-03: don't switch to the payment step with a broken Stripe element.
      if (!clientSecret || !stripePaymentId) {
        throw new Error('Failed to start payment — please try again')
      }
      setClientSecret(clientSecret)
      setStripePaymentId(stripePaymentId)

      setStep('payment')
    } catch (err) {
      const detail = err.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : (detail?.message || 'Failed to create booking')
      toast.error(msg)
    } finally {
      setProceeding(false)
    }
  }

  const handlePaymentSuccess = (failure = null) => {
    clearBooking()
    // Bust the My Bookings cache so the user sees their fresh booking
    // immediately when they navigate to /profile?tab=bookings. Without this,
    // the global staleTime of 5min on the queryClient (main.jsx) keeps showing
    // the stale list and the new booking only appears after a hard refresh.
    qc.invalidateQueries({ queryKey: ['my-bookings'] })
    if (failure) {
      // Payment captured but supplier booking failed — the backend has already
      // attempted a refund. Route to the failure page so the user understands.
      navigate(`/bookings/${bookingId}/failure`, { state: { failure } })
      return
    }
    toast.success('Payment successful!')
    navigate(`/bookings/${bookingId}/confirmation`)
  }

  return (
    <>
      <Helmet>
        <title>Complete Booking — TravelBooking</title>
      </Helmet>
      <div className="max-w-6xl mx-auto px-4 py-6">
        <Breadcrumb
          items={[
            { label: 'Home', to: '/' },
            (isViatorTour || isRegularTour)
              ? { label: selectedTour?.name || 'Tour', to: selectedTour?.id ? `/tours/${selectedTour.id}` : '/tours' }
              : { label: hotel?.name || 'Hotel', to: hotel?.id ? `/hotels/${hotel.id}` : '/hotels/search' },
            { label: 'Booking' },
          ]}
        />

        <div className="flex items-center gap-4 mb-6">
          {step === 'payment' && (
            <button
              onClick={() => setStep('details')}
              className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
          )}
          <h1 className="font-heading text-2xl font-bold">
            {step === 'details' ? t('page.title') : t('payment.title')}
          </h1>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-2 mb-6 text-sm">
          <div className={`flex items-center gap-1.5 font-medium ${step === 'details' ? 'text-primary' : 'text-success'}`}>
            {step === 'payment' ? <CheckCircle className="w-4 h-4" /> : <span className="w-5 h-5 rounded-full bg-primary text-white flex items-center justify-center text-xs">1</span>}
            Details
          </div>
          <ChevronRight className="w-4 h-4 text-gray-400" />
          <div className={`flex items-center gap-1.5 font-medium ${step === 'payment' ? 'text-primary' : 'text-gray-400'}`}>
            <span className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${step === 'payment' ? 'bg-primary text-white' : 'bg-gray-200 text-gray-500'}`}>2</span>
            Payment
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left: step content */}
          <div className="lg:col-span-2 space-y-6">
            {step === 'details' && (
              <DetailsStep
                form={form}
                setForm={setForm}
                dateRange={dateRange}
                setDateRange={setDateRange}
                effectiveCheckIn={effectiveCheckIn}
                voucherInput={voucherInput}
                setVoucherInput={setVoucherInput}
                appliedVoucher={appliedVoucher}
                onApplyVoucher={handleApplyVoucher}
                voucherLoading={voucherLoading}
                loyaltyPoints={loyaltyPoints}
                pointsToRedeem={pointsToRedeem}
                setPointsToRedeem={setPointsToRedeem}
                loyaltyDiscount={loyaltyDiscount}
                pointsApplied={pointsApplied}
                onApplyLoyalty={handleApplyLoyalty}
                subtotal={subtotal}
                onProceed={handleProceedToPayment}
                proceeding={proceeding}
              />
            )}

            {step === 'payment' && clientSecret && (
              <Elements
                key={clientSecret}
                stripe={stripePromise}
                options={{ clientSecret, appearance: { theme: 'stripe' } }}
              >
                <StripeCardForm
                  stripePaymentId={stripePaymentId}
                  onSuccess={handlePaymentSuccess}
                  finalTotal={finalTotal}
                />
              </Elements>
            )}
          </div>

          {/* Right: order summary */}
          <div className="lg:col-span-1">
            <div className="sticky top-20 bg-white border rounded-xl p-5 space-y-5">
              <div className="flex gap-3">
                <img
                  src={
                    (isViatorTour || isRegularTour)
                      ? (selectedTour?.images?.[0] || 'https://placehold.co/80x80?text=Tour')
                      : (hotel?.images?.[0] || 'https://placehold.co/80x80?text=Hotel')
                  }
                  alt={(isViatorTour || isRegularTour) ? selectedTour?.name : hotel?.name}
                  className="w-20 h-20 rounded-lg object-cover"
                />
                <div className="min-w-0">
                  <p className="font-bold text-sm line-clamp-1">
                    {(isViatorTour || isRegularTour) ? selectedTour?.name : hotel?.name}
                  </p>
                  {!(isViatorTour || isRegularTour) && <p className="text-xs text-gray-500">{selectedRoom?.name}</p>}
                  <p className="text-xs text-gray-400">
                    {(isViatorTour || isRegularTour) ? selectedTour?.city : `${hotel?.city}, ${hotel?.country}`}
                  </p>
                </div>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-gray-400" />
                  <span>
                    {(isViatorTour || isRegularTour)
                      ? (tourDate ? formatDate(tourDate) : '---')
                      : `${effectiveCheckIn ? formatDate(effectiveCheckIn) : '---'} — ${effectiveCheckOut ? formatDate(effectiveCheckOut) : '---'}`}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-gray-400" />
                  <span>
                    {effectiveAdults} adult{effectiveAdults > 1 ? 's' : ''}
                    {effectiveChildAges.length > 0 && (
                      <>
                        {' '}· {effectiveChildAges.length} child
                        {effectiveChildAges.length > 1 ? 'ren' : ''}{' '}
                        ({effectiveChildAges.join(', ')} y/o)
                      </>
                    )}
                  </span>
                </div>
              </div>

              <hr />

              <PriceBreakdown
                pricePerNight={(isViatorTour || isRegularTour) ? (selectedTour?.price_per_person || 0) : roomRateTotal}
                nights={(isViatorTour || isRegularTour) ? (guests || 1) : nights}
                discount={totalDiscount}
                tierDiscount={tierDiscount}
                tierName={loyaltyTier?.name}
                tierDiscountPct={tierDiscountPct}
                labelOverride={(isViatorTour || isRegularTour) ? 'per person' : undefined}
              />

              {(tierDiscount > 0 || appliedVoucher || pointsApplied) && (
                <div className="space-y-1 text-xs text-success bg-success/5 rounded-lg p-3">
                  {tierDiscount > 0 && (
                    <p>✓ {loyaltyTier?.name} member discount ({tierDiscountPct}%): -{fmt(tierDiscount)}</p>
                  )}
                  {appliedVoucher && (
                    <p>✓ Voucher <strong>{appliedVoucher.code}</strong>: -{fmt(appliedVoucher.discount_amount)}</p>
                  )}
                  {pointsApplied && loyaltyDiscount > 0 && (
                    <p>✓ {pointsToRedeem} loyalty pts: -{fmt(loyaltyDiscount)}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function DetailsStep({
  form, setForm, dateRange, setDateRange, effectiveCheckIn,
  voucherInput, setVoucherInput, appliedVoucher, onApplyVoucher, voucherLoading,
  loyaltyPoints, pointsToRedeem, setPointsToRedeem, loyaltyDiscount, pointsApplied, onApplyLoyalty,
  subtotal, onProceed, proceeding,
}) {
  const fmt = useFormatCurrency()
  return (
    <>
      {/* Guest details */}
      <div className="bg-white rounded-xl border p-6 space-y-5">
        <h2 className="font-heading font-bold text-lg">Guest Details</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
            <input
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Phone</label>
            <input
              value={form.phone}
              onChange={(e) => setForm({ ...form, phone: e.target.value })}
              className="w-full border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Special Requests
          </label>
          <textarea
            value={form.special_requests}
            onChange={(e) => setForm({ ...form, special_requests: e.target.value })}
            className="w-full border rounded-lg px-4 py-3 text-sm resize-none h-20 focus:outline-none focus:ring-2 focus:ring-primary/30"
            placeholder="Any special requests? (optional)"
          />
        </div>
      </div>

      {/* Stay dates */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="font-heading font-bold text-lg flex items-center gap-2">
          <Calendar className="w-5 h-5" /> Stay Dates
        </h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Check-in</label>
            <input
              type="date"
              value={dateRange.checkIn}
              onChange={(e) => setDateRange({ ...dateRange, checkIn: e.target.value })}
              min={format(new Date(), 'yyyy-MM-dd')}
              className="w-full border rounded-lg px-4 py-2.5 text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Check-out</label>
            <input
              type="date"
              value={dateRange.checkOut}
              onChange={(e) => setDateRange({ ...dateRange, checkOut: e.target.value })}
              min={dateRange.checkIn || format(new Date(), 'yyyy-MM-dd')}
              className="w-full border rounded-lg px-4 py-2.5 text-sm"
            />
          </div>
        </div>
      </div>

      {/* Voucher */}
      <div className="bg-white rounded-xl border p-6 space-y-4">
        <h2 className="font-heading font-bold text-lg flex items-center gap-2">
          <Tag className="w-5 h-5" /> Voucher Code
        </h2>
        {appliedVoucher ? (
          <div className="flex items-center gap-3 bg-success/10 rounded-lg p-3">
            <CheckCircle className="w-4 h-4 text-success shrink-0" />
            <div className="flex-1 text-sm">
              <span className="font-semibold">{appliedVoucher.code}</span> applied —{' '}
              {fmt(appliedVoucher.discount_amount)} off
            </div>
            <button
              onClick={() => { setVoucherInput('') }}
              className="text-xs text-gray-400 hover:text-gray-600"
            >
              Remove
            </button>
          </div>
        ) : (
          <div className="flex gap-2">
            <input
              value={voucherInput}
              onChange={(e) => setVoucherInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onApplyVoucher()}
              placeholder="Enter voucher code"
              className="flex-1 border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <button
              onClick={() => onApplyVoucher()}
              disabled={voucherLoading || !voucherInput.trim()}
              className="bg-primary text-white px-4 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors"
            >
              {voucherLoading ? '...' : 'Apply'}
            </button>
          </div>
        )}
        {!appliedVoucher && <AvailableVoucherPicker onPick={onApplyVoucher} />}
      </div>

      {/* Loyalty points */}
      {loyaltyPoints > 0 && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <h2 className="font-heading font-bold text-lg flex items-center gap-2">
            <Award className="w-5 h-5 text-warning" /> Loyalty Points
          </h2>
          <p className="text-sm text-gray-600">
            You have <strong className="text-primary">{loyaltyPoints} points</strong> (1 pt = $0.01 discount)
          </p>
          {pointsApplied ? (
            <div className="flex items-center gap-3 bg-success/10 rounded-lg p-3 text-sm">
              <CheckCircle className="w-4 h-4 text-success shrink-0" />
              <span>
                {pointsToRedeem} pts redeemed — {fmt(loyaltyDiscount)} off
              </span>
            </div>
          ) : (
            <div className="flex gap-2 items-center">
              <input
                type="number"
                value={pointsToRedeem}
                onChange={(e) => setPointsToRedeem(e.target.value)}
                placeholder="Points to redeem"
                min={1}
                max={loyaltyPoints}
                className="flex-1 border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
              <button
                onClick={onApplyLoyalty}
                disabled={!pointsToRedeem}
                className="bg-warning text-white px-4 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-warning/90 transition-colors"
              >
                Redeem
              </button>
            </div>
          )}
        </div>
      )}

      <div className="bg-blue-50 rounded-xl p-4 text-sm text-primary">
        <strong>Free cancellation</strong> — Cancel before check-in and get a full refund.
      </div>

      <button
        onClick={onProceed}
        disabled={proceeding}
        className="w-full bg-accent hover:bg-accent/90 disabled:bg-gray-300 text-white font-bold py-4 rounded-xl transition-colors flex items-center justify-center gap-2 text-base"
      >
        <CreditCard className="w-5 h-5" />
        {proceeding ? 'Creating Booking...' : 'Proceed to Payment'}
      </button>
    </>
  )
}

function AvailableVoucherPicker({ onPick }) {
  const { data: vouchers } = useQuery({
    queryKey: ['available-vouchers'],
    queryFn: () => vouchersApi.available(),
    select: (res) => res.data || [],
  })
  if (!vouchers?.length) return null
  return (
    <div className="pt-1">
      <p className="text-xs text-gray-500 mb-1.5">Available vouchers</p>
      <div className="flex flex-wrap gap-2">
        {vouchers.slice(0, 6).map((v) => (
          <button key={v.code} type="button" onClick={() => onPick(v.code)}
            title={v.name}
            className="inline-flex items-center gap-1 border border-dashed border-primary/40 text-primary px-2.5 py-1 rounded-lg text-xs font-mono font-semibold hover:bg-primary/5">
            <Tag className="w-3 h-3" /> {v.code}
          </button>
        ))}
      </div>
    </div>
  )
}

function StripeCardForm({ stripePaymentId, onSuccess, finalTotal }) {
  const stripe = useStripe()
  const elements = useElements()
  const fmt = useFormatCurrency()
  const [paying, setPaying] = useState(false)
  const [cardError, setCardError] = useState('')

  const handlePay = async (e) => {
    e.preventDefault()
    if (!stripe || !elements) return

    setCardError('')
    setPaying(true)

    // PaymentElement reads the client secret from <Elements options.clientSecret>,
    // and `redirect: 'if_required'` keeps card flows in-page while still letting
    // 3DS / redirect-based methods (Apple Pay, etc.) work.
    const { error, paymentIntent } = await stripe.confirmPayment({
      elements,
      confirmParams: {},
      redirect: 'if_required',
    })

    if (error) {
      setCardError(error.message || 'Payment failed')
      setPaying(false)
      return
    }

    if (paymentIntent?.status === 'succeeded') {
      // Notify backend to confirm booking + award loyalty points. The backend
      // returns success=false when a supplier (e.g. Duffel) rejected the order
      // — in that case we route to the failure page so the user sees that
      // their payment was refunded.
      if (stripePaymentId) {
        try {
          const res = await paymentsApi.confirmStripe(stripePaymentId)
          const payload = res?.data?.data ?? res?.data
          const succeeded = res?.data?.success !== false
          if (!succeeded && payload) {
            onSuccess(payload)
            return
          }
        } catch {
          // Non-fatal — webhook will eventually retry. Treat as success
          // locally; the confirmation page can re-read the booking.
        }
      }
      onSuccess()
    } else {
      setCardError('Payment did not complete. Please try again.')
      setPaying(false)
    }
  }

  return (
    <div className="bg-white rounded-xl border p-6 space-y-5">
      <h2 className="font-heading font-bold text-lg">Card Details</h2>

      <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-xs text-blue-700">
        <strong>Test card:</strong> 4242 4242 4242 4242 &nbsp;|&nbsp; Any future date &nbsp;|&nbsp; Any CVC
      </div>

      <form onSubmit={handlePay} className="space-y-4">
        <PaymentElement options={{ layout: 'tabs' }} />

        {cardError && (
          <p className="text-sm text-error">{cardError}</p>
        )}

        <button
          type="submit"
          disabled={!stripe || paying}
          className="w-full bg-accent hover:bg-accent/90 disabled:bg-gray-300 text-white font-bold py-4 rounded-xl transition-colors flex items-center justify-center gap-2 text-base"
        >
          <CreditCard className="w-5 h-5" />
          {paying ? 'Processing...' : `Pay ${fmt(finalTotal)}`}
        </button>
      </form>
    </div>
  )
}
