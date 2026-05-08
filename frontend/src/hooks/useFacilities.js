import { useQuery } from '@tanstack/react-query'
import { facilitiesApi } from '@/api/facilitiesApi'
import { LITEAPI_ID_TO_SLUG, AMENITIES } from '@/utils/constants'

export function useFacilities() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['facilities'],
    queryFn: () => facilitiesApi.list().then((r) => r.data),
    staleTime: Infinity,
    gcTime: 24 * 60 * 60 * 1000,
  })

  // Keep only the 13 mapped facilities, in canonical AMENITIES order
  const facilities = (data || [])
    .filter((f) => LITEAPI_ID_TO_SLUG[f.id] !== undefined)
    .sort((a, b) => {
      const ia = AMENITIES.indexOf(LITEAPI_ID_TO_SLUG[a.id])
      const ib = AMENITIES.indexOf(LITEAPI_ID_TO_SLUG[b.id])
      return ia - ib
    })

  return { facilities, isLoading, isError }
}
