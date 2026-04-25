import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { flightsApi } from '@/api/flightsApi'
import FlightOfferCard from '@/components/flight/FlightOfferCard'
import Skeleton from '@/components/common/Skeleton'
import { format, addDays } from 'date-fns'
import { PlaneTakeoff, ArrowRight, ArrowLeftRight } from 'lucide-react'

const AIRPORTS = [
  { code: 'HAN', name: 'Hanoi (HAN)' },
  { code: 'SGN', name: 'Ho Chi Minh City (SGN)' },
  { code: 'DAD', name: 'Da Nang (DAD)' },
  { code: 'BKK', name: 'Bangkok (BKK)' },
  { code: 'SIN', name: 'Singapore (SIN)' },
  { code: 'KUL', name: 'Kuala Lumpur (KUL)' },
  { code: 'NRT', name: 'Tokyo Narita (NRT)' },
  { code: 'ICN', name: 'Seoul Incheon (ICN)' },
  { code: 'LHR', name: 'London Heathrow (LHR)' },
  { code: 'CDG', name: 'Paris CDG (CDG)' },
  { code: 'JFK', name: 'New York JFK (JFK)' },
  { code: 'DXB', name: 'Dubai (DXB)' },
]

const CABIN_CLASSES = [
  { value: 'economy', label: 'Economy' },
  { value: 'premium_economy', label: 'Premium Economy' },
  { value: 'business', label: 'Business' },
  { value: 'first', label: 'First' },
]

export default function FlightsSearchPage() {
  const navigate = useNavigate()
  const today = format(new Date(), 'yyyy-MM-dd')

  const [tripType, setTripType] = useState('one-way')
  const [origin, setOrigin] = useState('HAN')
  const [destination, setDestination] = useState('SGN')
  const [departDate, setDepartDate] = useState(format(addDays(new Date(), 7), 'yyyy-MM-dd'))
  const [returnDate, setReturnDate] = useState(format(addDays(new Date(), 14), 'yyyy-MM-dd'))
  const [passengers, setPassengers] = useState(1)
  const [cabinClass, setCabinClass] = useState('economy')
  const [loading, setLoading] = useState(false)
  const [offers, setOffers] = useState(null)

  const handleSearch = async () => {
    if (!origin || !destination) { toast.error('Please select origin and destination'); return }
    if (origin === destination) { toast.error('Origin and destination cannot be the same'); return }
    if (!departDate) { toast.error('Please select a departure date'); return }
    if (tripType === 'round-trip' && !returnDate) { toast.error('Please select a return date'); return }
    if (tripType === 'round-trip' && returnDate <= departDate) {
      toast.error('Return date must be after departure date'); return
    }

    setLoading(true)
    setOffers(null)
    try {
      const params = {
        origin,
        destination,
        depart_date: departDate,
        passengers,
        cabin_class: cabinClass,
      }
      if (tripType === 'round-trip') params.return_date = returnDate

      const res = await flightsApi.search(params)
      setOffers(res.data?.data || [])
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Flight search unavailable — try again later')
      setOffers([])
    } finally {
      setLoading(false)
    }
  }

  const handleSwap = () => {
    const tmp = origin
    setOrigin(destination)
    setDestination(tmp)
  }

  const handleSelectOffer = (offer) => {
    navigate(`/flights/offers/${offer.duffel_offer_id}`)
  }

  return (
    <>
      <Helmet>
        <title>Search Flights — TravelBooking</title>
      </Helmet>

      {/* Hero */}
      <div className="bg-primary text-white py-10">
        <div className="max-w-5xl mx-auto px-4">
          <h1 className="font-heading text-3xl font-bold mb-1 flex items-center gap-3">
            <PlaneTakeoff className="w-8 h-8" /> Search Flights
          </h1>
          <p className="text-white/70 text-sm">Powered by Duffel — real airline inventory</p>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Search form */}
        <div className="bg-white rounded-2xl border shadow-sm p-6 mb-8 space-y-4">
          {/* Trip type */}
          <div className="flex gap-4 text-sm">
            {['one-way', 'round-trip'].map((t) => (
              <button
                key={t}
                onClick={() => setTripType(t)}
                className={`px-4 py-1.5 rounded-full font-medium transition-colors ${
                  tripType === t
                    ? 'bg-primary text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {t === 'one-way' ? 'One Way' : 'Round Trip'}
              </button>
            ))}
          </div>

          {/* Airport selectors */}
          <div className="grid grid-cols-1 sm:grid-cols-[1fr,auto,1fr] gap-3 items-end">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">From</label>
              <select
                value={origin}
                onChange={(e) => setOrigin(e.target.value)}
                className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                {AIRPORTS.map((a) => (
                  <option key={a.code} value={a.code}>{a.name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleSwap}
              className="p-2 rounded-full hover:bg-gray-100 transition-colors self-end mb-0.5"
              title="Swap"
            >
              <ArrowLeftRight className="w-4 h-4 text-gray-500" />
            </button>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">To</label>
              <select
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                {AIRPORTS.map((a) => (
                  <option key={a.code} value={a.code}>{a.name}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Dates, passengers, cabin */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Departure</label>
              <input
                type="date"
                value={departDate}
                min={today}
                onChange={(e) => setDepartDate(e.target.value)}
                className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            {tripType === 'round-trip' && (
              <div>
                <label className="block text-xs font-medium text-gray-500 mb-1">Return</label>
                <input
                  type="date"
                  value={returnDate}
                  min={departDate || today}
                  onChange={(e) => setReturnDate(e.target.value)}
                  className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                />
              </div>
            )}
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Passengers</label>
              <input
                type="number"
                value={passengers}
                min={1}
                max={9}
                onChange={(e) => setPassengers(parseInt(e.target.value) || 1)}
                className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Cabin Class</label>
              <select
                value={cabinClass}
                onChange={(e) => setCabinClass(e.target.value)}
                className="w-full border rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                {CABIN_CLASSES.map((c) => (
                  <option key={c.value} value={c.value}>{c.label}</option>
                ))}
              </select>
            </div>
          </div>

          <button
            onClick={handleSearch}
            disabled={loading}
            className="w-full bg-primary hover:bg-primary/90 disabled:bg-gray-300 text-white font-bold py-3 rounded-xl transition-colors flex items-center justify-center gap-2"
          >
            <PlaneTakeoff className="w-5 h-5" />
            {loading ? 'Searching...' : 'Search Flights'}
          </button>
        </div>

        {/* Results */}
        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-28 rounded-xl" />)}
          </div>
        )}

        {!loading && offers !== null && offers.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <PlaneTakeoff className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No flights found for this route and date.</p>
            <p className="text-sm mt-1">Try different dates or airports.</p>
          </div>
        )}

        {!loading && offers?.length > 0 && (
          <>
            <p className="text-sm text-gray-500 mb-4">
              Found <strong>{offers.length}</strong> flight{offers.length !== 1 ? 's' : ''} ·{' '}
              {origin} <ArrowRight className="w-3 h-3 inline" /> {destination}
            </p>
            <div className="space-y-3">
              {offers.map((offer) => (
                <FlightOfferCard key={offer.duffel_offer_id} offer={offer} onSelect={handleSelectOffer} />
              ))}
            </div>
          </>
        )}
      </div>
    </>
  )
}
