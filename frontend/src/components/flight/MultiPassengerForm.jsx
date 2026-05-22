import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react'
import { format } from 'date-fns'
import { emptyPassenger, isPassengerComplete } from './passengerHelpers'

const TITLE_OPTIONS = ['mr', 'mrs', 'ms', 'dr']
const GENDER_OPTIONS = [
  { value: 'M', label: 'Male' },
  { value: 'F', label: 'Female' },
]

// IATA / Duffel only accept ASCII letters, space, hyphen and apostrophe in
// passenger names. The backend transliterates via `unidecode` so users CAN
// type their real name in any script — we only need to warn them that the
// printed ticket will be ASCII (same as their passport MRZ).
const hasNonAscii = (s) => Boolean(s) && /[^\x00-\x7F]/.test(String(s))

/**
 * MultiPassengerForm — renders N collapsible passenger cards.
 *
 * Props:
 *   passengers: PassengerInfo[]   — controlled array (length === count)
 *   onChange(passengers)
 *   count: number
 *   labels?: [{ kind: 'adult'|'child'|'infant', text: string, age: number|null }, ...]
 *     When supplied each card shows the passenger type ("Adult", "Child age 8")
 *     under the title — matches the offer's passenger_breakdown ordering.
 */
export default function MultiPassengerForm({ passengers, onChange, count, labels }) {
  const { t } = useTranslation(['flights', 'common'])
  const [openIdx, setOpenIdx] = useState(0)

  const setField = (i, field, value) => {
    const next = [...passengers]
    next[i] = { ...next[i], [field]: value }
    onChange(next)
  }

  const today = format(new Date(), 'yyyy-MM-dd')

  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => {
        const pax = passengers[i] || emptyPassenger()
        const open = openIdx === i
        const done = isPassengerComplete(pax)
        const meta = labels?.[i]
        const isMinor = meta && (meta.kind === 'child' || meta.kind === 'infant')
        const baseLabel = i === 0
          ? t('flights:passengers.leadPassenger')
          : t('flights:passengers.passenger_n', { n: i + 1 })
        const label = isMinor ? `${baseLabel} · ${meta.text}` : baseLabel

        return (
          <div key={i} className="bg-white border rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setOpenIdx(open ? -1 : i)}
              className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className={`w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm ${
                  done ? 'bg-success/10 text-success' : 'bg-primary/10 text-primary'
                }`}>
                  {done ? <CheckCircle2 className="w-4 h-4" /> : (i + 1)}
                </span>
                <div className="text-left">
                  <p className="text-sm font-semibold text-gray-900">{label}</p>
                  {done && (
                    <p className="text-xs text-gray-500 truncate">
                      {pax.first_name} {pax.last_name}
                    </p>
                  )}
                </div>
              </div>
              {open
                ? <ChevronUp className="w-4 h-4 text-gray-400" />
                : <ChevronDown className="w-4 h-4 text-gray-400" />}
            </button>

            {open && (
              <div className="px-5 pb-5 pt-1 grid grid-cols-2 gap-4 border-t">
                <Field label={t('flights:detail.passenger.title')}>
                  <select
                    value={pax.title}
                    onChange={(e) => setField(i, 'title', e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    {TITLE_OPTIONS.map((t) => <option key={t} value={t}>{t.toUpperCase()}</option>)}
                  </select>
                </Field>
                <Field label={t('flights:detail.passenger.gender')}>
                  <select
                    value={pax.gender}
                    onChange={(e) => setField(i, 'gender', e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    {GENDER_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
                  </select>
                </Field>
                <Field label={t('flights:detail.passenger.firstName')}>
                  <input
                    value={pax.first_name}
                    onChange={(e) => setField(i, 'first_name', e.target.value)}
                    placeholder={t('flights:detail.passenger.firstNamePlaceholder')}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                  {hasNonAscii(pax.first_name) && (
                    <p className="text-xs text-amber-600 mt-1">
                      Vé bay in tên bằng chữ Latin không dấu theo chuẩn IATA (giống như trên hộ chiếu của bạn).
                    </p>
                  )}
                </Field>
                <Field label={t('flights:detail.passenger.lastName')}>
                  <input
                    value={pax.last_name}
                    onChange={(e) => setField(i, 'last_name', e.target.value)}
                    placeholder={t('flights:detail.passenger.lastNamePlaceholder')}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                  {hasNonAscii(pax.last_name) && (
                    <p className="text-xs text-amber-600 mt-1">
                      Vé bay in họ bằng chữ Latin không dấu theo chuẩn IATA.
                    </p>
                  )}
                </Field>
                <Field label={t('flights:detail.passenger.email')}>
                  <input
                    type="email"
                    value={pax.email}
                    onChange={(e) => setField(i, 'email', e.target.value)}
                    placeholder={t('flights:detail.passenger.emailPlaceholder')}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </Field>
                <Field label={t('flights:detail.passenger.dateOfBirth')}>
                  <input
                    type="date"
                    value={pax.born_on}
                    max={today}
                    onChange={(e) => setField(i, 'born_on', e.target.value)}
                    className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                  />
                </Field>
                <div className="col-span-2">
                  <Field label={t('flights:detail.passenger.phone', { defaultValue: 'Phone number' })}>
                    <input
                      type="tel"
                      required
                      value={pax.phone_number || ''}
                      onChange={(e) => setField(i, 'phone_number', e.target.value)}
                      placeholder={t('flights:detail.passenger.phonePlaceholder', { defaultValue: '+84...' })}
                      className="w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Hãng bay yêu cầu số điện thoại liên lạc cho mọi vé (bao gồm mã quốc gia, ví dụ +84...).
                    </p>
                  </Field>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1">{label} *</label>
      {children}
    </div>
  )
}

