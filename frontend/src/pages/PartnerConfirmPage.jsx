import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Helmet } from 'react-helmet-async'
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react'
import { authApi } from '@/api/authApi'

export default function PartnerConfirmPage() {
  const { t } = useTranslation('auth')
  const [params] = useSearchParams()
  const token = params.get('token') || ''
  // 'loading' | 'success' | 'error'
  const [state, setState] = useState('loading')
  const [error, setError] = useState('')
  const ran = useRef(false)

  useEffect(() => {
    // StrictMode double-invokes effects in dev — guard so we only POST once.
    if (ran.current) return
    ran.current = true

    if (!token) {
      setState('error')
      setError(t('partnerConfirm.missingToken'))
      return
    }
    authApi
      .confirmPartner(token)
      .then(() => setState('success'))
      .catch((err) => {
        const detail = err.response?.data?.detail
        setError(typeof detail === 'string' ? detail : t('partnerConfirm.error'))
        setState('error')
      })
  }, [token, t])

  return (
    <>
      <Helmet><title>{t('partnerConfirm.title')} — TravelBooking</title></Helmet>
      <div className="min-h-[80vh] flex items-center justify-center px-4 py-12 bg-surface">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-lg p-8 text-center">
            <h1 className="font-heading text-2xl font-bold mb-6">{t('partnerConfirm.title')}</h1>

            {state === 'loading' && (
              <div className="space-y-4">
                <Loader2 className="w-14 h-14 text-primary mx-auto animate-spin" aria-hidden="true" />
                <p className="text-sm text-gray-600">{t('partnerConfirm.verifying')}</p>
              </div>
            )}

            {state === 'success' && (
              <div className="space-y-4">
                <CheckCircle2 className="w-14 h-14 text-green-500 mx-auto" aria-hidden="true" />
                <p className="text-sm text-gray-700">{t('partnerConfirm.success')}</p>
                <Link to="/login" className="inline-block text-primary font-medium hover:underline">
                  {t('partnerConfirm.goToLogin')}
                </Link>
              </div>
            )}

            {state === 'error' && (
              <div className="space-y-4">
                <XCircle className="w-14 h-14 text-error mx-auto" aria-hidden="true" />
                <p role="alert" className="text-sm text-error">{error}</p>
                <Link to="/login" className="inline-block text-primary font-medium hover:underline">
                  {t('partnerConfirm.goToLogin')}
                </Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
