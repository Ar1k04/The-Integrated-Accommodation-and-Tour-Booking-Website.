import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronDown, ChevronUp, Info } from 'lucide-react'

function describeCondition(cond, t) {
  if (!cond) return t('flights:fareRules.changesNotAllowed')
  if (cond.allowed === false) return t('flights:fareRules.changesNotAllowed')
  if (cond.penalty_amount && Number(cond.penalty_amount) > 0) {
    return `${cond.penalty_amount} ${cond.penalty_currency || ''} ${t('flights:fareRules.feeApplies')}`
  }
  return t('flights:fareRules.changesAllowed')
}

export default function FareRulesAccordion({ conditions }) {
  const { t } = useTranslation(['flights'])
  const [open, setOpen] = useState(false)

  if (!conditions || Object.keys(conditions).length === 0) return null

  const refund = conditions.refund_before_departure
  const change = conditions.change_before_departure

  return (
    <div className="bg-white border rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-5 py-3 hover:bg-gray-50 transition-colors"
      >
        <span className="flex items-center gap-2 font-semibold text-sm text-gray-800">
          <Info className="w-4 h-4 text-gray-400" /> {t('flights:fareRules.title')}
        </span>
        {open ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
      </button>
      {open && (
        <div className="px-5 pb-4 space-y-2 text-sm border-t pt-3">
          <Rule
            label={t('flights:fareRules.cancellation')}
            badge={refund?.allowed
              ? t('flights:fareRules.refundable')
              : t('flights:fareRules.nonRefundable')}
            badgeColor={refund?.allowed ? 'green' : 'red'}
            detail={refund?.allowed
              ? describeCondition(refund, t)
              : t('flights:fareRules.nonRefundable')}
          />
          <Rule
            label={t('flights:fareRules.changes')}
            badge={change?.allowed
              ? t('flights:fareRules.changesAllowed')
              : t('flights:fareRules.changesNotAllowed')}
            badgeColor={change?.allowed ? 'green' : 'red'}
            detail={describeCondition(change, t)}
          />
        </div>
      )}
    </div>
  )
}

function Rule({ label, badge, badgeColor, detail }) {
  const colorClass = badgeColor === 'green'
    ? 'bg-green-50 text-green-700'
    : 'bg-red-50 text-red-700'
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="flex-1">
        <p className="text-xs font-medium text-gray-500 uppercase">{label}</p>
        <p className="text-xs text-gray-600 mt-1">{detail}</p>
      </div>
      <span className={`text-xs font-semibold px-2 py-1 rounded-full whitespace-nowrap ${colorClass}`}>
        {badge}
      </span>
    </div>
  )
}
