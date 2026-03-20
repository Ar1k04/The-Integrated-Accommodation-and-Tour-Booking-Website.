import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { bookingsApi } from '@/api/bookingsApi'
import { formatDate, formatCurrency } from '@/utils/formatters'
import Skeleton from '@/components/common/Skeleton'
import { CheckCircle, Download, Calendar, Users, Copy } from 'lucide-react'
import { toast } from 'sonner'
import { motion } from 'framer-motion'

export default function BookingConfirmationPage() {
  const { id } = useParams()

  const { data: booking, isLoading } = useQuery({
    queryKey: ['booking', id],
    queryFn: () => bookingsApi.get(id),
    select: (res) => res.data,
  })

  const copyRef = () => {
    navigator.clipboard.writeText(id)
    toast.success('Booking reference copied!')
  }

  const handleDownloadPDF = async () => {
    const { default: jsPDF } = await import('jspdf')
    const doc = new jsPDF()
    doc.setFontSize(20)
    doc.text('TravelBooking — Confirmation', 20, 20)
    doc.setFontSize(12)
    doc.text(`Booking Reference: ${id}`, 20, 40)
    doc.text(`Check-in: ${formatDate(booking.check_in)}`, 20, 55)
    doc.text(`Check-out: ${formatDate(booking.check_out)}`, 20, 65)
    doc.text(`Guests: ${booking.guests_count}`, 20, 75)
    doc.text(`Total: ${formatCurrency(booking.total_price)}`, 20, 85)
    doc.text(`Status: ${booking.status}`, 20, 95)
    doc.save(`booking-${id.slice(0, 8)}.pdf`)
  }

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-20 space-y-4">
        <Skeleton className="h-16 w-16 rounded-full mx-auto" />
        <Skeleton className="h-8 w-1/2 mx-auto" />
        <Skeleton className="h-40 w-full" />
      </div>
    )
  }

  return (
    <>
      <Helmet><title>Booking Confirmed — TravelBooking</title></Helmet>
      <div className="max-w-2xl mx-auto px-4 py-12">
        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', duration: 0.6 }}
          className="text-center mb-8">
          <CheckCircle className="w-20 h-20 text-success mx-auto" />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <h1 className="font-heading text-3xl font-bold text-center text-gray-900 mb-2">Booking Confirmed!</h1>
          <p className="text-gray-500 text-center mb-8">Thank you for your reservation. Here are your booking details.</p>

          <div className="bg-white rounded-2xl border shadow-sm p-6 space-y-6">
            <div className="text-center">
              <p className="text-sm text-gray-500 mb-1">Booking Reference</p>
              <div className="flex items-center justify-center gap-2">
                <code className="text-lg font-mono font-bold text-primary">{id?.slice(0, 8).toUpperCase()}</code>
                <button onClick={copyRef} className="text-gray-400 hover:text-primary"><Copy className="w-4 h-4" /></button>
              </div>
            </div>

            <hr />

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-gray-400" />
                <div>
                  <p className="text-gray-500">Check-in</p>
                  <p className="font-medium">{formatDate(booking?.check_in)}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="w-4 h-4 text-gray-400" />
                <div>
                  <p className="text-gray-500">Check-out</p>
                  <p className="font-medium">{formatDate(booking?.check_out)}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-gray-400" />
                <div>
                  <p className="text-gray-500">Guests</p>
                  <p className="font-medium">{booking?.guests_count}</p>
                </div>
              </div>
              <div>
                <p className="text-gray-500">Total Paid</p>
                <p className="font-bold text-lg text-primary">{formatCurrency(booking?.total_price)}</p>
              </div>
            </div>

            <hr />

            <div className="flex flex-col sm:flex-row gap-3">
              <button onClick={handleDownloadPDF}
                className="flex-1 flex items-center justify-center gap-2 border border-primary text-primary font-semibold py-2.5 rounded-lg hover:bg-primary/5">
                <Download className="w-4 h-4" /> Download PDF
              </button>
              <Link to="/profile?tab=bookings"
                className="flex-1 flex items-center justify-center gap-2 bg-primary text-white font-semibold py-2.5 rounded-lg hover:bg-primary-dark">
                View All Bookings
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </>
  )
}
