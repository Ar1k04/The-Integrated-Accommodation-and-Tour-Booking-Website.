import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { loadStripe } from '@stripe/stripe-js'
import {
  Elements, PaymentElement, useStripe, useElements,
} from '@stripe/react-stripe-js'
import { format, addDays } from 'date-fns'
import {
  ArrowLeft, ArrowRight, ArrowLeftRight, Plus, Minus, Check, AlertCircle,
  ArrowRightLeft, PlaneTakeoff,
} from 'lucide-react'

import { bookingsApi } from '@/api/bookingsApi'
import { flightsApi } from '@/api/flightsApi'
import AirportSearchInput from '@/components/flight/AirportSearchInput'
import FlightItineraryBlock from '@/components/flight/FlightItineraryBlock'
import Skeleton from '@/components/common/Skeleton'
import Breadcrumb from '@/components/common/Breadcrumb'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'

const stripePromise = loadStripe(import.meta.env.VITE_STRIPE_PUBLIC_KEY || '')

export default function FlightChangeRequestPage() {
  const { bookingId } = useParams()
  const navigate = useNavigate()
  const { t } = useTranslation(['flights', 'common'])
  const fmt = useFormatCurrency()

  const [step, setStep] = useState(1)
  const [slicesRemove, setSlicesRemove] = useState([])
  const [slicesAdd, setSlicesAdd] = useState([
    { origin: null, destination: null, date: format(addDays(new Date(), 14), 'yyyy-MM-dd'), cabin_class: 'economy' },
  ])
  const [ocrId, setOcrId] = useState(null)
  const [selectedOffer, setSelectedOffer] = useState(null)
  const [orderChangeId, setOrderChangeId] = useState(null)
  const [clientSecret, setClientSecret] = useState(null)
  const [paymentIntentId, setPaymentIntentId] = useState(null)

  const { data: booking, isLoading } = useQuery({
    queryKey: ['booking', bookingId],
    queryFn: () => bookingsApi.get(bookingId),
    select: (res) => res.data,
  })

  const flightItem = booking?.items?.find((i) => i.item_type === 'flight')
  const flight = flightItem?.flight_booking
  const snapshot = flight?.passenger_details?.offer_snapshot || {}
  const currentSlices = snapshot.slices || []

  // ── Wizard mutations ─────────────────────────────────────────────────────
  const createChangeMutation = useMutation({
    mutationFn: (body) => flightsApi.createChangeRequest(flight.duffel_order_id, body),
    onSuccess: (res) => {
      const id = res.data?.data?.id
      if (!id) {
        toast.error(t('flights:change.createFailed', 'Could not start change request'))
        return
      }
      setOcrId(id)
      setStep(2)
    },
    onError: (err) =>
      toast.error(err.response?.data?.detail || t('flights:change.createFailed', 'Could not start change request')),
  })

  const { data: changeOffers, isFetching: offersLoading } = useQuery({
    queryKey: ['change-offers', ocrId],
    queryFn: () => flightsApi.listChangeOffers(ocrId, { limit: 50 }),
    enabled: !!ocrId,
    refetchInterval: (q) => {
      const data = q.state.data?.data?.data
      return !data || data.length === 0 ? 2500 : false
    },
    select: (res) => res.data?.data || [],
    staleTime: 30_000,
  })

  const selectOfferMutation = useMutation({
    mutationFn: (ocoId) => flightsApi.selectChangeOffer(ocoId),
    onSuccess: (res) => {
      const data = res.data?.data || {}
      setOrderChangeId(data.id)
      setStep(3)
      const change = Number(data.change_total_amount || 0)
      if (change > 0) {
        // Need to create a Stripe intent
        createIntentMutation.mutate(data.id)
      }
    },
    onError: (err) =>
      toast.error(err.response?.data?.detail || t('flights:change.selectFailed', 'Could not select offer')),
  })

  const createIntentMutation = useMutation({
    mutationFn: (ocId) => flightsApi.createChangePaymentIntent(ocId),
    onSuccess: (res) => {
      setClientSecret(res.data?.data?.client_secret)
      setPaymentIntentId(res.data?.data?.payment_intent_id)
    },
    onError: () => toast.error(t('flights:change.intentFailed', 'Could not initialise payment')),
  })

  const confirmMutation = useMutation({
    mutationFn: ({ piId }) =>
      flightsApi.confirmOrderChange(orderChangeId, piId ? { payment_intent_id: piId } : {}),
    onSuccess: () => {
      toast.success(t('flights:change.success', 'Change confirmed'))
      setStep(4)
    },
    onError: (err) =>
      toast.error(err.response?.data?.detail || t('flights:change.confirmFailed', 'Confirmation failed')),
  })

  // ── Slice editing helpers ────────────────────────────────────────────────
  const toggleRemove = (sliceId) => {
    setSlicesRemove((s) => s.includes(sliceId) ? s.filter((x) => x !== sliceId) : [...s, sliceId])
  }

  const updateAddSlice = (idx, patch) => {
    setSlicesAdd((s) => s.map((sl, i) => (i === idx ? { ...sl, ...patch } : sl)))
  }
  const addAddSlice = () => {
    if (slicesAdd.length >= 6) return
    setSlicesAdd((s) => [...s, { origin: null, destination: null, date: format(addDays(new Date(), 21), 'yyyy-MM-dd'), cabin_class: 'economy' }])
  }
  const removeAddSlice = (idx) => {
    if (slicesAdd.length <= 1) return
    setSlicesAdd((s) => s.filter((_, i) => i !== idx))
  }

  const handleStep1Submit = () => {
    if (slicesRemove.length === 0) {
      toast.error(t('flights:change.selectRemoveSlice', 'Select at least one slice to change'))
      return
    }
    for (const sl of slicesAdd) {
      if (!sl.origin?.iata || !sl.destination?.iata || !sl.date) {
        toast.error(t('flights:change.fillNewSlice', 'Fill all new slice fields'))
        return
      }
      if (sl.origin.iata === sl.destination.iata) {
        toast.error(t('flights:page.sameAirport'))
        return
      }
    }
    createChangeMutation.mutate({
      slices_remove: slicesRemove,
      slices_add: slicesAdd.map((s) => ({
        origin: s.origin.iata,
        destination: s.destination.iata,
        departure_date: s.date,
        cabin_class: s.cabin_class || 'economy',
      })),
    })
  }

  const offers = changeOffers || []
  const sortedOffers = useMemo(
    () => [...offers].sort((a, b) => (a.change_total_amount || 0) - (b.change_total_amount || 0)),
    [offers],
  )

  if (isLoading) {
    return <div className="max-w-4xl mx-auto px-4 py-8 space-y-4">
      <Skeleton className="h-32 rounded-xl" /><Skeleton className="h-64 rounded-xl" />
    </div>
  }

  if (!booking || !flight || !flight.duffel_order_id) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-20 text-center">
        <AlertCircle className="w-12 h-12 text-gray-300 mx-auto mb-3" />
        <p className="text-gray-500 mb-6">{t('flights:change.noBooking', 'No flight booking to change')}</p>
        <button
          onClick={() => navigate(`/flights/bookings/${bookingId}`)}
          className="text-primary hover:underline"
        >
          ← {t('flights:change.backToManage', 'Back to booking')}
        </button>
      </div>
    )
  }

  const changeTotalUSD = selectedOffer?.change_total_amount || 0

  return (
    <>
      <Helmet><title>{t('flights:change.title', 'Change flight')}</title></Helmet>
      <div className="max-w-4xl mx-auto px-4 py-6">
        <Breadcrumb items={[
          { label: 'Home', to: '/' },
          { label: 'My Bookings', to: '/profile?tab=bookings' },
          { label: t('flights:manage.heading'), to: `/flights/bookings/${bookingId}` },
          { label: t('flights:change.title', 'Change flight') },
        ]} />

        <div className="flex items-center gap-3 mt-4 mb-6">
          <button
            onClick={() => navigate(`/flights/bookings/${bookingId}`)}
            className="p-2 rounded-lg hover:bg-gray-100 transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="font-heading text-2xl font-bold flex items-center gap-2">
            <ArrowRightLeft className="w-6 h-6 text-accent" />
            {t('flights:change.title', 'Change flight')}
          </h1>
        </div>

        <div className="flex items-center gap-3 mb-6 text-xs">
          {[1, 2, 3, 4].map((n) => (
            <div key={n} className={`flex-1 h-1.5 rounded-full ${
              n <= step ? 'bg-primary' : 'bg-gray-200'
            }`} />
          ))}
        </div>

        {/* Step 1 — Select what to change */}
        {step === 1 && (
          <div className="space-y-6">
            <div className="bg-white border rounded-2xl p-6">
              <h2 className="font-heading font-bold text-lg mb-2">
                {t('flights:change.step1Title', '1. Choose slices to remove')}
              </h2>
              <p className="text-sm text-gray-500 mb-4">
                {t('flights:change.step1Hint', 'Select the slices you want to replace.')}
              </p>
              <ul className="space-y-2">
                {currentSlices.map((sl, idx) => (
                  <li key={idx}>
                    <label className="flex items-start gap-3 p-3 rounded-lg border hover:bg-gray-50 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={slicesRemove.includes(sl.id)}
                        onChange={() => toggleRemove(sl.id)}
                        disabled={!sl.id}
                        className="mt-1"
                      />
                      <div className="flex-1">
                        <p className="font-medium text-sm">
                          {(sl.origin?.iata_code || sl.origin) || flight.departure_airport}
                          <ArrowRight className="inline w-3.5 h-3.5 mx-2" />
                          {(sl.destination?.iata_code || sl.destination) || flight.arrival_airport}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">
                          {(sl.segments?.[0]?.departure_at || '').slice(0, 16).replace('T', ' ')}
                          {sl.id && (
                            <code className="ml-2 text-[10px] text-gray-400">{sl.id}</code>
                          )}
                        </p>
                      </div>
                    </label>
                  </li>
                ))}
                {currentSlices.length === 0 && (
                  <p className="text-sm text-gray-500">
                    {t('flights:change.noSlicesAvailable', 'No slice IDs available — try sync first')}
                  </p>
                )}
              </ul>
            </div>

            <div className="bg-white border rounded-2xl p-6">
              <h2 className="font-heading font-bold text-lg mb-2">
                {t('flights:change.step1AddTitle', '2. New flights to search')}
              </h2>
              <p className="text-sm text-gray-500 mb-4">
                {t('flights:change.step1AddHint', 'Describe the new slices you want.')}
              </p>
              <div className="space-y-3">
                {slicesAdd.map((sl, idx) => (
                  <div key={idx} className="bg-gray-50 rounded-xl p-3 border">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-gray-500">
                        {t('flights:page.sliceLabel', { n: idx + 1, defaultValue: `Flight ${idx + 1}` })}
                      </span>
                      {slicesAdd.length > 1 && (
                        <button
                          type="button"
                          onClick={() => removeAddSlice(idx)}
                          className="text-error hover:bg-error/10 rounded-full w-7 h-7 flex items-center justify-center"
                        >
                          <Minus className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-[1fr,auto,1fr,160px,140px] gap-2 items-end">
                      <AirportSearchInput
                        label={t('flights:page.from')}
                        value={sl.origin}
                        onChange={(v) => updateAddSlice(idx, { origin: v })}
                      />
                      <button
                        type="button"
                        onClick={() => updateAddSlice(idx, { origin: sl.destination, destination: sl.origin })}
                        className="p-2 rounded-full hover:bg-gray-100 self-end mb-0.5 text-gray-500"
                      >
                        <ArrowLeftRight className="w-4 h-4" />
                      </button>
                      <AirportSearchInput
                        label={t('flights:page.to')}
                        value={sl.destination}
                        onChange={(v) => updateAddSlice(idx, { destination: v })}
                      />
                      <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                          {t('flights:page.depart')}
                        </label>
                        <input
                          type="date"
                          value={sl.date}
                          onChange={(e) => updateAddSlice(idx, { date: e.target.value })}
                          className="w-full border rounded-lg px-2 py-2 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1">
                          {t('flights:page.cabinClass')}
                        </label>
                        <select
                          value={sl.cabin_class}
                          onChange={(e) => updateAddSlice(idx, { cabin_class: e.target.value })}
                          className="w-full border rounded-lg px-2 py-2 text-sm"
                        >
                          <option value="economy">Economy</option>
                          <option value="premium_economy">Premium</option>
                          <option value="business">Business</option>
                          <option value="first">First</option>
                        </select>
                      </div>
                    </div>
                  </div>
                ))}
                {slicesAdd.length < 6 && (
                  <button
                    type="button"
                    onClick={addAddSlice}
                    className="flex items-center gap-1.5 text-sm text-primary hover:underline"
                  >
                    <Plus className="w-4 h-4" /> {t('flights:page.addFlight', 'Add flight')}
                  </button>
                )}
              </div>
            </div>

            <button
              onClick={handleStep1Submit}
              disabled={createChangeMutation.isPending}
              className="w-full bg-primary hover:bg-primary/90 disabled:bg-gray-300 text-white font-bold py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
            >
              <PlaneTakeoff className="w-5 h-5" />
              {createChangeMutation.isPending
                ? t('flights:change.searching', 'Searching…')
                : t('flights:change.findOffers', 'Find change offers')}
            </button>
          </div>
        )}

        {/* Step 2 — Browse change offers */}
        {step === 2 && (
          <div className="space-y-4">
            <h2 className="font-heading font-bold text-lg">
              {t('flights:change.step2Title', 'Available change offers')}
            </h2>
            {offersLoading && (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => <Skeleton key={i} className="h-32 rounded-xl" />)}
              </div>
            )}
            {!offersLoading && sortedOffers.length === 0 && (
              <div className="text-center py-16 text-gray-400">
                <p>{t('flights:change.noOffers', 'No change offers from the airline')}</p>
              </div>
            )}
            {!offersLoading && sortedOffers.map((o) => (
              <div key={o.id} className="bg-white border rounded-2xl p-5 hover:border-primary cursor-pointer transition-colors"
                   onClick={() => { setSelectedOffer(o); selectOfferMutation.mutate(o.id) }}>
                <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
                  <div>
                    <p className="text-sm text-gray-500">
                      {(o.slices_add || []).map((s) => `${s.origin}→${s.destination}`).join(', ')}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className={`text-2xl font-bold ${(o.change_total_amount || 0) > 0 ? 'text-error' : (o.change_total_amount || 0) < 0 ? 'text-success' : 'text-gray-700'}`}>
                      {(o.change_total_amount || 0) > 0 ? '+' : ''}{fmt(o.change_total_amount || 0, o.change_total_currency || 'USD')}
                    </p>
                    <p className="text-xs text-gray-400">
                      {(o.change_total_amount || 0) > 0
                        ? t('flights:change.youPay', 'You pay')
                        : (o.change_total_amount || 0) < 0
                          ? t('flights:change.youGetBack', 'You get back')
                          : t('flights:change.noChargeNoRefund', 'No charge')}
                    </p>
                  </div>
                </div>
                <FlightItineraryBlock slices={o.slices_add} compact />
                {o.penalty_total_amount > 0 && (
                  <p className="text-xs text-amber-700 mt-2">
                    {t('flights:change.penalty', 'Penalty')}: {fmt(o.penalty_total_amount, o.penalty_total_currency)}
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Step 3 — Confirm + (optional) pay */}
        {step === 3 && selectedOffer && (
          <div className="space-y-4">
            <div className="bg-white border rounded-2xl p-6">
              <h2 className="font-heading font-bold text-lg mb-3">
                {t('flights:change.step3Title', 'Confirm change')}
              </h2>
              <div className="text-sm space-y-2 mb-4">
                <p>
                  <span className="text-gray-500">{t('flights:change.diff', 'Difference')}:</span>{' '}
                  <strong className={changeTotalUSD > 0 ? 'text-error' : changeTotalUSD < 0 ? 'text-success' : ''}>
                    {changeTotalUSD > 0 ? '+' : ''}{fmt(changeTotalUSD, selectedOffer.change_total_currency || 'USD')}
                  </strong>
                </p>
                {selectedOffer.penalty_total_amount > 0 && (
                  <p>
                    <span className="text-gray-500">{t('flights:change.penalty', 'Penalty')}:</span>{' '}
                    {fmt(selectedOffer.penalty_total_amount, selectedOffer.penalty_total_currency || 'USD')}
                  </p>
                )}
                {selectedOffer.refund_to && changeTotalUSD < 0 && (
                  <p className="text-xs text-gray-500">
                    {t('flights:change.refundTo', 'Refund to')}: {selectedOffer.refund_to}
                  </p>
                )}
              </div>

              {changeTotalUSD <= 0 && (
                <button
                  onClick={() => confirmMutation.mutate({ piId: null })}
                  disabled={confirmMutation.isPending}
                  className="w-full bg-primary hover:bg-primary/90 disabled:bg-gray-300 text-white font-bold py-3 rounded-xl transition-colors"
                >
                  {confirmMutation.isPending
                    ? t('flights:change.confirming', 'Confirming…')
                    : t('flights:change.confirmNoCharge', 'Confirm change')}
                </button>
              )}

              {changeTotalUSD > 0 && (
                <>
                  {!clientSecret && (
                    <p className="text-sm text-gray-500">{t('flights:change.preparingPayment', 'Preparing payment…')}</p>
                  )}
                  {clientSecret && (
                    <Elements key={clientSecret} stripe={stripePromise} options={{ clientSecret, appearance: { theme: 'stripe' } }}>
                      <ChangePaymentForm
                        clientSecret={clientSecret}
                        paymentIntentId={paymentIntentId}
                        amount={changeTotalUSD}
                        currency={selectedOffer.change_total_currency || 'USD'}
                        onPaid={(piId) => confirmMutation.mutate({ piId })}
                        confirming={confirmMutation.isPending}
                      />
                    </Elements>
                  )}
                </>
              )}
            </div>
          </div>
        )}

        {/* Step 4 — Success */}
        {step === 4 && (
          <div className="bg-white border rounded-2xl p-10 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-success/10 flex items-center justify-center">
              <Check className="w-8 h-8 text-success" />
            </div>
            <h2 className="font-heading font-bold text-xl mb-2">
              {t('flights:change.successTitle', 'Change confirmed')}
            </h2>
            <p className="text-sm text-gray-500 mb-6">
              {t('flights:change.successMessage', 'Your itinerary is updated. We have synced the new flight with the airline.')}
            </p>
            <button
              onClick={() => navigate(`/flights/bookings/${bookingId}`)}
              className="bg-primary text-white font-semibold px-6 py-2.5 rounded-lg hover:bg-primary/90"
            >
              {t('flights:change.backToManage', 'Back to booking')}
            </button>
          </div>
        )}
      </div>
    </>
  )
}

function ChangePaymentForm({ clientSecret, paymentIntentId, amount, currency, onPaid, confirming }) {
  const stripe = useStripe()
  const elements = useElements()
  const { t } = useTranslation('flights')
  const fmt = useFormatCurrency()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handlePay = async () => {
    if (!stripe || !elements) return
    setLoading(true)
    setError('')
    try {
      const result = await stripe.confirmPayment({
        elements,
        redirect: 'if_required',
      })
      if (result.error) {
        setError(result.error.message)
        setLoading(false)
        return
      }
      if (result.paymentIntent?.status === 'succeeded') {
        onPaid(result.paymentIntent.id)
      } else {
        setError(t('change.paymentNotSucceeded', 'Payment not yet succeeded'))
      }
    } catch (e) {
      setError(e.message || 'Payment failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <PaymentElement />
      {error && <p className="text-sm text-error">{error}</p>}
      <button
        onClick={handlePay}
        disabled={loading || confirming || !stripe || !elements}
        className="w-full bg-primary hover:bg-primary/90 disabled:bg-gray-300 text-white font-bold py-3 rounded-xl transition-colors"
      >
        {loading
          ? t('change.charging', 'Charging…')
          : confirming
            ? t('change.confirming', 'Confirming…')
            : `${t('change.payAndConfirm', 'Pay & confirm')} ${fmt(amount, currency)}`}
      </button>
    </div>
  )
}
