import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Wifi, Car, Dumbbell, UtensilsCrossed, Waves, Sparkles,
  ConciergeBell, Wind, WashingMachine, PlaneTakeoff, PawPrint,
  Briefcase, Wine, CheckCircle,
} from 'lucide-react'
import { LITEAPI_ID_TO_SLUG } from '@/utils/constants'

const SLUG_ICONS = {
  wifi: Wifi,
  parking: Car,
  gym: Dumbbell,
  restaurant: UtensilsCrossed,
  pool: Waves,
  spa: Sparkles,
  room_service: ConciergeBell,
  air_conditioning: Wind,
  laundry: WashingMachine,
  airport_shuttle: PlaneTakeoff,
  pet_friendly: PawPrint,
  business_center: Briefcase,
  bar: Wine,
}

const INITIAL_SHOW = 12

export default function FacilitiesSection({ amenities }) {
  const { t } = useTranslation('hotels')
  const [showAll, setShowAll] = useState(false)

  if (!amenities?.length) return null

  // Normalise to [{slug?, label, Icon}] — handles both string slugs and {id, name} objects
  const items = amenities.map((a) => {
    if (typeof a === 'string') {
      return {
        slug: a,
        label: t(`amenities.${a}`, a.replace(/_/g, ' ')),
        Icon: SLUG_ICONS[a] || CheckCircle,
      }
    }
    // LiteAPI object: {id: number, name: string}
    const slug = LITEAPI_ID_TO_SLUG[a.id]
    return {
      slug,
      label: slug ? t(`amenities.${slug}`, a.name) : a.name,
      Icon: (slug && SLUG_ICONS[slug]) || CheckCircle,
    }
  })

  // Known-slug items first (mapped → have icons), then remaining alphabetically
  const sorted = [
    ...items.filter((i) => i.slug),
    ...items.filter((i) => !i.slug).sort((a, b) => a.label.localeCompare(b.label)),
  ]

  const visible = showAll ? sorted : sorted.slice(0, INITIAL_SHOW)
  const hasMore = sorted.length > INITIAL_SHOW

  return (
    <div>
      <h2 className="font-heading font-bold text-lg mb-4">
        {t('detail.amenities', 'Facilities')}
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        {visible.map(({ label, Icon }, i) => (
          <div key={i} className="flex items-center gap-2 text-sm text-gray-700">
            <Icon className="w-4 h-4 text-primary shrink-0" />
            <span className="capitalize">{label}</span>
          </div>
        ))}
      </div>
      {hasMore && (
        <button
          onClick={() => setShowAll((v) => !v)}
          className="mt-3 text-sm font-medium text-primary hover:underline"
        >
          {showAll
            ? t('amenities.showLess', 'Show less')
            : t('amenities.showAll', { count: sorted.length, defaultValue: `Show all ${sorted.length} facilities` })}
        </button>
      )}
    </div>
  )
}
