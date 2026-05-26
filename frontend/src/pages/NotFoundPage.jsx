import { Link, useNavigate } from 'react-router-dom'
import { Helmet } from 'react-helmet-async'
import { Home, ArrowLeft, Search } from 'lucide-react'

export default function NotFoundPage() {
  const navigate = useNavigate()
  return (
    <>
      <Helmet><title>404 — Page Not Found · TravelBooking</title></Helmet>
      <div className="min-h-[60vh] flex items-center justify-center px-4 py-16">
        <div className="max-w-md text-center">
          <p className="text-7xl font-heading font-bold text-primary mb-2">404</p>
          <h1 className="font-heading text-2xl font-bold mb-2">Page not found</h1>
          <p className="text-gray-500 mb-8">
            The page you’re looking for doesn’t exist or has been moved.
          </p>
          <div className="flex flex-wrap gap-3 justify-center">
            <button
              onClick={() => navigate(-1)}
              className="inline-flex items-center gap-2 border border-primary text-primary font-semibold px-4 py-2.5 rounded-lg hover:bg-primary/5 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" /> Go back
            </button>
            <Link
              to="/"
              className="inline-flex items-center gap-2 bg-primary text-white font-semibold px-4 py-2.5 rounded-lg hover:bg-primary/90 transition-colors"
            >
              <Home className="w-4 h-4" /> Home
            </Link>
            <Link
              to="/flights"
              className="inline-flex items-center gap-2 border text-gray-700 font-semibold px-4 py-2.5 rounded-lg hover:bg-gray-50 transition-colors"
            >
              <Search className="w-4 h-4" /> Search flights
            </Link>
          </div>
        </div>
      </div>
    </>
  )
}
