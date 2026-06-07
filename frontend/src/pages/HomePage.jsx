import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { featuredApi } from '@/api/featuredApi'
import { searchDestinationPhoto } from '@/api/unsplashApi'
import SearchBar from '@/components/common/SearchBar'
import HotelCard from '@/components/hotel/HotelCard'
import TourCard from '@/components/tour/TourCard'
import { HotelCardSkeleton, TourCardSkeleton } from '@/components/common/Skeleton'
import { Shield, Clock, Headphones, CreditCard, ChevronRight } from 'lucide-react'

// `searchCity` must match the LiteAPI city name in our `cities` table exactly
// (the backend resolves country_code via `name_norm = f_unaccent(searchCity)`),
// and `cc` pins the country so ambiguous names don't resolve to the wrong town
// (e.g. bare "Bali" matches a tiny village in India, not the Indonesian island
// whose LiteAPI city is "Denpasar"). `name` is just the card label.
const FEATURED_DESTINATIONS = [
  { key: 'hanoi', name: 'Ha Noi', country: 'Vietnam', searchCity: 'Hanoi', cc: 'VN', query: 'Hoan Kiem lake Hanoi' },
  { key: 'bangkok', name: 'Bangkok', country: 'Thailand', searchCity: 'Bangkok', cc: 'TH' },
  { key: 'tokyo', name: 'Tokyo', country: 'Japan', searchCity: 'Tokyo', cc: 'JP' },
  { key: 'paris', name: 'Paris', country: 'France', searchCity: 'Paris', cc: 'FR' },
  { key: 'bali', name: 'Bali', country: 'Indonesia', searchCity: 'Denpasar', cc: 'ID' },
  { key: 'seoul', name: 'Seoul', country: 'South Korea', searchCity: 'Seoul', cc: 'KR' },
]

// Gradient fallbacks per destination (shown while photo loads or if Unsplash key is absent)
const DEST_GRADIENTS = {
  'Ha Noi': 'from-red-500 to-orange-400',
  'Bangkok': 'from-yellow-500 to-amber-400',
  'Tokyo': 'from-pink-500 to-rose-400',
  'Paris': 'from-blue-500 to-indigo-400',
  'Bali': 'from-emerald-500 to-teal-400',
  'Seoul': 'from-purple-500 to-violet-400',
}

function DestinationCard({ dest }) {
  const { t } = useTranslation('common')
  const name = t(`home.destinations.${dest.key}.name`, dest.name)
  const country = t(`home.destinations.${dest.key}.country`, dest.country)
  const { data: photoUrl, isLoading } = useQuery({
    queryKey: ['unsplash-photo', dest.name],
    queryFn: () => searchDestinationPhoto(dest.query || `${dest.name} ${dest.country}`),
    staleTime: 90 * 60 * 1000,
    gcTime: 90 * 60 * 1000,
  })

  const gradient = DEST_GRADIENTS[dest.name] || 'from-gray-500 to-gray-400'

  return (
    <Link
      to={`/hotels/search?city=${encodeURIComponent(dest.searchCity || dest.name)}${dest.cc ? `&country=${dest.cc}` : ''}`}
      className="shrink-0 w-48 group"
    >
      <div className="relative h-32 rounded-xl overflow-hidden">
        {/* Gradient background always present as base */}
        <div className={`absolute inset-0 bg-gradient-to-br ${gradient}`} />

        {/* Skeleton shimmer while fetching */}
        {isLoading && (
          <div className="absolute inset-0 bg-gray-200 animate-pulse" />
        )}

        {/* Photo from Unsplash */}
        {photoUrl && (
          <img
            src={photoUrl}
            alt={name}
            className="absolute inset-0 w-full h-full object-cover group-hover:scale-110 transition-transform duration-500"
          />
        )}

        <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
        <div className="absolute bottom-3 left-3 text-white">
          <p className="font-bold text-sm">{name}</p>
          <p className="text-xs opacity-80">{country}</p>
        </div>
      </div>
    </Link>
  )
}

const VALUE_PROPS = [
  { icon: Shield, titleKey: 'home.valueProps.bestPrice', descKey: 'home.valueProps.bestPriceDesc' },
  { icon: Clock, titleKey: 'home.valueProps.freeCancel', descKey: 'home.valueProps.freeCancelDesc' },
  { icon: Headphones, titleKey: 'home.valueProps.support', descKey: 'home.valueProps.supportDesc' },
  { icon: CreditCard, titleKey: 'home.valueProps.securePayment', descKey: 'home.valueProps.securePaymentDesc' },
]

