import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { Eye, EyeOff, Lock, CheckCircle2 } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { authApi } from '@/api/authApi'
import { isStrongPassword } from '@/utils/validators'

export default function ResetPasswordPage() {
  const { t } = useTranslation('auth')
  const { isAuthenticated, user, refreshUser } = useAuth()
  // A logged-in Google account (no local password) may follow the reset link to
  // set a first password; normal logged-in users are redirected away.
  const needsFirstPassword = user?.has_password === false
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const token = params.get('token') || ''

  const [form, setForm] = useState({ password: '', confirmPassword: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})
  const [done, setDone] = useState(false)

  if (isAuthenticated && !needsFirstPassword) return <Navigate to="/" replace />

  const validate = () => {
    const errs = {}
    if (!token) errs.server = 'Missing or invalid reset token'
    if (!isStrongPassword(form.password)) errs.password = t('register.validation.passwordWeak')
    if (form.password !== form.confirmPassword) errs.confirmPassword = t('register.validation.passwordMismatch')
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    try {
      await authApi.resetPassword({ token, new_password: form.password })
      toast.success(t('resetPassword.success'))
      if (isAuthenticated) {
        // A logged-in Google account just set a first password: refresh the
        // cached user so has_password flips to true (the profile stops showing
        // "Set a password") and return them to the security tab.
        try { await refreshUser() } catch { /* non-fatal */ }
        navigate('/profile?tab=security', { replace: true })
        return
      }
      setDone(true)
      setTimeout(() => navigate('/login', { replace: true }), 2000)
    } catch (err) {
      const detail = err.response?.data?.detail
      setErrors({ server: typeof detail === 'string' ? detail : 'Failed to reset password' })
    } finally {
      setLoading(false)
    }
  }

  const inputClass = (field) =>
    `w-full pl-10 pr-12 py-3 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary ${
      errors[field] ? 'border-error' : 'border-gray-200'
    }`

  return (
    <>
      <Helmet><title>{t('resetPassword.title')} — TravelBooking</title></Helmet>
      <div className="min-h-[80vh] flex items-center justify-center px-4 py-12 bg-surface">
        <div className="w-full max-w-md">
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <h1 className="font-heading text-2xl font-bold text-center mb-1">{t('resetPassword.title')}</h1>

            {done ? (
              <div className="text-center space-y-4 mt-6">
                <CheckCircle2 className="w-14 h-14 text-green-500 mx-auto" aria-hidden="true" />
                <p className="text-sm text-gray-700">{t('resetPassword.success')}</p>
                <Link to="/login" className="text-primary font-medium hover:underline">
                  {t('forgotPassword.backToLogin')}
                </Link>
              </div>
            ) : (
              <>
                {errors.server && (
                  <div role="alert" className="bg-red-50 text-error text-sm px-4 py-3 rounded-lg mt-6 mb-2">
                    {errors.server}
                    <Link to="/forgot-password" className="block mt-2 font-semibold text-primary hover:underline">
                      {t('resetPassword.requestNewLink', 'Request a new reset link')}
                    </Link>
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-5 mt-6" noValidate>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('resetPassword.newPassword')}</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        required
                        value={form.password}
                        onChange={(e) => setForm({ ...form, password: e.target.value })}
                        className={inputClass('password')}
                        placeholder="Min. 8 characters"
                      />
                      <button type="button" onClick={() => setShowPassword(!showPassword)}
                        aria-label="Toggle password visibility"
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600">
                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                    {errors.password && <p className="text-error text-xs mt-1">{errors.password}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">{t('resetPassword.confirmPassword')}</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="password"
                        required
                        value={form.confirmPassword}
                        onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })}
                        className={inputClass('confirmPassword')}
                        placeholder="Re-enter your password"
                      />
                    </div>
                    {errors.confirmPassword && <p className="text-error text-xs mt-1">{errors.confirmPassword}</p>}
                  </div>

                  <button
                    type="submit"
                    disabled={loading || !token}
                    className="w-full bg-accent hover:bg-accent-dark disabled:bg-gray-300 text-white font-semibold py-3 rounded-lg transition-colors"
                  >
                    {loading ? '...' : t('resetPassword.submit')}
                  </button>
                </form>

                <p className="text-center text-sm text-gray-500 mt-6">
                  <Link to="/login" className="text-primary font-semibold hover:underline">
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
