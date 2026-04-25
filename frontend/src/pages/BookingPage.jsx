import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { loadStripe } from '@stripe/stripe-js'
import {
  Elements,
  CardElement,
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
import { nightsBetween, formatDate, formatCurrency } from '@/utils/formatters'
import { format } from 'date-fns'
import {
  Calendar, Users, CreditCard, Tag, Award, ChevronRight,
  ArrowLeft, CheckCircle, PlaneTakeoff,
} from 'lucide-react'

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLIC_KEY || '')

const CARD_ELEMENT_OPTIONS = {
  style: {
    base: {
      fontSize: '16px',
      color: '#1a1a2e',
      fontFamily: 'Inter, sans-serif',
      '::placeholder': { color: '#94a3b8' },
    },
    invalid: { color: '#ef4444' },
  },
}

export default function BookingPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { selectedRoom, hotel, checkIn, checkOut, guests, selectedTour, tourDate, selectedFlight, clearBooking } =
    useBookingStore()

  const isViatorTour = Boolean(selectedTour?.viator_product_code)
  const isFlightBooking = Boolean(selectedFlight?.duffel_offer_id)

  const [step, setStep] = useState('details') // 'details' | 'payment'
  const [bookingId, setBookingId] = useState(null)
  const [clientSecret, setClientSecret] = useState(null)
  const [paymentMethod, setPaymentMethod] = useState('stripe')

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
  const [pointsToRedeem, setPointsToRedeem] = useState('')
  const [loyaltyDiscount, setLoyaltyDiscount] = useState(0)
  const [pointsApplied, setPointsApplied] = useState(false)

  // Loading
  const [proceeding, setProceeding] = useState(false)
  const [vnpayLoading, setVnpayLoading] = useState(false)

  const effectiveCheckIn =
    dateRange.checkIn || (checkIn ? format(new Date(checkIn), 'yyyy-MM-dd') : '')
  const effectiveCheckOut =
    dateRange.checkOut || (checkOut ? format(new Date(checkOut), 'yyyy-MM-dd') : '')
  const nights = nightsBetween(effectiveCheckIn, effectiveCheckOut) || 1
  const subtotal = isFlightBooking
    ? (selectedFlight?.total_amount || 0)
    : isViatorTour
    ? (selectedTour?.price_per_person || 0) * (guests || 1)
    : (selectedRoom?.price_per_night || 0) * nights
  const taxes = Math.round(subtotal * 0.1 * 100) / 100
  const totalDiscount = (appliedVoucher?.discount_amount || 0) + loyaltyDiscount
  const finalTotal = Math.max(0, subtotal + taxes - totalDiscount)

  if (!isFlightBooking && !isViatorTour && (!selectedRoom || !hotel)) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <h2 className="text-xl font-bold text-gray-900 mb-2">No booking selected</h2>
        <p className="text-gray-500 mb-6">Please select a room, tour, or flight first.</p>
        <button
          onClick={() => navigate('/hotels/search')}
          className="bg-primary text-white px-6 py-2 rounded-lg"
        >
          Browse Hotels
        </button>
      </div>
    )
  }

  const handleApplyVoucher = async () => {
    if (!voucherInput.trim()) return
    setVoucherLoading(true)
    try {
      const res = await vouchersApi.validate(voucherInput.trim(), subtotal)
      if (res.data?.valid) {
        setAppliedVoucher({
          code: res.data.code,
          discount_amount: res.data.discount_amount,
        })
        toast.success(`Voucher applied — ${formatCurrency(res.data.discount_amount)} off`)
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
    toast.success(`${pts} points redeemed — ${formatCurrency(disc)} off`)
  }

  const handleProceedToPayment = async () => {
    if (!isFlightBooking && !isViatorTour && (!effectiveCheckIn || !effectiveCheckOut)) {
      toast.error('Please select check-in and check-out dates')
      return
    }
    if (isViatorTour && !tourDate) {
      toast.error('Please select a tour date')
      return
    }
    setProceeding(true)
    try {
      // 1. Create booking
      const isLiteapi = !isViatorTour && !isFlightBooking && Boolean(selectedRoom?.liteapi_rate_id)
      const bookingPayload = isFlightBooking
        ? {
            items: [{
              item_type: 'flight',
              duffel_offer_id: selectedFlight.duffel_offer_id,
              passenger: selectedFlight.passenger,
              quantity: 1,
            }],
            special_requests: form.special_requests || undefined,
            voucher_code: appliedVoucher?.code || undefined,
          }
        : isViatorTour
        ? {
            items: [{
              item_type: 'tour',
              viator_product_code: selectedTour.viator_product_code,
              viator_price: selectedTour.viator_price || selectedTour.price_per_person,
              viator_tour_name: selectedTour.name,
              tour_date: tourDate,
              quantity: guests || 1,
            }],
            special_requests: form.special_requests || undefined,
            voucher_code: appliedVoucher?.code || undefined,
          }
        : isLiteapi
        ? {
            items: [{
              item_type: 'room',
              liteapi_rate_id: selectedRoom.liteapi_rate_id,
              liteapi_hotel_id: selectedRoom.liteapi_hotel_id,
              liteapi_room_name: selectedRoom.name,
              liteapi_price: selectedRoom.liteapi_price,
              check_in: effectiveCheckIn,
              check_out: effectiveCheckOut,
              guests_count: guests || 1,
              quantity: 1,
            }],
            special_requests: form.special_requests || undefined,
            voucher_code: appliedVoucher?.code || undefined,
          }
        : {
            room_id: selectedRoom.id,
            check_in: effectiveCheckIn,
            check_out: effectiveCheckOut,
            guests_count: guests || 1,
            special_requests: form.special_requests || undefined,
            voucher_code: appliedVoucher?.code || undefined,
          }
      const bookingRes = await bookingsApi.create(bookingPayload)
      const bId = bookingRes.data?.id || bookingRes.data?.data?.id
      setBookingId(bId)

      // 2. Redeem loyalty points if applied
      if (pointsApplied && parseInt(pointsToRedeem, 10) > 0) {
        try {
          await loyaltyApi.redeem(parseInt(pointsToRedeem, 10), bId)
        } catch {
          toast.error('Could not redeem loyalty points — continuing without redemption')
          setLoyaltyDiscount(0)
          setPointsApplied(false)
        }
      }

      // 3. Create Stripe payment intent (for Stripe flow)
      const paymentRes = await paymentsApi.create({
        booking_id: bId,
        currency: 'usd',
      })
      setClientSecret(paymentRes.data?.data?.client_secret)

      setStep('payment')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create booking')
    } finally {
      setProceeding(false)
    }
  }

  const handleVnpayPay = async () => {
    setVnpayLoading(true)
    try {
      const res = await paymentsApi.createVnpayUrl({
        booking_id: bookingId,
        return_url: `${window.location.origin}/payments/vnpay/return`,
      })
      const url = res.data?.data?.payment_url
      if (url) {
        window.location.href = url
      } else {
        toast.error('Failed to get VNPay payment URL')
      }
    } catch {
      toast.error('Failed to create VNPay payment')
    } finally {
      setVnpayLoading(false)
    }
  }

  const handlePaymentSuccess = () => {
    clearBooking()
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
            isFlightBooking
              ? { label: 'Flights', to: '/flights' }
              : isViatorTour
              ? { label: 'Tours', to: '/tours' }
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
            {step === 'details' ? 'Complete Your Booking' : 'Payment'}
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
                stripe={stripePromise}
                options={{ clientSecret, appearance: { theme: 'stripe' } }}
              >
                <PaymentStep
                  paymentMethod={paymentMethod}
                  setPaymentMethod={setPaymentMethod}
                  clientSecret={clientSecret}
                  onSuccess={handlePaymentSuccess}
                  onVnpayPay={handleVnpayPay}
                  vnpayLoading={vnpayLoading}
                  finalTotal={finalTotal}
                />
              </Elements>
            )}
          </div>

          {/* Right: order summary */}
          <div className="lg:col-span-1">
            <div className="sticky top-20 bg-white border rounded-xl p-5 space-y-5">
              {isFlightBooking ? (
                <FlightOrderSummary flight={selectedFlight} />
              ) : (
                <>
                  <div className="flex gap-3">
                    <img
                      src={
                        isViatorTour
                          ? (selectedTour?.images?.[0] || 'https://placehold.co/80x80?text=Tour')
                          : (hotel?.images?.[0] || 'https://placehold.co/80x80?text=Hotel')
                      }
                      alt={isViatorTour ? selectedTour?.name : hotel?.name}
                      className="w-20 h-20 rounded-lg object-cover"
                    />
                    <div className="min-w-0">
                      <p className="font-bold text-sm line-clamp-1">
                        {isViatorTour ? selectedTour?.name : hotel?.name}
                      </p>
                      {!isViatorTour && <p className="text-xs text-gray-500">{selectedRoom?.name}</p>}
                      <p className="text-xs text-gray-400">
                        {isViatorTour ? selectedTour?.city : `${hotel?.city}, ${hotel?.country}`}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-gray-400" />
                      <span>
                        {isViatorTour
                          ? (tourDate ? formatDate(tourDate) : '---')
                          : `${effectiveCheckIn ? formatDate(effectiveCheckIn) : '---'} — ${effectiveCheckOut ? formatDate(effectiveCheckOut) : '---'}`}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Users className="w-4 h-4 text-gray-400" />
                      <span>
                        {guests || 1} guest{(guests || 1) > 1 ? 's' : ''}
                      </span>
                    </div>
                  </div>

                  <hr />

                  <PriceBreakdown
                    pricePerNight={isViatorTour ? (selectedTour?.price_per_person || 0) : (selectedRoom?.price_per_night || 0)}
                    nights={isViatorTour ? (guests || 1) : nights}
                    discount={totalDiscount}
                    labelOverride={isViatorTour ? 'per person' : undefined}
                  />
                </>
              )}

              {(appliedVoucher || pointsApplied) && (
                <div className="space-y-1 text-xs text-success bg-success/5 rounded-lg p-3">
                  {appliedVoucher && (
                    <p>✓ Voucher <strong>{appliedVoucher.code}</strong>: -{formatCurrency(appliedVoucher.discount_amount)}</p>
                  )}
                  {pointsApplied && loyaltyDiscount > 0 && (
                    <p>✓ {pointsToRedeem} loyalty pts: -{formatCurrency(loyaltyDiscount)}</p>
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

function FlightOrderSummary({ flight }) {
  if (!flight) return null
  const firstSlice = flight.slices?.[0]
  const pax = flight.passenger
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <PlaneTakeoff className="w-5 h-5 text-primary" />
        <span className="font-bold text-sm">{flight.airline_name}</span>
      </div>
      {flight.slices?.map((slice, i) => (
        <div key={i} className="text-sm text-gray-700">
          <span className="font-semibold">{slice.origin}</span>
          <span className="mx-1 text-gray-400">→</span>
          <span className="font-semibold">{slice.destination}</span>
          {slice.duration && <span className="text-xs text-gray-400 ml-2">{slice.duration}</span>}
        </div>
      ))}
      {pax && (
        <p className="text-xs text-gray-400">Passenger: {pax.first_name} {pax.last_name}</p>
      )}
      <hr />
      <div className="flex justify-between text-sm font-bold">
        <span>Total</span>
        <span>{formatCurrency(flight.total_amount, flight.currency)}</span>
      </div>
    </div>
  )
}

function DetailsStep({
  form, setForm, dateRange, setDateRange, effectiveCheckIn,
  voucherInput, setVoucherInput, appliedVoucher, onApplyVoucher, voucherLoading,
  loyaltyPoints, pointsToRedeem, setPointsToRedeem, loyaltyDiscount, pointsApplied, onApplyLoyalty,
  subtotal, onProceed, proceeding,
}) {
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
              {formatCurrency(appliedVoucher.discount_amount)} off
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
              onClick={onApplyVoucher}
              disabled={voucherLoading || !voucherInput.trim()}
              className="bg-primary text-white px-4 py-2.5 rounded-lg text-sm font-medium disabled:opacity-50 hover:bg-primary/90 transition-colors"
            >
              {voucherLoading ? '...' : 'Apply'}
            </button>
          </div>
        )}
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
                {pointsToRedeem} pts redeemed — {formatCurrency(loyaltyDiscount)} off
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

function PaymentStep({
  paymentMethod, setPaymentMethod, clientSecret,
  onSuccess, onVnpayPay, vnpayLoading, finalTotal,
}) {
  return (
    <div className="space-y-6">
      {/* Payment method selector */}
      <div className="bg-white rounded-xl border p-6">
        <h2 className="font-heading font-bold text-lg mb-4">Choose Payment Method</h2>
        <div className="grid grid-cols-2 gap-3">
          <button
            onClick={() => setPaymentMethod('stripe')}
            className={`border-2 rounded-xl p-4 text-sm font-medium transition-colors ${
              paymentMethod === 'stripe'
                ? 'border-primary bg-primary/5 text-primary'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            <CreditCard className="w-6 h-6 mx-auto mb-2" />
            Credit / Debit Card
            <p className="text-xs font-normal text-gray-400 mt-1">Visa, Mastercard, Amex</p>
          </button>
          <button
            onClick={() => setPaymentMethod('vnpay')}
            className={`border-2 rounded-xl p-4 text-sm font-medium transition-colors ${
              paymentMethod === 'vnpay'
                ? 'border-primary bg-primary/5 text-primary'
                : 'border-gray-200 text-gray-600 hover:border-gray-300'
            }`}
          >
            <span className="text-2xl mx-auto mb-2 block text-center">🏦</span>
            VNPay
            <p className="text-xs font-normal text-gray-400 mt-1">ATM, QR, Internet Banking</p>
          </button>
        </div>
      </div>

      {/* Stripe card form */}
      {paymentMethod === 'stripe' && (
        <StripeCardForm
          clientSecret={clientSecret}
          onSuccess={onSuccess}
          finalTotal={finalTotal}
        />
      )}

      {/* VNPay button */}
      {paymentMethod === 'vnpay' && (
        <div className="bg-white rounded-xl border p-6 space-y-4">
          <h2 className="font-heading font-bold text-lg">Pay with VNPay</h2>
          <p className="text-sm text-gray-500">
            You will be redirected to VNPay's secure payment page. Amount:{' '}
            <strong>{Math.round(finalTotal * 25000).toLocaleString('vi-VN')} ₫</strong>
          </p>
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-700">
            <strong>Test card:</strong> NCB — 9704198526191432198 &nbsp;|&nbsp; OTP: 123456
          </div>
          <button
            onClick={onVnpayPay}
            disabled={vnpayLoading}
            className="w-full bg-primary hover:bg-primary/90 disabled:bg-gray-300 text-white font-bold py-4 rounded-xl transition-colors flex items-center justify-center gap-2"
          >
            {vnpayLoading ? 'Redirecting...' : 'Pay with VNPay →'}
          </button>
        </div>
      )}
    </div>
  )
}

function StripeCardForm({ clientSecret, onSuccess, finalTotal }) {
  const stripe = useStripe()
  const elements = useElements()
  const [paying, setPaying] = useState(false)
  const [cardError, setCardError] = useState('')

  const handlePay = async (e) => {
    e.preventDefault()
    if (!stripe || !elements) return

    setCardError('')
    setPaying(true)

    const cardElement = elements.getElement(CardElement)
    const { error, paymentIntent } = await stripe.confirmCardPayment(clientSecret, {
      payment_method: { card: cardElement },
    })

    if (error) {
      setCardError(error.message)
      setPaying(false)
    } else if (paymentIntent.status === 'succeeded') {
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
        <div className="border rounded-lg px-4 py-3">
          <CardElement options={CARD_ELEMENT_OPTIONS} />
        </div>

        {cardError && (
          <p className="text-sm text-error">{cardError}</p>
        )}

        <button
          type="submit"
          disabled={!stripe || paying}
          className="w-full bg-accent hover:bg-accent/90 disabled:bg-gray-300 text-white font-bold py-4 rounded-xl transition-colors flex items-center justify-center gap-2 text-base"
        >
          <CreditCard className="w-5 h-5" />
          {paying ? 'Processing...' : `Pay ${formatCurrency(finalTotal)}`}
        </button>
      </form>
    </div>
  )
}