export default function HomePage() {
  const { t } = useTranslation(['common', 'hotels', 'tours'])

  // Viewer's local "today" (server runs UTC), sent so LiteAPI hotels are priced
  // for the user's actual current date regardless of timezone.
  const today = useMemo(() => {
    const d = new Date()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    return `${d.getFullYear()}-${mm}-${dd}`
  }, [])

  // Featured hotels (partner + LiteAPI) + tours (Viator). The external half is
  // cached permanently on the backend; partner hotels are fetched live there.
  // One request feeds both sections; staleTime keeps it from refetching within a session.
  const { data: featured, isLoading: featuredLoading } = useQuery({
    queryKey: ['featured-home', today],
    queryFn: () => featuredApi.home(today),
    select: (res) => res.data || {},
    staleTime: 30 * 60 * 1000,
    gcTime: 60 * 60 * 1000,
  })

  // Backend already attaches today's price to LiteAPI hotels (cached per calendar
  // day) and partner hotels carry their own, so the cards render prices directly.
  const hotelsData = featured?.hotels || []
  const toursData = featured?.tours || []
  const hotelsLoading = featuredLoading
  const toursLoading = featuredLoading

  return (
    <>
      <Helmet>
        <title>TravelBooking — Find Your Perfect Stay</title>
        <meta name="description" content="Book hotels, tours, and activities worldwide at the best prices. Free cancellation, 24/7 support, and secure payments." />
        <meta property="og:title" content="TravelBooking — Find Your Perfect Stay" />
        <meta property="og:description" content="Book hotels, tours, and activities worldwide at the best prices." />
        <meta property="og:type" content="website" />
      </Helmet>

      {/* Hero */}
      <section className="relative bg-gradient-to-br from-primary via-primary-light to-primary-dark py-20 md:py-32">
        <div className="absolute inset-0 bg-black/20 pointer-events-none" />
        <div className="relative z-10 max-w-7xl mx-auto px-4 text-center">
          <h1 className="font-heading text-3xl md:text-5xl font-extrabold text-white mb-4 leading-tight">
            {t('hotels:search.title')}
          </h1>
          <p className="text-white/80 text-lg md:text-xl mb-10 max-w-2xl mx-auto">
            {t('tours:search.title')}
          </p>
          <SearchBar variant="hero" />
        </div>
      </section>

      {/* Featured Destinations */}
      <section className="max-w-7xl mx-auto px-4 py-16">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="font-heading text-2xl font-bold text-gray-900">{t('common:home.featuredTitle')}</h2>
            <p className="text-gray-500 mt-1">{t('common:home.featuredSubtitle')}</p>
          </div>
        </div>
        <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide">
          {FEATURED_DESTINATIONS.map((dest) => (
            <DestinationCard key={dest.name} dest={dest} />
          ))}
        </div>
      </section>

      {/* Popular Hotels */}
      <section className="bg-surface py-16">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="font-heading text-2xl font-bold text-gray-900">{t('common:nav.hotels')}</h2>
              <p className="text-gray-500 mt-1">{t('common:home.popularHotelsSubtitle')}</p>
            </div>
            <Link to="/hotels/search" className="text-primary font-semibold text-sm flex items-center gap-1 hover:underline">
              {t('common:common.viewAll')} <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="space-y-4">
            {hotelsLoading
              ? Array.from({ length: 3 }, (_, i) => <HotelCardSkeleton key={i} />)
              : hotelsData?.map((hotel) => <HotelCard key={hotel.id || hotel.liteapi_hotel_id} hotel={hotel} />)
            }
            {!hotelsLoading && hotelsData?.length === 0 && (
              <p className="text-center text-gray-400 py-12">{t('common:home.noHotels')}</p>
            )}
          </div>
        </div>
      </section>

      {/* Top Tours */}
      <section className="max-w-7xl mx-auto px-4 py-16">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="font-heading text-2xl font-bold text-gray-900">{t('common:nav.tours')}</h2>
            <p className="text-gray-500 mt-1">{t('common:home.topToursSubtitle')}</p>
          </div>
          <Link to="/tours" className="text-primary font-semibold text-sm flex items-center gap-1 hover:underline">
            {t('common:common.viewAll')} <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {toursLoading
            ? Array.from({ length: 4 }, (_, i) => <TourCardSkeleton key={i} />)
            : toursData?.map((tour) => <TourCard key={tour.id || tour.viator_product_code} tour={tour} />)
          }
          {!toursLoading && toursData?.length === 0 && (
            <p className="col-span-full text-center text-gray-400 py-12">{t('common:home.noTours')}</p>
          )}
        </div>
      </section>

      {/* Value Props */}
      <section className="bg-primary/5 py-16">
        <div className="max-w-7xl mx-auto px-4">
          <h2 className="font-heading text-2xl font-bold text-gray-900 text-center mb-12">{t('common:home.whyBookTitle')}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {VALUE_PROPS.map(({ icon: Icon, titleKey, descKey }) => (
              <div key={titleKey} className="text-center">
                <div className="w-14 h-14 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Icon className="w-7 h-7 text-primary" />
                </div>
                <h3 className="font-heading font-bold text-gray-900 mb-2">{t(`common:${titleKey}`)}</h3>
                <p className="text-sm text-gray-500">{t(`common:${descKey}`)}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}
