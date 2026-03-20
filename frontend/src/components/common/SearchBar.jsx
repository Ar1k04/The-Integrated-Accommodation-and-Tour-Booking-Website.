import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSearchStore } from '@/store/searchStore'
import { useDebounce } from '@/hooks/useDebounce'
import { useQuery } from '@tanstack/react-query'
import { hotelsApi } from '@/api/hotelsApi'
import { Search, MapPin, Calendar, Users } from 'lucide-react'
import { format } from 'date-fns'

export default function SearchBar({ variant = 'hero' }) {
  const navigate = useNavigate()
  const { destination, checkIn, checkOut, guests, searchType, setDestination, setDates, setGuests, setSearchType } = useSearchStore()

  const [localDest, setLocalDest] = useState(destination)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [showGuests, setShowGuests] = useState(false)
  const debouncedDest = useDebounce(localDest, 300)

  const { data: suggestions } = useQuery({
    queryKey: ['hotel-search-suggestions', debouncedDest],
    queryFn: () => hotelsApi.list({ search: debouncedDest, per_page: 5 }),
    enabled: debouncedDest.length >= 2,
    select: (res) => res.data?.items || [],
  })

  const totalGuests = guests.adults + guests.children

  const handleSearch = () => {
    setDestination(localDest)
    if (searchType === 'hotels') {
      const params = new URLSearchParams()
      if (localDest) params.set('city', localDest)
      if (checkIn) params.set('check_in', format(checkIn, 'yyyy-MM-dd'))
      if (checkOut) params.set('check_out', format(checkOut, 'yyyy-MM-dd'))
      if (totalGuests) params.set('guests', totalGuests)
      navigate(`/hotels/search?${params.toString()}`)
    } else {
      const params = new URLSearchParams()
      if (localDest) params.set('city', localDest)
      navigate(`/tours?${params.toString()}`)
    }
  }

  const isHero = variant === 'hero'

  return (
    <div className={isHero ? 'w-full max-w-4xl mx-auto' : ''}>
      {isHero && (
        <div className="flex gap-1 mb-3">
          {['hotels', 'tours'].map((t) => (
            <button
              key={t}
              onClick={() => setSearchType(t)}
              className={`px-4 py-2 rounded-t-lg text-sm font-semibold transition-colors capitalize
                ${searchType === t ? 'bg-white text-primary' : 'bg-white/20 text-white hover:bg-white/30'}`}
            >
              {t === 'hotels' ? 'Hotels' : 'Tours & Activities'}
            </button>
          ))}
        </div>
      )}

      <div className={`bg-white rounded-xl shadow-xl ${isHero ? 'p-2' : 'p-1'} flex flex-col md:flex-row gap-2`}>
        <div className="relative flex-1 min-w-0">
          <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder="Where are you going?"
            value={localDest}
            onChange={(e) => { setLocalDest(e.target.value); setShowSuggestions(true) }}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
            className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          />
          {showSuggestions && suggestions?.length > 0 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white border rounded-lg shadow-lg z-50 max-h-48 overflow-y-auto">
              {suggestions.map((h) => (
                <button
                  key={h.id}
                  onMouseDown={() => { setLocalDest(h.city); setShowSuggestions(false) }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 text-left"
                >
                  <MapPin className="w-4 h-4 text-gray-400 shrink-0" />
                  <div>
                    <p className="text-sm font-medium">{h.name}</p>
                    <p className="text-xs text-gray-500">{h.city}, {h.country}</p>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2 min-w-[200px]">
          <Calendar className="w-5 h-5 text-gray-400 shrink-0" />
          <input
            type="date"
            value={checkIn ? format(checkIn, 'yyyy-MM-dd') : ''}
            onChange={(e) => setDates(e.target.value ? new Date(e.target.value) : null, checkOut)}
            min={format(new Date(), 'yyyy-MM-dd')}
            className="text-sm flex-1 min-w-0 focus:outline-none"
            placeholder="Check-in"
          />
          <span className="text-gray-300">—</span>
          <input
            type="date"
            value={checkOut ? format(checkOut, 'yyyy-MM-dd') : ''}
            onChange={(e) => setDates(checkIn, e.target.value ? new Date(e.target.value) : null)}
            min={checkIn ? format(new Date(checkIn.getTime() + 86400000), 'yyyy-MM-dd') : format(new Date(), 'yyyy-MM-dd')}
            className="text-sm flex-1 min-w-0 focus:outline-none"
            placeholder="Check-out"
          />
        </div>

        <div className="relative">
          <button
            onClick={() => setShowGuests(!showGuests)}
            className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-3 text-sm w-full md:w-auto min-w-[140px]"
          >
            <Users className="w-5 h-5 text-gray-400" />
            <span>{totalGuests} Guest{totalGuests > 1 ? 's' : ''}, {guests.rooms} Room{guests.rooms > 1 ? 's' : ''}</span>
          </button>
          {showGuests && (
            <div className="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg z-50 p-4 w-64">
              {[
                { label: 'Adults', key: 'adults', min: 1 },
                { label: 'Children', key: 'children', min: 0 },
                { label: 'Rooms', key: 'rooms', min: 1 },
              ].map(({ label, key, min }) => (
                <div key={key} className="flex items-center justify-between py-2">
                  <span className="text-sm">{label}</span>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setGuests({ ...guests, [key]: Math.max(min, guests[key] - 1) })}
                      className="w-8 h-8 rounded-full border flex items-center justify-center hover:bg-gray-100 text-sm"
                    >-</button>
                    <span className="w-6 text-center text-sm font-medium">{guests[key]}</span>
                    <button
                      onClick={() => setGuests({ ...guests, [key]: guests[key] + 1 })}
                      className="w-8 h-8 rounded-full border flex items-center justify-center hover:bg-gray-100 text-sm"
                    >+</button>
                  </div>
                </div>
              ))}
              <button onClick={() => setShowGuests(false)}
                className="w-full mt-2 bg-primary text-white rounded-lg py-2 text-sm font-medium">
                Done
              </button>
            </div>
          )}
        </div>

        <button
          onClick={handleSearch}
          className="bg-accent hover:bg-accent-dark text-white font-semibold px-6 py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <Search className="w-5 h-5" />
          Search
        </button>
      </div>
    </div>
  )
}
