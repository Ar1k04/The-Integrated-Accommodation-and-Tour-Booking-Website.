const NON_ALNUM_RE = /[^a-z0-9]+/g
const EDGE_UNDERSCORE_RE = /^_+|_+$/g

function normalizeLanguage(language) {
  return String(language || 'en').replace('-', '_')
}

function translateWithDefault(t, key, defaultValue) {
  if (typeof t !== 'function') return defaultValue
  const translated = t(key, { defaultValue })
  return translated && translated !== key ? translated : defaultValue
}

function getLocaleName(tag, language) {
  const namesByLocale = tag?.names_by_locale || tag?.allNamesByLocale || {}
  const normalized = normalizeLanguage(language)
  const base = normalized.split('_')[0]

  return namesByLocale[normalized]
    || namesByLocale[base]
    || namesByLocale[`${base}_${base.toUpperCase()}`]
    || (base === 'en' ? namesByLocale.en_GB || namesByLocale.en_AU : '')
    || ''
}

export function makeViatorTagNameKey(name) {
  return String(name || '')
    .toLowerCase()
    .replace(/&/g, ' and ')
    .replace(NON_ALNUM_RE, '_')
    .replace(EDGE_UNDERSCORE_RE, '')
}

export function getViatorTagLabel(tag, t, language = 'en') {
  const id = tag?.tag_id ?? tag?.id
  const rawName = tag?.name || tag?.label || ''
  const localizedName = getLocaleName(tag, language)
  const fallback = localizedName || rawName || (id ? `#${id}` : '')

  const nameKey = makeViatorTagNameKey(rawName || localizedName)
  if (nameKey) {
    const byName = translateWithDefault(t, `tours:page.filters.viatorTagNames.${nameKey}`, fallback)
    if (byName !== fallback) return byName
  }

  if (id) {
    return translateWithDefault(t, `tours:page.filters.viatorTags.${id}`, fallback)
  }

  return fallback
}
