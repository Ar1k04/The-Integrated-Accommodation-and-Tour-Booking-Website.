import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { loadStripe } from '@stripe/stripe-js'
import {
  Elements, PaymentElement, useStripe, useElements,
} from '@stripe/react-stripe-js'
import {
  PlaneTakeoff, ArrowRight, Tag, Award, CreditCard,
  Ticket, Clock, AlertCircle, ArrowLeft, CheckCircle,
} from 'lucide-react'

import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import { bookingsApi } from '@/api/bookingsApi'
import { paymentsApi } from '@/api/paymentsApi'
import { vouchersApi } from '@/api/vouchersApi'
import { loyaltyApi } from '@/api/loyaltyApi'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import Breadcrumb from '@/components/common/Breadcrumb'

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLIC_KEY || '')

const fmtDuration = (iso) => {
  if (!iso) return ''
  return String(iso).replace('PT', '').toLowerCase()
}

const fmtTime = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch { return '' }
}

const fmtDate = (iso) => {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })
  } catch { return '' }
}

export default function FlightCheckoutPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { user } = useAuth()
  const { selectedFlight, clearBooking } = useBookingStore()
  const fmt = useFormatCurrency()

  // ── Guard: must come from offer detail page ─────────────────────────────
  // After successful payment we deliberately clearBooking() — that nukes
  // selectedFlight and would re-trigger this redirect, racing the navigate
  // to the confirmation page. The completedRef short-circuits the guard
  // once we've sent the user to /bookings/:id/confirmation.
  const completedRef = useRef(false)
  useEffect(() => {
    if (completedRef.current) return
    if (!selectedFlight?.duffel_offer_id) {
      toast.info('Please select a flight first')
      navigate('/flights')
    }
  }, [selectedFlight, navigate])

  // ── Form / step state ────────────────────────────────────────────────────
  const [step, setStep] = useState('review') // 'review' | 'payment'
  const [bookingId, setBookingId] = useState(null)
  const [stripePaymentId, setStripePaymentId] = useState(null)
  const [clientSecret, setClientSecret] = useState(null)
  const [specialRequests, setSpecialRequests] = useState('')
  const [proceeding, setProceeding] = useState(false)

  // ── Voucher / loyalty (same UX as hotel checkout) ───────────────────────
  const [voucherInput, setVoucherInput] = useState('')
  const [appliedVoucher, setAppliedVoucher] = useState(null)
  const [voucherLoading, setVoucherLoading] = useState(false)

  const [loyaltyPoints, setLoyaltyPoints] = useState(user?.loyalty_points || 0)
  const [loyaltyTier, setLoyaltyTier] = useState(null)
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

  // ── Live offer-expiry countdown ─────────────────────────────────────────
  const [secondsLeft, setSecondsLeft] = useState(null)
  useEffect(() => {
    const expiresAt = selectedFlight?.expires_at
    if (!expiresAt) return undefined
    const compute = () => {
      try {
        setSecondsLeft(Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000))
      } catch { setSecondsLeft(null) }
    }
    compute()
    const id = setInterval(compute, 1000)
    return () => clearInterval(id)
  }, [selectedFlight?.expires_at])

  useEffect(() => {
    if (secondsLeft != null && secondsLeft <= 0) {
      toast.error('Flight offer has expired — please search again')
      navigate('/flights')
    }
  }, [secondsLeft, navigate])

  if (!selectedFlight?.duffel_offer_id) return null

  // ── Pricing ─────────────────────────────────────────────────────────────
  const subtotal = Number(selectedFlight.total_amount || 0)
  const currency = selectedFlight.currency || 'USD'
  const taxes = Math.round(subtotal * 0.1 * 100) / 100
  const tierDiscountPct = loyaltyTier?.discount_percent || 0
  const tierDiscount = tierDiscountPct > 0
    ? Math.round(subtotal * tierDiscountPct / 100 * 100) / 100
    : 0
  const totalDiscount = tierDiscount + (appliedVoucher?.discount_amount || 0) + loyaltyDiscount
  const finalTotal = Math.max(0, subtotal + taxes - totalDiscount)

  const paxList = selectedFlight.passengers
    || (selectedFlight.passenger ? [selectedFlight.passenger] : [])
  const paxCount = selectedFlight.quantity || paxList.length || 1

  // ── Voucher / loyalty handlers ──────────────────────────────────────────
  const { data: availableVouchers } = useQuery({
    queryKey: ['available-vouchers'],
    queryFn: () => vouchersApi.available(),
    select: (res) => res.data || [],
  })

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
        toast.success(`Voucher applied: −${fmt(res.data.discount_amount, currency)}`)
      } else {
        toast.error(res.data?.message || 'Invalid voucher')
        setAppliedVoucher(null)
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Could not validate voucher')
    } finally {
      setVoucherLoading(false)
    }
  }

  const handleApplyLoyalty = () => {
    const pts = parseInt(pointsToRedeem, 10)
    if (!pts || pts <= 0) return
    if (pts > loyaltyPoints) {
      toast.error('Not enough points'); return
    }
    // 100 pts = 1 USD (standard rate across app)
    const discount = Math.min(Math.round((pts / 100) * 100) / 100, subtotal)
    setLoyaltyDiscount(discount)
    setPointsApplied(true)
    toast.success(`Redeemed ${pts} points = ${fmt(discount, currency)} off`)
  }

  // ── Proceed to payment ──────────────────────────────────────────────────
  const handleProceed = async () => {
    if (proceeding) return
    if (paxList.length === 0) {
      toast.error('No passenger info — please go back to the offer page'); return
    }
    setProceeding(true)
    try {
      // Build adults / children breakdown from passenger forms
      const adultsInForm = paxList.filter((p) => p.age == null).length
      const childAgesInForm = paxList.filter((p) => p.age != null).map((p) => Number(p.age))

      // 1. Create booking
      const bookingPayload = {
        items: [{
          item_type: 'flight',
          duffel_offer_id: selectedFlight.duffel_offer_id,
          passengers: paxList,
          selected_services: selectedFlight.selected_services || undefined,
          selected_seats: selectedFlight.selected_seats || undefined,
          quantity: paxCount,
          adults: adultsInForm > 0 ? adultsInForm : (selectedFlight.adults || paxCount),
          children_ages: childAgesInForm,
        }],
        special_requests: specialRequests || undefined,
        voucher_code: appliedVoucher?.code || undefined,
        points_to_redeem: pointsApplied && parseInt(pointsToRedeem, 10) > 0 ? parseInt(pointsToRedeem, 10) : 0,
      }
      const bookingRes = await bookingsApi.create(bookingPayload)
      const bId = bookingRes.data?.id || bookingRes.data?.data?.id
      // FE-03: don't carry an undefined booking id forward.
      if (!bId) throw new Error('Booking creation failed — no booking id returned')
      setBookingId(bId)

      // Loyalty points are redeemed as part of booking creation (points_to_redeem
      // above): the backend deducts them, applies the discount to booking.total_price
      // so Stripe charges the reduced amount, and reverses them if the booking is
      // never paid. No separate redeem call — that double-deducts and leaves
      // total_price stale (UC17).

      // 2. Create Stripe PaymentIntent — backend re-validates offer-alive
      const paymentRes = await paymentsApi.create({
        booking_id: bId,
        currency: 'usd',
      })
      const clientSecret = paymentRes.data?.data?.client_secret
      const stripePaymentId = paymentRes.data?.data?.payment_id
      // FE-03: don't render the Stripe step without a usable client secret.
      if (!clientSecret || !stripePaymentId) {
        throw new Error('Failed to start payment — please try again')
      }
      setClientSecret(clientSecret)
      setStripePaymentId(stripePaymentId)
      setStep('payment')
    } catch (err) {
      const detail = err.response?.data?.detail
      if (err.response?.status === 409 && detail?.error_code === 'offer_no_longer_available') {
        toast.error(detail.message || 'Flight offer is no longer available — please search again')
        navigate('/flights')
        return
      }
      const msg = typeof detail === 'string' ? detail : (detail?.message || 'Could not start payment')
      toast.error(msg)
    } finally {
      setProceeding(false)
    }
  }

  // ── Payment success handler ─────────────────────────────────────────────
  const handlePaymentSuccess = (failure = null) => {
    // Order matters: mark `completedRef` BEFORE clearBooking so the guard
    // useEffect skips its redirect when the store nulls out. Then navigate
    // explicitly to the booking confirmation page (or failure page on
    // supplier rejection) — never back to /flights search.
    completedRef.current = true
    clearBooking()
    // Bust the My Bookings cache so the new flight shows up the next time the
    // user opens /profile?tab=bookings — global staleTime is 5min, so without
    // this the list stays stale until the user hard-refreshes.
    qc.invalidateQueries({ queryKey: ['my-bookings'] })
    if (failure) {
      navigate(`/bookings/${bookingId}/failure`, { state: { failure }, replace: true })
      return
    }
    toast.success('Booking confirmed!')
    navigate(`/bookings/${bookingId}/confirmation`, { replace: true })
  }

  return (
    <>
      <Helmet>
        <title>Flight Checkout — TravelBooking</title>
      </Helmet>
      <div className="max-w-6xl mx-auto px-4 py-6">
        <Breadcrumb items={[
          { label: 'Home', to: '/' },
          { label: 'Flights', to: '/flights' },
          { label: 'Checkout' },
        ]} />

        <div className="flex items-center gap-3 mt-4 mb-6">
          <button onClick={() => navigate(-1)} className="p-2 rounded-lg hover:bg-gray-100 transition-colors">
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
            <PlaneTakeoff className="w-6 h-6 text-primary" />
            {step === 'review' ? 'Review your flight' : 'Pay for your flight'}
          </h1>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-3 mb-6 text-xs">
          <StepDot label="Review" active={step === 'review'} done={step === 'payment'} />
          <div className="flex-1 h-0.5 bg-gray-200" />
          <StepDot label="Payment" active={step === 'payment'} done={false} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: form */}
          <div className="lg:col-span-2 space-y-6">
            {step === 'review' && (
              <>
                {/* Passenger list (read-only) */}
                <div className="bg-white border rounded-2xl p-6">
                  <h2 className="font-heading font-bold text-lg mb-4 flex items-center gap-2">
                    <Ticket className="w-5 h-5 text-primary" /> Passengers ({paxCount})
                  </h2>
                  {paxList.length === 0 ? (
                    <p className="text-sm text-error">No passenger info — go back to the offer page</p>
                  ) : (
                    <ul className="space-y-2 text-sm">
                      {paxList.map((p, i) => (
                        <li key={i} className="flex items-start gap-3 py-2 border-b last:border-b-0">
                          <span className="text-xs font-semibold text-gray-400 w-6">{i + 1}.</span>
                          <div className="flex-1 min-w-0">
                            <p className="font-medium">
                              {(p.title || '').toUpperCase()}. {p.first_name} {p.last_name}
                              {p.age != null && (
                                <span className="ml-2 text-xs text-gray-500">(age {p.age})</span>
                              )}
                            </p>
                            <p className="text-xs text-gray-500">
                              {p.email} {p.phone_number && `· ${p.phone_number}`}
                            </p>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="text-xs text-gray-400 mt-3">
                    Need to edit? <button onClick={() => navigate(-1)} className="text-primary hover:underline">
                      Go back to the offer page
                    </button>
                  </p>
                </div>

                {/* Voucher */}
                <div className="bg-white border rounded-2xl p-6 space-y-3">
                  <h2 className="font-heading font-bold text-lg flex items-center gap-2">
                    <Tag className="w-5 h-5" /> Voucher
                  </h2>
                  {appliedVoucher ? (
                    <div className="flex items-center justify-between bg-success/5 border border-success/20 rounded-lg px-4 py-3">
                      <div>
                        <p className="text-sm font-semibold text-success">
                          {appliedVoucher.code} applied
                        </p>
                        <p className="text-xs text-gray-500">
                          You save {fmt(appliedVoucher.discount_amount, currency)}
                        </p>
                      </div>
                      <button
                        onClick={() => { setAppliedVoucher(null); setVoucherInput('') }}
                        className="text-xs text-error hover:underline"
                      >
                        Remove
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={voucherInput}
                        onChange={(e) => setVoucherInput(e.target.value.toUpperCase())}
                        placeholder="Enter voucher code"
                        className="flex-1 border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                      />
                      <button
                        onClick={() => handleApplyVoucher()}
                        disabled={voucherLoading || !voucherInput.trim()}
                        className="bg-primary text-white font-semibold px-4 py-2 rounded-lg hover:bg-primary/90 disabled:bg-gray-300 text-sm"
                      >
                        {voucherLoading ? 'Checking…' : 'Apply'}
                      </button>
                    </div>
                  )}
                  {!appliedVoucher && availableVouchers?.length > 0 && (
                    <div className="pt-1">
                      <p className="text-xs text-gray-500 mb-1.5">Available vouchers</p>
                      <div className="flex flex-wrap gap-2">
                        {availableVouchers.slice(0, 6).map((v) => (
                          <button key={v.code} type="button" onClick={() => handleApplyVoucher(v.code)}
                            title={v.name}
                            className="inline-flex items-center gap-1 border border-dashed border-primary/40 text-primary px-2.5 py-1 rounded-lg text-xs font-mono font-semibold hover:bg-primary/5">
                            <Tag className="w-3 h-3" /> {v.code}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Loyalty */}
                <div className="bg-white border rounded-2xl p-6 space-y-3">
                  <h2 className="font-heading font-bold text-lg flex items-center gap-2">
                    <Award className="w-5 h-5" /> Loyalty points
                  </h2>
                  <p className="text-sm text-gray-600">
                    Available: <strong>{loyaltyPoints.toLocaleString()}</strong> points
                    {loyaltyTier?.name && (
                      <span className="text-xs text-gray-400 ml-2">· {loyaltyTier.name} tier</span>
                    )}
                  </p>
                  {pointsApplied ? (
                    <div className="flex items-center justify-between bg-primary/5 border border-primary/20 rounded-lg px-4 py-3">
                      <p className="text-sm font-semibold text-primary">
                        {pointsToRedeem} points = {fmt(loyaltyDiscount, currency)} off
                      </p>
                      <button
                        onClick={() => { setPointsApplied(false); setLoyaltyDiscount(0); setPointsToRedeem('') }}
                        className="text-xs text-error hover:underline"
                      >
                        Remove
                      </button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <input
                        type="number"
                        min="0"
                        max={loyaltyPoints}
                        value={pointsToRedeem}
                        onChange={(e) => setPointsToRedeem(e.target.value)}
                        placeholder="Points to redeem"
                        className="flex-1 border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                      />
                      <button
                        onClick={handleApplyLoyalty}
                        disabled={!pointsToRedeem || parseInt(pointsToRedeem, 10) <= 0}
                        className="bg-primary text-white font-semibold px-4 py-2 rounded-lg hover:bg-primary/90 disabled:bg-gray-300 text-sm"
                      >
                        Apply
                      </button>
                    </div>
                  )}
                  <p className="text-xs text-gray-400">100 points = $1.00 USD</p>
                </div>

                {/* Special requests */}
                <div className="bg-white border rounded-2xl p-6 space-y-2">
                  <h2 className="font-heading font-bold text-lg">Special requests</h2>
                  <textarea
                    value={specialRequests}
                    onChange={(e) => setSpecialRequests(e.target.value)}
                    placeholder="e.g. dietary requirements, wheelchair assistance (forwarded to airline if supported)"
                    className="w-full border rounded-lg px-4 py-3 text-sm resize-none h-20 focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>

                <button
                  onClick={handleProceed}
                  disabled={proceeding || paxList.length === 0}
                  className="w-full bg-accent hover:bg-accent/90 disabled:bg-gray-300 text-white font-bold py-4 rounded-xl text-base flex items-center justify-center gap-2"
                >
                  {proceeding ? 'Preparing payment…' : 'Continue to payment'}
                  {!proceeding && <ArrowRight className="w-5 h-5" />}
                </button>
              </>
            )}

            {step === 'payment' && clientSecret && (
              <Elements
                key={clientSecret}
                stripe={stripePromise}
                options={{ clientSecret, appearance: { theme: 'stripe' } }}
              >
                <FlightStripeForm
                  stripePaymentId={stripePaymentId}
                  finalTotal={finalTotal}
                  currency={currency}
                  onSuccess={handlePaymentSuccess}
                />
              </Elements>
            )}
          </div>

          {/* Right: order summary (sticky) */}
          <div className="lg:col-span-1">
            <div className="sticky top-20 space-y-4">
              <FlightSummaryCard
                flight={selectedFlight}
                subtotal={subtotal}
                taxes={taxes}
                discounts={{
                  tier: tierDiscount,
                  voucher: appliedVoucher?.discount_amount || 0,
                  loyalty: loyaltyDiscount,
                }}
                finalTotal={finalTotal}
                paxCount={paxCount}
              />

              {secondsLeft != null && secondsLeft > 0 && (
                <div className={`flex items-center justify-center gap-1.5 text-xs font-medium px-3 py-2 rounded-lg ${
                  secondsLeft < 180
                    ? 'bg-error/10 text-error'
                    : secondsLeft < 300
                      ? 'bg-amber-50 text-amber-700'
                      : 'bg-gray-50 text-gray-500'
                }`}>
                  <Clock className="w-3.5 h-3.5" />
                  Offer expires in {Math.floor(secondsLeft / 60)}m {secondsLeft % 60}s
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

function StepDot({ label, active, done }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
        active ? 'bg-primary text-white' : done ? 'bg-success text-white' : 'bg-gray-200 text-gray-500'
      }`}>
        {done ? <CheckCircle className="w-3.5 h-3.5" /> : (label === 'Review' ? '1' : '2')}
      </div>
      <span className={`text-xs font-medium ${active ? 'text-primary' : done ? 'text-success' : 'text-gray-400'}`}>
        {label}
      </span>
    </div>
  )
}

function FlightSummaryCard({ flight, subtotal, taxes, discounts, finalTotal, paxCount }) {
  const fmt = useFormatCurrency()
  const currency = flight.currency || 'USD'

  return (
    <div className="bg-white border rounded-2xl p-5 space-y-4 shadow-sm">
      <div className="flex items-center gap-2">
        <PlaneTakeoff className="w-5 h-5 text-primary" />
        <span className="font-bold text-sm">{flight.airline_name}</span>
        {flight.cabin_class && (
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full ml-auto">
            {flight.cabin_class}
          </span>
        )}
      </div>

      {/* Slices: show each leg with departure/arrival */}
      <div className="space-y-3 border-t pt-3">
        {flight.slices?.map((slice, i) => {
          const firstSeg = slice.segments?.[0]
          const lastSeg = slice.segments?.[slice.segments.length - 1]
          return (
            <div key={i} className="text-sm">
              <p className="text-xs text-gray-400 font-semibold mb-1">
                {flight.slices.length > 1 ? `Leg ${i + 1}` : 'Itinerary'}
              </p>
              <div className="flex items-center gap-2">
                <div className="flex-1 min-w-0">
                  <p className="font-bold">{slice.origin}</p>
                  {firstSeg && (
                    <p className="text-xs text-gray-500">
                      {fmtTime(firstSeg.departure_at)} · {fmtDate(firstSeg.departure_at)}
                    </p>
                  )}
                </div>
                <div className="flex flex-col items-center text-gray-400">
                  <ArrowRight className="w-4 h-4" />
                  {slice.duration && (
                    <span className="text-[10px]">{fmtDuration(slice.duration)}</span>
                  )}
                </div>
                <div className="flex-1 min-w-0 text-right">
                  <p className="font-bold">{slice.destination}</p>
                  {lastSeg && (
                    <p className="text-xs text-gray-500">
                      {fmtTime(lastSeg.arrival_at)} · {fmtDate(lastSeg.arrival_at)}
                    </p>
                  )}
                </div>
              </div>
              {slice.segments?.length > 1 && (
                <p className="text-[10px] text-amber-600 mt-1">
                  {slice.segments.length - 1} stop{slice.segments.length > 2 ? 's' : ''}
                </p>
              )}
            </div>
          )
        })}
      </div>

      {/* Pricing breakdown */}
      <div className="space-y-1.5 text-sm border-t pt-3">
        <div className="flex justify-between">
          <span className="text-gray-600">
            Base fare × {paxCount}
          </span>
          <span>{fmt(subtotal, currency)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-600">Taxes & fees</span>
          <span>{fmt(taxes, currency)}</span>
        </div>
        {discounts.tier > 0 && (
          <div className="flex justify-between text-success">
            <span>Loyalty tier discount</span>
            <span>−{fmt(discounts.tier, currency)}</span>
          </div>
        )}
        {discounts.voucher > 0 && (
          <div className="flex justify-between text-success">
            <span>Voucher</span>
            <span>−{fmt(discounts.voucher, currency)}</span>
          </div>
        )}
        {discounts.loyalty > 0 && (
          <div className="flex justify-between text-success">
            <span>Points redeemed</span>
            <span>−{fmt(discounts.loyalty, currency)}</span>
          </div>
        )}
      </div>

      <div className="flex justify-between items-baseline border-t pt-3">
        <span className="text-sm font-semibold">Total to pay</span>
        <span className="text-xl font-bold text-primary">{fmt(finalTotal, currency)}</span>
      </div>
    </div>
  )
}

function FlightStripeForm({ stripePaymentId, finalTotal, currency, onSuccess }) {
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
          // Webhook will retry — treat as success client-side; confirmation
          // page re-reads the booking record on mount.
        }
      }
      onSuccess()
    } else {
      setCardError('Payment did not complete. Please try again.')
      setPaying(false)
    }
  }

  return (
    <div className="bg-white border rounded-2xl p-6 space-y-5">
      <h2 className="font-heading font-bold text-lg flex items-center gap-2">
        <CreditCard className="w-5 h-5" /> Card details
      </h2>

      <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 text-xs text-blue-700 flex items-start gap-2">
        <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        <span>
          <strong>Test card:</strong> 4242 4242 4242 4242 — any future date — any CVC
        </span>
      </div>

      <form onSubmit={handlePay} className="space-y-4">
        <PaymentElement options={{ layout: 'tabs' }} />

        {cardError && (
          <p className="text-sm text-error">{cardError}</p>
        )}

        <button
          type="submit"
          disabled={!stripe || paying}
          className="w-full bg-accent hover:bg-accent/90 disabled:bg-gray-300 text-white font-bold py-4 rounded-xl text-base flex items-center justify-center gap-2"
        >
          <CreditCard className="w-5 h-5" />
          {paying ? 'Processing…' : `Pay ${fmt(finalTotal, currency)}`}
        </button>
      </form>

      <p className="text-xs text-gray-400 text-center">
        Booking is finalised with the airline immediately after a successful charge.
      </p>
    </div>
  )
}
