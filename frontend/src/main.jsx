import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { GoogleOAuthProvider } from '@react-oauth/google'
import { HelmetProvider } from 'react-helmet-async'
import { router } from './router'
import { queryClient } from './lib/queryClient'
import { useAuthStore } from './store/authStore'
import { useUiStore } from './store/uiStore'
import './i18n'
import 'leaflet/dist/leaflet.css'
import './index.css'

useAuthStore.getState().initialize()
useUiStore.getState().initExchangeRate()

const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || ''

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <GoogleOAuthProvider clientId={googleClientId}>
      <HelmetProvider>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </HelmetProvider>
    </GoogleOAuthProvider>
  </StrictMode>
)
