import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { useTranslation } from 'react-i18next'
import {
  CreditCard, CheckCircle, User, PlaneTakeoff, PlaneLanding, Armchair, Briefcase, Clock,
} from 'lucide-react'

import { flightsApi } from '@/api/flightsApi'
import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import Breadcrumb from '@/components/common/Breadcrumb'
import Skeleton from '@/components/common/Skeleton'
import FlightItineraryBlock from '@/components/flight/FlightItineraryBlock'
import MultiPassengerForm from '@/components/flight/MultiPassengerForm'
import { emptyPassenger, arePassengersComplete } from '@/components/flight/passengerHelpers'
import FareBreakdownCard from '@/components/flight/FareBreakdownCard'
import FareRulesAccordion from '@/components/flight/FareRulesAccordion'
import SeatMapModal from '@/components/flight/SeatMapModal'
import AncillariesModal from '@/components/flight/AncillariesModal'

export default function FlightOfferDetailPage() {
  const { offerId } = useParams()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const setBookingData = useBookingStore((s) => s.setBookingData)
  const { t } = useTranslation(['common', 'flights'])
  const fmt = useFormatCurrency()

  // Pull the search-page composition off the URL so we can render adult-vs-child
  // labels even before the offer fetch resolves. Once the offer arrives, its
  // `passenger_breakdown` is authoritative.
  const requestedAdults = Math.max(1, parseInt(searchParams.get('adults')) || parseInt(searchParams.get('pax')) || 1)
  const requestedChildAges = useMemo(() => {
    const raw = searchParams.get('child_ages') || ''
    return raw
      ? raw.split(',').map((s) => parseInt(s, 10)).filter((n) => !Number.isNaN(n) && n >= 0 && n <= 17)
      : []
  }, [searchParams])
  const requestedPax = requestedAdults + requestedChildAges.length

  const { data: offer, isLoading } = useQuery({
    queryKey: ['duffel-offer', offerId],
    queryFn: () => flightsApi.getOffer(offerId),
    select: (res) => res.data?.data,
  })

  // Live countdown to offer expiry so users see how much time they have left
  // before the airline rejects the booking with `offer_no_longer_available`.
  // Anything under ~3 minutes won't survive the Stripe + Duffel round-trip
  // — we proactively redirect rather than let the user spend time filling
  // forms only to get charged-then-refunded at the airline rejection.
  const [secondsLeft, setSecondsLeft] = useState(null)
  useEffect(() => {
    if (!offer?.expires_at) return undefined
    const compute = () => {
      try {
        const left = Math.floor((new Date(offer.expires_at).getTime() - Date.now()) / 1000)
        setSecondsLeft(left)
      } catch {
        setSecondsLeft(null)
      }
    }
    compute()
    const id = setInterval(compute, 1000)
    return () => clearInterval(id)
  }, [offer?.expires_at])

  useEffect(() => {
    if (secondsLeft == null) return
    // Hard fail at expiry, soft fail < 3 min so user has time to pay.
    if (secondsLeft <= 0) {
      toast.error(t('flights:detail.offerExpired', 'This offer has expired. Please search again.'))
      navigate('/flights')
    } else if (secondsLeft < 180 && secondsLeft >= 0) {
      // Show a sticky warning toast but don't kick them out yet.
      toast.warning(
        t('flights:detail.offerExpiringSoon', 'This offer is expiring soon — complete your booking quickly.'),
        { id: 'offer-expiring', duration: 8000 },
      )
    }
  }, [secondsLeft, navigate, t])

  const paxCount = offer?.passengers || requestedPax

  // Adult-first ordering matches both the search payload we sent to Duffel
  // (_build_passengers_payload) and the offer.passenger_breakdown the API
  // returns — passenger form #N maps to passenger_breakdown[N].
  const buildInitialPassengers = () => {
    const list = []
    for (let i = 0; i < requestedAdults; i += 1) {
      list.push({ ...emptyPassenger(), age: null })
    }
    for (const age of requestedChildAges) {
      list.push({ ...emptyPassenger(), age })
    }
    return list
  }

  const [passengers, setPassengers] = useState(buildInitialPassengers)

  const [trackedPaxCount, setTrackedPaxCount] = useState(requestedPax)
  if (offer && trackedPaxCount !== paxCount) {
    setTrackedPaxCount(paxCount)
    // Reconcile against the offer's authoritative passenger_breakdown so each
    // form is bound to the right Duffel passenger record (adult vs child).
    const breakdown = offer.passenger_breakdown || []
    setPassengers((prev) => {
      const next = []
      for (let i = 0; i < paxCount; i += 1) {
        const existing = prev[i] || emptyPassenger()
        const meta = breakdown[i] || {}
        const isChild = (meta.type && meta.type !== 'adult') || meta.age != null
        next.push({
          ...existing,
          age: isChild ? (meta.age ?? existing.age ?? null) : null,
        })
      }
      return next
    })
  }

  // Per-form labels surface the passenger type so users see "Adult #1" vs
  // "Child (age 8) #2" — matches Booking.com / Skyscanner UX.
  const passengerLabels = useMemo(() => {
    const breakdown = offer?.passenger_breakdown
    const labels = []
    for (let i = 0; i < paxCount; i += 1) {
      const meta = breakdown?.[i]
      if (meta?.type === 'infant_without_seat') {
        labels.push({ kind: 'infant', text: `Infant (lap)`, age: meta.age })
      } else if (meta?.age != null) {
        labels.push({ kind: 'child', text: `Child (age ${meta.age})`, age: meta.age })
      } else if ((meta?.type || 'adult') === 'adult') {
        labels.push({ kind: 'adult', text: 'Adult', age: null })
      } else {
        labels.push({ kind: meta.type, text: meta.type, age: meta.age })
      }
    }
    return labels
  }, [offer, paxCount])

  // ── Seat + ancillary state ──────────────────────────────────────────
  const [seatModalOpen, setSeatModalOpen] = useState(false)
  const [ancillaryModalOpen, setAncillaryModalOpen] = useState(false)
  const [selectedSeats, setSelectedSeats] = useState({}) // { paxIdx: service_id }
  const [seatSummaries, setSeatSummaries] = useState({}) // local label cache
  const [selectedServices, setSelectedServices] = useState([]) // [{id, quantity}]

  const { data: seatMaps = [] } = useQuery({
    queryKey: ['flight-seat-maps', offerId],
    queryFn: () => flightsApi.getSeatMaps(offerId),
    enabled: !!offerId,
    select: (res) => res.data?.data || [],
    staleTime: 60_000,
  })

  const { data: availableServices = [] } = useQuery({
    queryKey: ['flight-services', offerId],
    queryFn: () => flightsApi.getAvailableServices(offerId),
    enabled: !!offerId,
    select: (res) => res.data?.data || [],
    staleTime: 60_000,
  })

  // Sum of selected services' prices
  const servicesTotal = useMemo(() => {
    if (!selectedServices.length || !availableServices.length) return 0
    const byId = new Map(availableServices.map((s) => [s.id, s]))
    return selectedServices.reduce((acc, sel) => {
      const svc = byId.get(sel.id)
      if (!svc) return acc
      return acc + (parseFloat(svc.total_amount) || 0) * (sel.quantity || 0)
    }, 0)
  }, [selectedServices, availableServices])

  // Sum of selected seat prices
  const seatsTotal = useMemo(() => {
    return Object.values(seatSummaries).reduce(
      (acc, s) => acc + (parseFloat(s?.amount) || 0), 0,
    )
  }, [seatSummaries])

  const ancillariesTotal = servicesTotal + seatsTotal

  const perPaxAmount = useMemo(() => {
    if (!offer?.total_amount || !paxCount) return 0
    return offer.total_amount / paxCount
  }, [offer, paxCount])

  const handleBook = () => {
    if (!isAuthenticated) {
      // Preserve adults + child ages so post-login the form keeps the right
      // composition (would otherwise default to all-adults on return).
      const params = new URLSearchParams({ adults: String(requestedAdults) })
      if (requestedChildAges.length) params.set('child_ages', requestedChildAges.join(','))
      navigate(`/login?redirect=/flights/offers/${offerId}?${params.toString()}`)
      return
    }
    if (!arePassengersComplete(passengers, paxCount)) {
      toast.error(t('flights:errors.fillPassengerDetails'))
      return
    }

    const seatsForBooking = {}
    for (const [k, v] of Object.entries(selectedSeats)) {
      if (v) seatsForBooking[k] = v
    }

    // Split passengers list into adult count + child ages so the booking
    // payload mirrors what we sent Duffel at search time.
    const adultsInForm = passengers.filter((p) => p.age == null).length
    const childAgesInForm = passengers
      .filter((p) => p.age != null)
      .map((p) => Number(p.age))

    setBookingData({
      selectedFlight: {
        duffel_offer_id: offerId,
        total_amount: offer.total_amount + ancillariesTotal,
        currency: offer.currency,
        airline_name: offer.airline_name,
        airline_iata: offer.airline_iata,
        cabin_class: offer.cabin_class,
        slices: offer.slices,
        expires_at: offer.expires_at,
        passengers,
        quantity: paxCount,
        adults: adultsInForm,
        childAges: childAgesInForm,
        selected_services: selectedServices,
        selected_seats: seatsForBooking,
      },
    })
    navigate('/flights/checkout')
  }

  const handleSeatApply = (mapByPax) => {
    setSelectedSeats(mapByPax)
    // Build summaries from seat maps so we can display chips
    const allSeats = {}
    for (const segment of seatMaps) {
      for (const cabin of segment.cabins || []) {
        for (const row of cabin.rows || []) {
          for (const section of row.sections || []) {
            for (const el of section.elements || []) {
              if (el.type === 'seat' && el.available_services?.length) {
                for (const svc of el.available_services) {
                  allSeats[svc.id] = {
                    designator: el.designator,
                    amount: svc.total_amount,
                    currency: svc.total_currency,
                  }
                }
              }
            }
          }
        }
      }
    }
    const summaries = {}
    for (const [k, svcId] of Object.entries(mapByPax)) {
      const info = allSeats[svcId]
      if (info) summaries[k] = info
    }
    setSeatSummaries(summaries)
  }

  if (isLoading) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-4">
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  if (!offer) {
    return <div className="text-center py-20 text-gray-400">{t('flights:detail.notFound')}</div>
  }

  const seatsCount = Object.keys(seatSummaries).length
  const servicesCount = selectedServices.reduce((acc, s) => acc + (s.quantity || 0), 0)

  return (
    <>
      <Helmet>
        <title>{t('flights:detail.title')}</title>
      </Helmet>
      <div className="max-w-5xl mx-auto px-4 py-6">
        <Breadcrumb items={[
          { label: t('common:common.home'), to: '/' },
          { label: t('nav.flights'), to: '/flights' },
          { label: t('flights:detail.passengerDetails') },
        ]} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          <div className="lg:col-span-2 space-y-6">
            <FlightItineraryBlock
              slices={offer.slices}
              airlineName={offer.airline_name}
              airlineIata={offer.airline_iata}
              cabinClass={offer.cabin_class}
            />

            <FareRulesAccordion conditions={offer.conditions} />

            {/* Add-on actions */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setSeatModalOpen(true)}
                className="border rounded-xl p-4 hover:bg-primary/5 transition-colors text-left flex items-start gap-3"
              >
                <Armchair className="w-6 h-6 text-primary shrink-0" />
                <div className="flex-1">
                  <p className="font-semibold text-sm text-gray-900">
                    {t('flights:seats.chooseSeats')}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {seatsCount > 0
                      ? `${seatsCount} / ${paxCount} ${t('flights:seats.selected').toLowerCase()}`
                      : (seatMaps.length === 0
                        ? t('flights:seats.noSeatMap')
                        : t('flights:seats.subtitle'))}
                  </p>
                </div>
              </button>
              <button
                type="button"
                onClick={() => setAncillaryModalOpen(true)}
                disabled={availableServices.length === 0}
                className="border rounded-xl p-4 hover:bg-primary/5 transition-colors text-left flex items-start gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Briefcase className="w-6 h-6 text-primary shrink-0" />
                <div className="flex-1">
                  <p className="font-semibold text-sm text-gray-900">
                    {t('flights:ancillaries.addBaggage')}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {availableServices.length === 0
                      ? t('flights:ancillaries.noServices')
                      : (servicesCount > 0
                        ? `${servicesCount} ${t('flights:ancillaries.title').toLowerCase()}`
                        : t('flights:ancillaries.subtitle'))}
                  </p>
                </div>
              </button>
            </div>

            <div>
              <h2 className="font-heading font-bold text-lg flex items-center gap-2 mb-3">
                <User className="w-5 h-5" /> {t('flights:detail.passengerDetails')}
              </h2>
              <MultiPassengerForm
                passengers={passengers}
                onChange={setPassengers}
                count={paxCount}
                labels={passengerLabels}
              />
            </div>
          </div>

          {/* Right column — price */}
          <div className="lg:col-span-1 space-y-4">
            <div className="sticky top-20 space-y-4">
              <div className="bg-white border rounded-xl p-5 shadow-sm space-y-4">
                <div className="text-center">
                  <p className="text-3xl font-bold text-gray-900">
                    {fmt(perPaxAmount, offer.currency)}
                  </p>
                  <p className="text-xs text-gray-400">{t('flights:detail.perPersonTotalFare')}</p>
                  {paxCount > 1 && (
                    <p className="text-sm text-gray-600 mt-2">
                      {t('flights:detail.totalAllPax')}:{' '}
                      <strong>{fmt(offer.total_amount, offer.currency)}</strong>
                      <span className="text-xs text-gray-400 ml-1">× {paxCount}</span>
                    </p>
                  )}
                </div>

                {secondsLeft != null && secondsLeft > 0 && (
                  <div className={`flex items-center justify-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg ${
                    secondsLeft < 180
                      ? 'bg-error/10 text-error'
                      : secondsLeft < 300
                        ? 'bg-amber-50 text-amber-700'
                        : 'bg-gray-50 text-gray-500'
                  }`}>
                    <Clock className="w-3.5 h-3.5" />
                    {t('flights:detail.offerExpiresIn', 'Offer expires in')}{' '}
                    {Math.floor(secondsLeft / 60)}m {secondsLeft % 60}s
                  </div>
                )}

                <div className="text-sm space-y-2 text-gray-600">
                  <div className="flex items-center gap-2">
                    <PlaneTakeoff className="w-4 h-4 text-gray-400" />
                    <span>{offer.slices?.[0]?.origin} → {offer.slices?.[0]?.destination}</span>
                  </div>
                  {offer.slices?.length > 1 && (
                    <div className="flex items-center gap-2">
                      <PlaneLanding className="w-4 h-4 text-gray-400" />
                      <span>{offer.slices[1].origin} → {offer.slices[1].destination}</span>
                    </div>
                  )}
                  {offer.cabin_class && (
                    <p className="capitalize">{offer.cabin_class.replace('_', ' ')} {t('flights:detail.class')}</p>
                  )}
                </div>

                <hr />

                <ul className="text-xs text-gray-500 space-y-1">
                  <li className="flex items-center gap-1">
                    <CheckCircle className="w-3 h-3 text-success" /> {t('flights:detail.poweredByDuffel')}
                  </li>
                  <li className="flex items-center gap-1">
                    <CheckCircle className="w-3 h-3 text-success" /> {t('flights:detail.realtimeInventory')}
                  </li>
                </ul>

                <button
                  onClick={handleBook}
                  className="w-full bg-accent hover:bg-accent/90 text-white font-bold py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
                >
                  <CreditCard className="w-5 h-5" />
                  {t('flights:detail.continueCheckout')}
                </button>
              </div>

              <FareBreakdownCard
                offer={offer}
                paxCount={paxCount}
                servicesTotal={ancillariesTotal}
              />
            </div>
          </div>
        </div>
      </div>

      <SeatMapModal
        open={seatModalOpen}
        onClose={() => setSeatModalOpen(false)}
        seatMaps={seatMaps}
        passengers={passengers}
        initialSelected={(() => {
          const out = {}
          for (const [k, info] of Object.entries(seatSummaries)) {
            out[k] = { _designator: info.designator, service_id: selectedSeats[k] }
          }
          return out
        })()}
        onApply={handleSeatApply}
      />
      <AncillariesModal
        open={ancillaryModalOpen}
        onClose={() => setAncillaryModalOpen(false)}
        services={availableServices}
        passengers={passengers}
        initialSelection={selectedServices}
        onApply={setSelectedServices}
      />
    </>
  )
}
