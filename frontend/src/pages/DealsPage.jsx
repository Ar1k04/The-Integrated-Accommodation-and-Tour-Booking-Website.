import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { Ticket, Copy, Check, AlertCircle } from 'lucide-react'
import { useState } from 'react'
import { vouchersApi } from '@/api/vouchersApi'
import { formatCurrency, formatDate } from '@/utils/formatters'
import Skeleton from '@/components/common/Skeleton'

function VoucherCard({ voucher }) {
  const { t } = useTranslation('common')
  const [copied, setCopied] = useState(false)

  const isPercent = voucher.discount_type === 'percentage'
  const discountLabel = isPercent
    ? t('deals.percentOff', { value: Number(voucher.discount_value) })
    : t('deals.amountOff', { amount: formatCurrency(voucher.discount_value) })

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(voucher.code)
      setCopied(true)
      toast.success(t('deals.copied'))
      setTimeout(() => setCopied(false), 2000)
    } catch {
      toast.error(t('deals.loadError'))
    }
  }

  return (
    <div className="flex overflow-hidden rounded-xl border border-gray-200 bg-white shadow-sm transition-shadow hover:shadow-md">
      {/* Left stub */}
      <div className="flex w-28 shrink-0 flex-col items-center justify-center bg-gradient-to-br from-primary to-primary-dark p-4 text-center text-white">
        <Ticket className="mb-1 h-6 w-6" />
        <span className="text-lg font-bold leading-tight">{discountLabel}</span>
      </div>

      {/* Body */}
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div>
          <h3 className="font-semibold text-gray-900">{voucher.name}</h3>
          <p className="text-xs text-gray-500">
            {t(`deals.appliesTo_${voucher.applicable_to}`, { defaultValue: voucher.applicable_to })}
          </p>
        </div>

        {voucher.description && (
          <p className="line-clamp-2 text-sm text-gray-600">{voucher.description}</p>
        )}

        <ul className="mt-auto space-y-0.5 text-xs text-gray-500">
          {voucher.min_order_value > 0 && (
            <li>{t('deals.minOrder', { amount: formatCurrency(voucher.min_order_value) })}</li>
          )}
          {isPercent && voucher.maximum_discount_amount != null && (
            <li>{t('deals.maxDiscount', { amount: formatCurrency(voucher.maximum_discount_amount) })}</li>
          )}
          <li>
            {voucher.valid_to
              ? t('deals.validUntil', { date: formatDate(voucher.valid_to) })
              : t('deals.noExpiry')}
          </li>
        </ul>

        <div className="mt-2 flex items-center gap-2">
          <code className="flex-1 rounded-md border border-dashed border-gray-300 bg-gray-50 px-3 py-1.5 text-center text-sm font-semibold tracking-wider text-gray-800">
            {voucher.code}
          </code>
          <button
            type="button"
            onClick={copyCode}
            className="inline-flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-primary-dark"
          >
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? t('deals.copied') : t('deals.copy')}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function DealsPage() {
  const { t } = useTranslation('common')

  const { data, isLoading, isError } = useQuery({
    queryKey: ['vouchers', 'public'],
    queryFn: () => vouchersApi.public().then((res) => res.data),
  })

  const vouchers = data ?? []

  return (
    <div className="min-h-[60vh] bg-gray-50">
      <Helmet>
        <title>{t('deals.title')} · TravelBooking</title>
      </Helmet>

      <div className="mx-auto max-w-7xl px-4 py-10">
        <header className="mb-8">
          <h1 className="flex items-center gap-2 font-heading text-3xl font-bold text-gray-900">
            <Ticket className="h-7 w-7 text-primary" />
            {t('deals.title')}
          </h1>
          <p className="mt-1 text-gray-600">{t('deals.subtitle')}</p>
        </header>

        {isLoading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-44 rounded-xl" />
            ))}
          </div>
        )}

        {isError && (
          <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
            <AlertCircle className="h-5 w-5" />
            {t('deals.loadError')}
          </div>
        )}

        {!isLoading && !isError && vouchers.length === 0 && (
          <div className="rounded-xl border border-dashed border-gray-300 bg-white py-16 text-center text-gray-500">
            <Ticket className="mx-auto mb-3 h-10 w-10 text-gray-300" />
            {t('deals.empty')}
          </div>
        )}

        {!isLoading && !isError && vouchers.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {vouchers.map((v) => (
              <VoucherCard key={v.code} voucher={v} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
