import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { flightsApi } from '@/api/flightsApi'
import { useBookingStore } from '@/store/bookingStore'
import { useAuth } from '@/hooks/useAuth'
import Breadcrumb from '@/components/common/Breadcrumb'
import Skeleton from '@/components/common/Skeleton'
import { formatCurrency } from '@/utils/formatters'
import {
  PlaneTakeoff, PlaneLanding, Clock, ChevronRight,
  User, CreditCard, Calendar, CheckCircle,
} from 'lucide-react'
import { format, addYears } from 'date-fns'

const TITLE_OPTIONS = ['mr', 'mrs', 'ms', 'dr']
const GENDER_OPTIONS = [{ value: 'M', label: 'Male' }, { value: 'F', label: 'Female' }]

export default function FlightOfferDetailPage() {
  const { offerId } = useParams()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const setBookingData = useBookingStore((s) => s.setBookingData)

  const [passenger, setPassenger] = useState({
    first_name: '',
    last_name: '',
    email: '',
    gender: 'M',
    born_on: format(addYears(new Date(), -30), 'yyyy-MM-dd'),
    title: 'mr',
    phone_number: '',
  })

  const { data: offer, isLoading } = useQuery({
    queryKey: ['duffel-offer', offerId],
    queryFn: () => flightsApi.getOffer(offerId),
    select: (res) => res.data?.data,
  })

  const formatTime = (iso) => {
    if (!iso) return '—'
    try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false }) }
    catch { return iso }
  }

  const formatDateFull = (iso) => {
    if (!iso) return '—'
    try { return new Date(iso).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false }) }
    catch { return iso }
  }

  const handleBook = () => {
    if (!isAuthenticated) {
      navigate(`/login?redirect=/flights/offers/${offerId}`)
      return
    }
    if (!passenger.first_name || !passenger.last_name || !passenger.email || !passenger.born_on) {
      toast.error('Please fill in all required passenger details')
      return
    }
    setBookingData({
      selectedFlight: {
        duffel_offer_id: offerId,
        total_amount: offer.total_amount,
        currency: offer.currency,
        airline_name: offer.airline_name,
        slices: offer.slices,
        passenger: { ...passenger },
      },
    })
    navigate('/bookings/new?type=flight')
  }

  const setPax = (field, value) => setPassenger((p) => ({ ...p, [field]: value }))

  if (isLoading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 space-y-4">
        <Skeleton className="h-48 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
    )
  }

  if (!offer) return <div className="text-center py-20 text-gray-400">Offer not found or expired</div>

  return (
    <>
      <Helmet>
        <title>Flight Details — TravelBooking</title>
      </Helmet>
      <div className="max-w-4xl mx-auto px-4 py-6">
        <Breadcrumb items={[
          { label: 'Home', to: '/' },
          { label: 'Flights', to: '/flights' },
          { label: 'Flight Details' },
        ]} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          {/* Left: itinerary + passenger form */}
          <div className="lg:col-span-2 space-y-6">
            {/* Itinerary */}
            <div className="bg-white border rounded-xl p-6">
              <div className="flex items-center gap-2 mb-5">
                <span className="bg-primary/10 text-primary text-sm font-bold px-3 py-1 rounded-full">
                  {offer.airline_iata}
                </span>
                <h2 className="font-heading font-bold text-lg">{offer.airline_name}</h2>
                {offer.cabin_class && (
                  <span className="text-xs text-gray-400 capitalize bg-gray-100 px-2 py-0.5 rounded-full">
                    {offer.cabin_class.replace('_', ' ')}
                  </span>
                )}
              </div>

              {offer.slices?.map((slice, si) => (
                <div key={si} className={si > 0 ? 'mt-6 pt-6 border-t' : ''}>
                  <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                    {si === 0 ? 'Outbound Flight' : 'Return Flight'}
                  </p>
                  {slice.segments?.map((seg, i) => (
                    <div key={i} className={i > 0 ? 'mt-4 pt-4 border-t border-dashed' : ''}>
                      <div className="flex items-center gap-4">
                        <div className="text-center w-16">
                          <p className="text-2xl font-bold text-gray-900">{formatTime(seg.departure_at)}</p>
                          <p className="text-xs font-semibold text-primary">{seg.origin_iata}</p>
                          <p className="text-xs text-gray-400 truncate">{seg.origin_name}</p>
                        </div>
                        <div className="flex-1 flex flex-col items-center gap-1">
                          {seg.duration && (
                            <span className="text-xs text-gray-400 flex items-center gap-1">
                              <Clock className="w-3 h-3" />{seg.duration}
                            </span>
                          )}
                          <div className="w-full flex items-center">
                            <PlaneTakeoff className="w-4 h-4 text-gray-300 mr-1 shrink-0" />
                            <div className="flex-1 h-0.5 bg-gray-200" />
                            <PlaneLanding className="w-4 h-4 text-gray-300 ml-1 shrink-0" />
                          </div>
                          <span className="text-xs text-gray-400">
                            {seg.flight_number}
                            {seg.aircraft ? ` · ${seg.aircraft}` : ''}
                          </span>
                        </div>
                        <div className="text-center w-16">
                          <p className="text-2xl font-bold text-gray-900">{formatTime(seg.arrival_at)}</p>
                          <p className="text-xs font-semibold text-primary">{seg.destination_iata}</p>
                          <p className="text-xs text-gray-400 truncate">{seg.destination_name}</p>
                        </div>
                      </div>
                      <p className="text-xs text-gray-400 mt-2">{formatDateFull(seg.departure_at)}</p>
                    </div>
                  ))}
                </div>
              ))}
            </div>

            {/* Passenger form */}
            <div className="bg-white border rounded-xl p-6 space-y-4">
              <h2 className="font-heading font-bold text-lg flex items-center gap-2">
                <User className="w-5 h-5" /> Passenger Details
              </h2>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Title *</label>
                  <select
                    value={passenger.title}
                    onChange={(e) => setPax('title', e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    {TITLE_OPTIONS.map((t) => <option key={t} value={t}>{t.toUpperCase()}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Gender *</label>
                  <select
                    value={passenger.gender}
                    onChange={(e) => setPax('gender', e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    {GENDER_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">First Name *</label>
                  <input
                    value={passenger.first_name}
                    onChange={(e) => setPax('first_name', e.target.value)}
                    placeholder="John"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Last Name *</label>
                  <input
                    value={passenger.last_name}
                    onChange={(e) => setPax('last_name', e.target.value)}
                    placeholder="Doe"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Email *</label>
                  <input
                    type="email"
                    value={passenger.email}
                    onChange={(e) => setPax('email', e.target.value)}
                    placeholder="john@example.com"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Date of Birth *</label>
                  <input
                    type="date"
                    value={passenger.born_on}
                    max={format(new Date(), 'yyyy-MM-dd')}
                    onChange={(e) => setPax('born_on', e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-gray-500 mb-1">Phone Number (optional)</label>
                  <input
                    type="tel"
                    value={passenger.phone_number}
                    onChange={(e) => setPax('phone_number', e.target.value)}
                    placeholder="+84 900 000 000"
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Right: price summary */}
          <div className="lg:col-span-1">
            <div className="sticky top-20 bg-white border rounded-xl p-5 shadow-sm space-y-4">
              <div className="text-center">
                <p className="text-3xl font-bold text-gray-900">
                  {formatCurrency(offer.total_amount, offer.currency)}
                </p>
                <p className="text-xs text-gray-400">per person · total fare</p>
              </div>

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
                  <p className="capitalize">{offer.cabin_class.replace('_', ' ')} class</p>
                )}
              </div>

              <hr />

              <ul className="text-xs text-gray-500 space-y-1">
                <li className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-success" /> Powered by Duffel</li>
                <li className="flex items-center gap-1"><CheckCircle className="w-3 h-3 text-success" /> Real-time inventory</li>
              </ul>

              <button
                onClick={handleBook}
                className="w-full bg-accent hover:bg-accent/90 text-white font-bold py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
              >
                <CreditCard className="w-5 h-5" />
                Continue to Checkout
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
