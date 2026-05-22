// The selector is shared across hotels/tours/flights — live source is
// `components/common/OccupancySelector`. This re-export keeps existing
// `@/components/hotel/OccupancySelector` imports working.
export { default } from '@/components/common/OccupancySelector'
