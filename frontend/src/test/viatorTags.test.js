import { describe, expect, it } from 'vitest'
import {
  getViatorTagLabel,
  makeViatorTagNameKey,
} from '@/utils/viatorTags'
import viTours from '@/i18n/locales/vi/tours.json'

const t = (key, options = {}) => {
  const translations = {
    'tours:page.filters.viatorTagNames.shore_excursions': 'Tour tham quan khi tàu cập cảng',
    'tours:page.filters.viatorTagNames.outdoor_activities': 'Hoạt động ngoài trời',
    'tours:page.filters.viatorTags.21909': 'Tour đi bộ',
    'tours:page.filters.viatorTags.21545': 'Lớp học thể thao mô tô',
  }
  return translations[key] || options.defaultValue || key
}
const tEn = (_key, options = {}) => options.defaultValue

describe('viator tag labels', () => {
  it('normalizes Viator tag names into stable i18n keys', () => {
    expect(makeViatorTagNameKey('Food, Wine & Nightlife')).toBe('food_wine_and_nightlife')
  })

  it('uses explicit i18n labels by tag id first for Vietnamese', () => {
    const label = getViatorTagLabel({ tag_id: 21909, name: 'Walking Tours' }, t, 'vi')
    expect(label).toBe('Tour đi bộ')
  })

  it('uses name i18n before id i18n when a live catalog id was remapped', () => {
    const label = getViatorTagLabel({
      tag_id: 21909,
      name: 'Outdoor Activities',
      names_by_locale: { en: 'Outdoor Activities' },
    }, t, 'vi')
    expect(label).toBe('Hoạt động ngoài trời')
  })

  it('uses generated i18n labels for live Viator tags', () => {
    const label = getViatorTagLabel({ tag_id: 21545, name: 'Motor Sports Classes' }, t, 'vi')
    expect(label).toBe('Lớp học thể thao mô tô')
  })

  it('keeps English labels for English locale', () => {
    const label = getViatorTagLabel({ tag_id: 21768, name: 'Shore Excursions' }, tEn, 'en')
    expect(label).toBe('Shore Excursions')
  })

  it('ships i18n entries for the full live Viator tag catalog snapshot', () => {
    const viatorTags = viTours.page.filters.viatorTags
    expect(Object.keys(viatorTags).length).toBeGreaterThanOrEqual(1263)
    expect(viatorTags['9188']).toBe('Trung tâm thể hình')
    expect(viatorTags['9180']).toBe('Giặt khô')
    expect(viatorTags['12046']).toBe('Tour đi bộ')
    expect(viatorTags['21909']).toBe('Hoạt động ngoài trời')
    expect(viatorTags['21545']).toBe('Lớp học thể thao mô tô')
  })
})
