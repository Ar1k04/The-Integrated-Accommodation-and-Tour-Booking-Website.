import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { ArrowLeft, Mail, CheckCircle2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { authApi } from '@/api/authApi'
import { isValidEmail } from '@/utils/validators'

export default function ForgotPasswordPage() {
  const { t } = useTranslation('auth')
  const { isAuthenticated, user } = useAuth()
  // A logged-in Google account has no local password; let it through to set a
  // first one via the email reset flow. Normal logged-in users still bounce home.
  const needsFirstPassword = user?.has_password === false

  const [email, setEmail] = useState(user?.email || '')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  if (isAuthenticated && !needsFirstPassword) return <Navigate to="/" replace />

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!isValidEmail(email)) {
      setError(t('register.validation.emailRequired'))
      return
    }
    setLoading(true)
    try {
      await authApi.forgotPassword(email)
      setSent(true)
      toast.success(t('forgotPassword.success'))
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : t('forgotPassword.success'))
      setSent(true)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Helmet><title>{t('forgotPassword.title')} — TravelBooking</title></Helmet>
      <div className="min-h-[80vh] flex items-center justify-center px-4 py-12 bg-surface">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <h1 className="font-heading text-2xl font-bold text-center mb-1">{t('forgotPassword.title')}</h1>
            <p className="text-gray-500 text-center text-sm mb-8">{t('forgotPassword.subtitle')}</p>

            {sent ? (
              <div className="text-center space-y-4">
                <CheckCircle2 className="w-14 h-14 text-green-500 mx-auto" aria-hidden="true" />
                <p className="text-sm text-gray-700">{t('forgotPassword.success')}</p>
                <Link to="/login" className="inline-flex items-center gap-2 text-primary font-medium hover:underline">
                  <ArrowLeft className="w-4 h-4" />
                  {t('forgotPassword.backToLogin')}
                </Link>
              </div>
            ) : (
              <>
                {error && (
                  <div role="alert" className="bg-red-50 text-error text-sm px-4 py-3 rounded-lg mb-6">{error}</div>
                )}
                <form onSubmit={handleSubmit} className="space-y-5" noValidate>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('forgotPassword.email')}</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="email"
                        required
                        aria-required="true"
                        aria-invalid={!!error}
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full pl-10 pr-4 py-3 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary"
                        placeholder="your@email.com"
                      />
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-accent hover:bg-accent-dark disabled:bg-gray-300 text-white font-semibold py-3 rounded-lg transition-colors"
                  >
                    {loading ? '...' : t('forgotPassword.send')}
                  </button>
                </form>

                <p className="text-center text-sm text-gray-500 mt-6">
                  <Link to="/login" className="inline-flex items-center gap-1 text-primary font-semibold hover:underline">
                    <ArrowLeft className="w-4 h-4" />
                    {t('forgotPassword.backToLogin')}
                  </Link>
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
