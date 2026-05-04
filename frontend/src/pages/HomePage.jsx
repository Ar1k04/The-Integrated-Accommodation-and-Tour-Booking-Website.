import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { hotelsApi } from '@/api/hotelsApi'
import { toursApi } from '@/api/toursApi'
import SearchBar from '@/components/common/SearchBar'
import HotelCard from '@/components/hotel/HotelCard'
import TourCard from '@/components/tour/TourCard'
import { HotelCardSkeleton, TourCardSkeleton } from '@/components/common/Skeleton'
import { Shield, Clock, Headphones, CreditCard, ChevronRight } from 'lucide-react'

const FEATURED_DESTINATIONS = [
  { name: 'Ha Noi', country: 'Vietnam', img: 'https://placehold.co/300x200?text=Hanoi' },
  { name: 'Bangkok', country: 'Thailand', img: 'https://placehold.co/300x200?text=Bangkok' },
  { name: 'Tokyo', country: 'Japan', img: 'https://placehold.co/300x200?text=Tokyo' },
  { name: 'Paris', country: 'France', img: 'https://placehold.co/300x200?text=Paris' },
  { name: 'Bali', country: 'Indonesia', img: 'https://placehold.co/300x200?text=Bali' },
  { name: 'Seoul', country: 'South Korea', img: 'https://placehold.co/300x200?text=Seoul' },
]

const VALUE_PROPS = [
  { icon: Shield, title: 'Best Price Guarantee', desc: 'Find a lower price? We match it.' },
  { icon: Clock, title: 'Free Cancellation', desc: 'Flexible bookings on most rooms.' },
  { icon: Headphones, title: '24/7 Support', desc: 'Our team is here around the clock.' },
  { icon: CreditCard, title: 'Secure Payment', desc: 'Your data is always protected.' },
]

export default function HomePage() {
  const { t } = useTranslation(['common', 'hotels', 'tours'])
  const { data: hotelsData, isLoading: hotelsLoading } = useQuery({
    queryKey: ['popular-hotels'],
    queryFn: () => hotelsApi.list({ sort_by: 'avg_rating', sort_order: 'desc', per_page: 4 }),
    select: (res) => res.data?.items || [],
  })

  const { data: toursData, isLoading: toursLoading } = useQuery({
    queryKey: ['top-tours'],
    queryFn: () => toursApi.list({ sort_by: 'avg_rating', sort_order: 'desc', per_page: 4 }),
    select: (res) => res.data?.items || [],
  })

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
            <h2 className="font-heading text-2xl font-bold text-gray-900">Featured Destinations</h2>
            <p className="text-gray-500 mt-1">Explore top travel destinations</p>
          </div>
        </div>
        <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide">
          {FEATURED_DESTINATIONS.map((dest) => (
            <Link
              key={dest.name}
              to={`/hotels/search?city=${encodeURIComponent(dest.name)}`}
              className="shrink-0 w-48 group"
            >
              <div className="relative h-32 rounded-xl overflow-hidden">
                <img src={dest.img} alt={dest.name}
                  className="w-full h-full object-cover group-hover:scale-110 transition-transform duration-500" />
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
                <div className="absolute bottom-3 left-3 text-white">
                  <p className="font-bold text-sm">{dest.name}</p>
                  <p className="text-xs opacity-80">{dest.country}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </section>

      {/* Popular Hotels */}
      <section className="bg-surface py-16">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex items-center justify-between mb-8">
            <div>
              <h2 className="font-heading text-2xl font-bold text-gray-900">{t('common:nav.hotels')}</h2>
              <p className="text-gray-500 mt-1">Top-rated stays loved by travelers</p>
            </div>
            <Link to="/hotels/search" className="text-primary font-semibold text-sm flex items-center gap-1 hover:underline">
              {t('common:common.viewAll')} <ChevronRight className="w-4 h-4" />
            </Link>
          </div>
          <div className="space-y-4">
            {hotelsLoading
              ? Array.from({ length: 3 }, (_, i) => <HotelCardSkeleton key={i} />)
              : hotelsData?.map((hotel) => <HotelCard key={hotel.id} hotel={hotel} />)
            }
            {!hotelsLoading && hotelsData?.length === 0 && (
              <p className="text-center text-gray-400 py-12">No hotels available yet. Check back soon!</p>
            )}
          </div>
        </div>
      </section>

      {/* Top Tours */}
      <section className="max-w-7xl mx-auto px-4 py-16">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h2 className="font-heading text-2xl font-bold text-gray-900">{t('common:nav.tours')}</h2>
            <p className="text-gray-500 mt-1">Unforgettable experiences</p>
          </div>
          <Link to="/tours" className="text-primary font-semibold text-sm flex items-center gap-1 hover:underline">
            {t('common:common.viewAll')} <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {toursLoading
            ? Array.from({ length: 4 }, (_, i) => <TourCardSkeleton key={i} />)
            : toursData?.map((tour) => <TourCard key={tour.id} tour={tour} />)
          }
          {!toursLoading && toursData?.length === 0 && (
            <p className="col-span-full text-center text-gray-400 py-12">No tours available yet.</p>
          )}
        </div>
      </section>

      {/* Value Props */}
      <section className="bg-primary/5 py-16">
        <div className="max-w-7xl mx-auto px-4">
          <h2 className="font-heading text-2xl font-bold text-gray-900 text-center mb-12">Why Book With Us</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {VALUE_PROPS.map(({ icon: Icon, title, desc }) => (
              <div key={title} className="text-center">
                <div className="w-14 h-14 bg-primary/10 rounded-2xl flex items-center justify-center mx-auto mb-4">
                  <Icon className="w-7 h-7 text-primary" />
                </div>
                <h3 className="font-heading font-bold text-gray-900 mb-2">{title}</h3>
                <p className="text-sm text-gray-500">{desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}
