import { Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import Navbar from './Navbar'
import Footer from './Footer'
import ErrorBoundary from './ErrorBoundary'
import PageTransition from './PageTransition'
import { Toaster } from 'sonner'

export default function AppLayout() {
  const { t } = useTranslation('common')
  return (
    <div className="flex flex-col min-h-screen">
      {/* Skip-to-content link: visible on focus, hidden otherwise */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[9999] bg-primary text-white text-sm font-semibold px-4 py-2 rounded-lg"
      >
        {t('common.skipToContent', 'Skip to main content')}
      </a>
      <Navbar />
      <main id="main-content" className="flex-1">
        <ErrorBoundary>
          <PageTransition>
            <Outlet />
          </PageTransition>
        </ErrorBoundary>
      </main>
      <Footer />
      <Toaster position="top-right" richColors closeButton />
    </div>
  )
}
