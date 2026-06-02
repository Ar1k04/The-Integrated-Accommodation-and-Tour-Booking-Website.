import { useGoogleLogin } from '@react-oauth/google'
import { useTranslation } from 'react-i18next'

/**
 * Custom "Continue with Google" button.
 *
 * Unlike the official <GoogleLogin> widget (whose text is rendered by Google's
 * GSI script and does NOT re-localize on runtime language changes), this button
 * uses our own i18n text so it always matches the app language. It triggers the
 * Google OAuth implicit popup and hands the resulting access token to onSuccess.
 */
function GoogleGlyph() {
  return (
    <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z" />
      <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84Z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38Z" />
    </svg>
  )
}

export default function GoogleButton({ onSuccess, onError, mode = 'signin', disabled = false }) {
  const { t } = useTranslation('auth')

  const trigger = useGoogleLogin({
    scope: 'openid email profile',
    onSuccess: (resp) => onSuccess?.(resp.access_token),
    onError: () => onError?.(),
  })

  const label = mode === 'signup' ? t('login.googleSignup') : t('login.google')

  return (
    <button
      type="button"
      onClick={() => trigger()}
      disabled={disabled}
      className="w-full flex items-center justify-center gap-3 border border-gray-300 rounded-lg py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
    >
      <GoogleGlyph />
      {label}
    </button>
  )
}
