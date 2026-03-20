import { Outlet } from 'react-router-dom'
import Navbar from './Navbar'
import Footer from './Footer'
import ErrorBoundary from './ErrorBoundary'
import PageTransition from './PageTransition'
import { Toaster } from 'sonner'

export default function AppLayout() {
  return (
    <div className="flex flex-col min-h-screen">
      <Navbar />
      <main className="flex-1">
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
