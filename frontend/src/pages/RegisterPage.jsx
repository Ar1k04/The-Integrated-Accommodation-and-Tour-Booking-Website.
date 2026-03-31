import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { Helmet } from 'react-helmet-async'
import { toast } from 'sonner'
import { Eye, EyeOff, Mail, Lock, User, ShieldCheck, ChevronDown } from 'lucide-react'
import { isValidEmail, isStrongPassword } from '@/utils/validators'

export default function RegisterPage() {
  const { register, isAuthenticated, user } = useAuth()
  const navigate = useNavigate()

  const [form, setForm] = useState({ full_name: '', email: '', password: '', confirmPassword: '' })
  const [adminForm, setAdminForm] = useState({ full_name: '', email: '', password: '', confirmPassword: '' })
  const [showPassword, setShowPassword] = useState(false)
  const [showAdminPassword, setShowAdminPassword] = useState(false)
  const [showAdminRegister, setShowAdminRegister] = useState(false)
  const [agreed, setAgreed] = useState(false)
  const [loading, setLoading] = useState(false)
  const [errors, setErrors] = useState({})
  const [adminError, setAdminError] = useState('')
  const [adminErrors, setAdminErrors] = useState({})

  if (isAuthenticated) {
    return <Navigate to={user?.role === 'admin' ? '/admin' : '/'} replace />
  }

  const validate = () => {
    const errs = {}
    if (!form.full_name.trim()) errs.full_name = 'Full name is required'
    if (!isValidEmail(form.email)) errs.email = 'Valid email is required'
    if (!isStrongPassword(form.password)) errs.password = 'Password must be at least 8 characters'
    if (form.password !== form.confirmPassword) errs.confirmPassword = 'Passwords do not match'
    if (!agreed) errs.agreed = 'You must agree to the terms'
    setErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!validate()) return
    setLoading(true)
    try {
      await register({ full_name: form.full_name, email: form.email, password: form.password })
      toast.success('Account created successfully!')
      navigate('/')
    } catch (err) {
      const detail = err.response?.data?.detail
      setErrors({ server: typeof detail === 'string' ? detail : 'Registration failed' })
    } finally {
      setLoading(false)
    }
  }

  const validateAdminForm = () => {
    const errs = {}
    if (!adminForm.full_name.trim()) errs.full_name = 'Full name is required'
    if (!isValidEmail(adminForm.email)) errs.email = 'Valid email is required'
    if (!isStrongPassword(adminForm.password)) errs.password = 'Password must be at least 8 characters'
    if (adminForm.password !== adminForm.confirmPassword) errs.confirmPassword = 'Passwords do not match'
    setAdminErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleAdminRegister = async (e) => {
    e.preventDefault()
    if (!validateAdminForm()) return
    setAdminError('')
    setLoading(true)
    try {
      await register({
        full_name: adminForm.full_name,
        email: adminForm.email,
        password: adminForm.password,
        role: 'admin',
      })
      toast.success('Admin account created!')
      navigate('/admin', { replace: true })
    } catch (err) {
      const detail = err.response?.data?.detail
      setAdminError(typeof detail === 'string' ? detail : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  const inputClass = (field) =>
    `w-full pl-10 pr-4 py-3 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary ${
      errors[field] ? 'border-error' : 'border-gray-200'
    }`

  const adminInputClass = (field) =>
    `w-full pl-10 pr-4 py-3 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary ${
      adminErrors[field] ? 'border-error' : 'border-gray-200'
    }`

  return (
    <>
      <Helmet><title>Register — TravelBooking</title></Helmet>
      <div className="min-h-[80vh] flex items-center justify-center px-4 py-12 bg-surface">
        <div className="w-full max-w-md space-y-5">
          <div className="bg-white rounded-2xl shadow-lg p-8">
            <h1 className="font-heading text-2xl font-bold text-center mb-1">Create Account</h1>
            <p className="text-gray-500 text-center text-sm mb-8">Start your journey with us</p>

            {errors.server && (
              <div className="bg-red-50 text-error text-sm px-4 py-3 rounded-lg mb-6">{errors.server}</div>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Full Name</label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input type="text" value={form.full_name}
                    onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                    className={inputClass('full_name')} placeholder="John Doe" />
                </div>
                {errors.full_name && <p className="text-error text-xs mt-1">{errors.full_name}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input type="email" value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className={inputClass('email')} placeholder="your@email.com" />
                </div>
                {errors.email && <p className="text-error text-xs mt-1">{errors.email}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input type={showPassword ? 'text' : 'password'} value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                    className={`${inputClass('password')} pr-12`} placeholder="Min. 8 characters" />
                  <button type="button" onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
                {errors.password && <p className="text-error text-xs mt-1">{errors.password}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1.5">Confirm Password</label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                  <input type="password" value={form.confirmPassword}
                    onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })}
                    className={inputClass('confirmPassword')} placeholder="Re-enter your password" />
                </div>
                {errors.confirmPassword && <p className="text-error text-xs mt-1">{errors.confirmPassword}</p>}
              </div>

              <label className="flex items-start gap-2">
                <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)}
                  className="rounded border-gray-300 mt-1" />
                <span className="text-sm text-gray-600">
                  I agree to the <a href="#" className="text-primary font-medium">Terms of Service</a> and{' '}
                  <a href="#" className="text-primary font-medium">Privacy Policy</a>
                </span>
              </label>
              {errors.agreed && <p className="text-error text-xs">{errors.agreed}</p>}

              <button type="submit" disabled={loading}
                className="w-full bg-accent hover:bg-accent-dark disabled:bg-gray-300 text-white font-semibold py-3 rounded-lg transition-colors">
                {loading ? 'Creating account...' : 'Create Account'}
              </button>
            </form>

            <p className="text-center text-sm text-gray-500 mt-6">
              Already have an account?{' '}
              <Link to="/login" className="text-primary font-semibold hover:underline">Sign In</Link>
            </p>
          </div>

          <div className="bg-white rounded-2xl shadow-lg overflow-hidden">
            <button
              type="button"
              onClick={() => { setShowAdminRegister(!showAdminRegister); setAdminError(''); setAdminErrors({}) }}
              className="w-full flex items-center justify-between px-8 py-4 text-sm font-medium text-gray-600 hover:bg-gray-50 transition-colors"
            >
              <span className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-primary" />
                Register as Admin
              </span>
              <ChevronDown className={`w-4 h-4 transition-transform ${showAdminRegister ? 'rotate-180' : ''}`} />
            </button>

            {showAdminRegister && (
              <div className="px-8 pb-8 pt-2">
                <p className="text-gray-500 text-sm mb-6">Create an administrator account to manage the platform.</p>

                {adminError && (
                  <div className="bg-red-50 text-error text-sm px-4 py-3 rounded-lg mb-6">{adminError}</div>
                )}

                <form onSubmit={handleAdminRegister} className="space-y-5">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">Full Name</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="text"
                        value={adminForm.full_name}
                        onChange={(e) => setAdminForm({ ...adminForm, full_name: e.target.value })}
                        className={adminInputClass('full_name')}
                        placeholder="Admin Name"
                      />
                    </div>
                    {adminErrors.full_name && <p className="text-error text-xs mt-1">{adminErrors.full_name}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="email"
                        value={adminForm.email}
                        onChange={(e) => setAdminForm({ ...adminForm, email: e.target.value })}
                        className={adminInputClass('email')}
                        placeholder="admin@email.com"
                      />
                    </div>
                    {adminErrors.email && <p className="text-error text-xs mt-1">{adminErrors.email}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">Password</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type={showAdminPassword ? 'text' : 'password'}
                        value={adminForm.password}
                        onChange={(e) => setAdminForm({ ...adminForm, password: e.target.value })}
                        className={`${adminInputClass('password')} pr-12`}
                        placeholder="Min. 8 characters"
                      />
                      <button type="button" onClick={() => setShowAdminPassword(!showAdminPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
                        {showAdminPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                    {adminErrors.password && <p className="text-error text-xs mt-1">{adminErrors.password}</p>}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1.5">Confirm Password</label>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
                      <input
                        type="password"
                        value={adminForm.confirmPassword}
                        onChange={(e) => setAdminForm({ ...adminForm, confirmPassword: e.target.value })}
                        className={adminInputClass('confirmPassword')}
                        placeholder="Re-enter your password"
                      />
                    </div>
                    {adminErrors.confirmPassword && <p className="text-error text-xs mt-1">{adminErrors.confirmPassword}</p>}
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-primary hover:bg-primary/90 disabled:bg-gray-300 text-white font-semibold py-3 rounded-lg transition-colors"
                  >
                    {loading ? 'Creating admin...' : 'Create Admin Account'}
                  </button>
                </form>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
