import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSearchStore } from '@/store/searchStore'
import { useDebounce } from '@/hooks/useDebounce'
import { useQuery } from '@tanstack/react-query'
import { searchCities } from '@/api/nominatimApi'
import { Search, MapPin, Calendar, Users } from 'lucide-react'
import { format } from 'date-fns'
import DateRangeCalendar from '@/components/common/DateRangeCalendar'
import { useTranslation } from 'react-i18next'

export default function SearchBar({ variant = 'hero' }) {
  const navigate = useNavigate()
  const { t } = useTranslation('common')
  const { destination, checkIn, checkOut, guests, searchType, setDestination, setDates, setGuests, setSearchType } = useSearchStore()

  const [localDest, setLocalDest] = useState(destination)
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [showGuests, setShowGuests] = useState(false)
  const [showCalendar, setShowCalendar] = useState(false)
  const calendarWrapRef = useRef(null)
  const guestsWrapRef = useRef(null)
  const debouncedDest = useDebounce(localDest, 300)

  const { data: suggestions, isFetching: suggestionsLoading } = useQuery({
    queryKey: ['location-suggestions', debouncedDest],
    queryFn: () => searchCities(debouncedDest),
    enabled: debouncedDest.length >= 2,
    staleTime: 60_000,
    placeholderData: [],
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

  useEffect(() => {
    if (!showCalendar) return
    const handleDocMouseDown = (e) => {
      const el = calendarWrapRef.current
      if (!el) return
      if (el.contains(e.target)) return
      setShowCalendar(false)
    }
    document.addEventListener('mousedown', handleDocMouseDown)
    return () => document.removeEventListener('mousedown', handleDocMouseDown)
  }, [showCalendar])

  useEffect(() => {
    if (!showGuests) return
    const handleDocMouseDown = (e) => {
      const el = guestsWrapRef.current
      if (!el) return
      if (el.contains(e.target)) return
      setShowGuests(false)
    }
    document.addEventListener('mousedown', handleDocMouseDown)
    return () => document.removeEventListener('mousedown', handleDocMouseDown)
  }, [showGuests])

  const isHero = variant === 'hero'

  return (
    <div className={isHero ? 'w-full max-w-4xl mx-auto' : ''}>
      {isHero && (
        <div className="flex gap-1 mb-3">
          {['hotels', 'tours'].map((type) => (
            <button
              key={type}
              onClick={() => setSearchType(type)}
              className={`px-4 py-2 rounded-t-lg text-sm font-semibold transition-colors capitalize
                ${searchType === type ? 'bg-white text-primary' : 'bg-white/20 text-white hover:bg-white/30'}`}
            >
              {type === 'hotels' ? t('searchBar.hotels') : t('searchBar.toursActivities')}
            </button>
          ))}
        </div>
      )}

      <div className={`bg-white rounded-xl shadow-xl ${isHero ? 'p-2' : 'p-1'} flex flex-col md:flex-row gap-2`}>
        <div className="relative flex-1 min-w-0">
          <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder={t('searchBar.whereGoing')}
            value={localDest}
            onChange={(e) => { setLocalDest(e.target.value); setShowSuggestions(true) }}
            onFocus={() => setShowSuggestions(true)}
            onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
            className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
          />
          {showSuggestions && debouncedDest.length >= 2 && (
            <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden">
              {suggestionsLoading && (!suggestions || suggestions.length === 0) ? (
                <div className="px-4 py-3 space-y-2">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-gray-100 animate-pulse shrink-0" />
                      <div className="flex-1 space-y-1">
                        <div className="h-3.5 bg-gray-100 rounded animate-pulse w-2/3" />
                        <div className="h-3 bg-gray-100 rounded animate-pulse w-1/2" />
                      </div>
                    </div>
                  ))}
                </div>
              ) : suggestions?.length > 0 ? (
                <>
                  {suggestions.map((s, i) => (
                    <button
                      key={i}
                      onMouseDown={() => { setLocalDest(s.city); setShowSuggestions(false) }}
                      className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-blue-50 text-left transition-colors"
                    >
                      <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                        <MapPin className="w-4 h-4 text-primary" />
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">{s.city}</p>
                        <p className="text-xs text-gray-500">
                          {[s.state, s.country].filter(Boolean).join(', ')}
                        </p>
                      </div>
                    </button>
                  ))}
                </>
              ) : (
                <div className="px-4 py-3 text-sm text-gray-400">{t('searchBar.noDestinations')}</div>
              )}
            </div>
          )}
        </div>

        <div className="relative flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-2 min-w-[240px]">
          <Calendar className="w-5 h-5 text-gray-400 shrink-0" />

          <div className="flex flex-1 items-center">
            <button
              type="button"
              onClick={() => setShowCalendar((s) => !s)}
              className="flex-1 text-center focus:outline-none"
            >
              <span className={`text-sm whitespace-nowrap ${checkIn ? 'text-primary font-bold' : 'text-gray-400'}`}>
                {checkIn ? format(checkIn, 'MMM dd') : t('hotels:search.checkIn')}
              </span>
            </button>

            <span className="text-gray-300 shrink-0 px-1">—</span>

            <button
              type="button"
              onClick={() => setShowCalendar((s) => !s)}
              className="flex-1 text-center focus:outline-none"
            >
              <span className={`text-sm whitespace-nowrap ${checkOut ? 'text-primary font-bold' : 'text-gray-400'}`}>
                {checkOut ? format(checkOut, 'MMM dd') : t('hotels:search.checkOut')}
              </span>
            </button>
          </div>

          {showCalendar && (
            <div ref={calendarWrapRef} className="absolute left-0 top-full z-50 mt-2">
              <DateRangeCalendar
                checkIn={checkIn}
                checkOut={checkOut}
                minDate={new Date()}
                onChange={(from, to) => {
                  setDates(from, to)
                }}
              />
            </div>
          )}
        </div>

        <div className="relative" ref={guestsWrapRef}>
          <button
            onClick={() => setShowGuests(!showGuests)}
            className="flex items-center gap-2 border border-gray-200 rounded-lg px-3 py-3 text-sm w-full md:w-auto min-w-[140px]"
          >
            <Users className="w-5 h-5 text-gray-400" />
            <span>{totalGuests} {totalGuests > 1 ? t('common.guests') : t('common.guests')}, {guests.rooms} {t('searchBar.rooms')}</span>
          </button>
          {showGuests && (
            <div className="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg z-50 p-4 w-64">
              {[
                { label: t('searchBar.adults'), key: 'adults', min: 1 },
                { label: t('searchBar.children'), key: 'children', min: 0 },
                { label: t('searchBar.rooms'), key: 'rooms', min: 1 },
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
                {t('common.done')}
              </button>
            </div>
          )}
        </div>

        <button
          type="button"
          onClick={handleSearch}
          className="bg-accent hover:bg-accent-dark text-white font-semibold px-6 py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
        >
          <Search className="w-5 h-5" />
          {t('common.search')}
        </button>
      </div>
    </div>
  )
}
