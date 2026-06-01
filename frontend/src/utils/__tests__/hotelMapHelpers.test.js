import { describe, it, expect, vi } from 'vitest'

// Mock leaflet: chỉ cần divIcon trả về { options } để kiểm tra HTML do ta sinh,
// và Icon.Default để các side-effect ở cuối module không ném lỗi trong jsdom.
vi.mock('leaflet', () => ({
  default: {
    divIcon: (opts) => ({ options: opts }),
    Icon: { Default: { prototype: {}, mergeOptions: () => {} } },
  },
}))

import { validCoords, buildHotelHref, buildPricePinIcon } from '@/utils/hotelMapHelpers'

describe('validCoords', () => {
  it('rejects null / undefined hotel', () => {
    expect(validCoords(null)).toBe(false)
    expect(validCoords(undefined)).toBe(false)
  })

  it('rejects the (0,0) null-island placeholder', () => {
    expect(validCoords({ latitude: 0, longitude: 0 })).toBe(false)
  })

  it('rejects non-numeric coordinates', () => {
    expect(validCoords({ latitude: 'x', longitude: 1 })).toBe(false)
    expect(validCoords({})).toBe(false)
  })

  it('accepts real coordinates', () => {
    expect(validCoords({ latitude: 10.78, longitude: 106.7 })).toBe(true)
  })

  it('accepts a zero on one axis if the other is non-zero', () => {
    expect(validCoords({ latitude: 0, longitude: 106.7 })).toBe(true)
  })
})

describe('buildHotelHref', () => {
  it('builds a local hotel path', () => {
    expect(buildHotelHref({ id: 'h1', source: 'partner' })).toBe('/hotels/h1')
  })

  it('builds a liteapi hotel path', () => {
    expect(buildHotelHref({ liteapi_hotel_id: 'lp9', source: 'liteapi' })).toBe(
      '/hotels/liteapi/lp9',
    )
  })

  it('appends formatted dates and occupancy as query params', () => {
    const href = buildHotelHref(
      { id: 'h1' },
      {
        checkIn: new Date(2026, 5, 1),
        checkOut: new Date(2026, 5, 4),
        guests: { adults: 2, child_ages: [5, 7], rooms: 2 },
      },
    )
    const url = new URL('http://x' + href)
    expect(url.pathname).toBe('/hotels/h1')
    expect(url.searchParams.get('check_in')).toBe('2026-06-01')
    expect(url.searchParams.get('check_out')).toBe('2026-06-04')
    expect(url.searchParams.get('adults')).toBe('2')
    expect(url.searchParams.get('child_ages')).toBe('5,7')
    expect(url.searchParams.get('guests')).toBe('4') // 2 adults + 2 children
    expect(url.searchParams.get('rooms')).toBe('2')
  })

  it('omits the rooms param when only one room', () => {
    const href = buildHotelHref({ id: 'h1' }, { guests: { adults: 1, rooms: 1 } })
    const url = new URL('http://x' + href)
    expect(url.searchParams.get('rooms')).toBeNull()
    expect(url.searchParams.get('adults')).toBe('1')
  })
})

describe('buildPricePinIcon', () => {
  it('embeds the formatted price in the pin html', () => {
    const icon = buildPricePinIcon('$120', false)
    expect(icon.options.html).toContain('$120')
    expect(icon.options.html).not.toContain('★')
  })

  it('prefixes a star for partner hotels', () => {
    const icon = buildPricePinIcon('$80', true)
    expect(icon.options.html).toContain('★')
    expect(icon.options.html).toContain('$80')
  })

  it('falls back to an em dash when price is empty', () => {
    expect(buildPricePinIcon('', false).options.html).toContain('—')
  })
})
