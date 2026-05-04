import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Helmet } from 'react-helmet-async'
import { useTranslation } from 'react-i18next'
import { bookingsApi } from '@/api/bookingsApi'
import { useFormatCurrency } from '@/hooks/useFormatCurrency'
import { formatDate } from '@/utils/formatters'
import Skeleton from '@/components/common/Skeleton'
import { CheckCircle, Download, Calendar, Users, Copy } from 'lucide-react'
import { toast } from 'sonner'
import { motion } from 'framer-motion'

export default function BookingConfirmationPage() {
  const { id } = useParams()
  const { t } = useTranslation('booking')
  const fmt = useFormatCurrency()

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
    let y = 55
    ;(booking?.items || []).forEach((item, idx) => {
      if (item.item_type === 'room') {
        doc.text(`Item ${idx + 1}: Hotel Room`, 20, y); y += 10
        doc.text(`  Check-in: ${formatDate(item.check_in)}  Check-out: ${formatDate(item.check_out)}`, 20, y); y += 10
        doc.text(`  Rooms: ${item.quantity}  Subtotal: ${fmt(item.subtotal)}`, 20, y); y += 10
      } else if (item.item_type === 'tour') {
        doc.text(`Item ${idx + 1}: Tour`, 20, y); y += 10
        doc.text(`  Date: ${formatDate(item.check_in)}  Pax: ${item.quantity}  Subtotal: ${fmt(item.subtotal)}`, 20, y); y += 10
      } else if (item.item_type === 'flight') {
        doc.text(`Item ${idx + 1}: Flight`, 20, y); y += 10
        doc.text(`  Subtotal: ${fmt(item.subtotal)}`, 20, y); y += 10
      }
    })
    doc.text(`Total: ${fmt(booking?.total_price)}`, 20, y); y += 10
    doc.text(`Status: ${booking?.status}`, 20, y)
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
      <Helmet><title>{t('confirmation.title')} — TravelBooking</title></Helmet>
      <div className="max-w-2xl mx-auto px-4 py-12">
        <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: 'spring', duration: 0.6 }}
          className="text-center mb-8">
          <CheckCircle className="w-20 h-20 text-success mx-auto" />
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <h1 className="font-heading text-3xl font-bold text-center text-gray-900 mb-2">{t('confirmation.title')}</h1>
          <p className="text-gray-500 text-center mb-8">{t('confirmation.subtitle')}</p>

          <div className="bg-white rounded-2xl border shadow-sm p-6 space-y-6">
            <div className="text-center">
              <p className="text-sm text-gray-500 mb-1">{t('confirmation.bookingRef')}</p>
              <div className="flex items-center justify-center gap-2">
                <code className="text-lg font-mono font-bold text-primary">{id?.slice(0, 8).toUpperCase()}</code>
                <button onClick={copyRef} className="text-gray-400 hover:text-primary"><Copy className="w-4 h-4" /></button>
              </div>
            </div>

            <hr />

            {(() => {
              const roomItem = booking?.items?.find(i => i.item_type === 'room')
              const tourItem = booking?.items?.find(i => i.item_type === 'tour')
              const flightItem = booking?.items?.find(i => i.item_type === 'flight')
              return (
                <div className="grid grid-cols-2 gap-4 text-sm">
                  {roomItem && (
                    <>
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-gray-500">{t('summary.checkIn')}</p>
                          <p className="font-medium">{formatDate(roomItem.check_in)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Calendar className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-gray-500">{t('summary.checkOut')}</p>
                          <p className="font-medium">{formatDate(roomItem.check_out)}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Users className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-gray-500">Rooms</p>
                          <p className="font-medium">{roomItem.quantity}</p>
                        </div>
                      </div>
                    </>
                  )}
                  {tourItem && (
                    <div className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-gray-400" />
                      <div>
                        <p className="text-gray-500">Tour Date</p>
                        <p className="font-medium">{formatDate(tourItem.check_in)}</p>
                      </div>
                    </div>
                  )}
                  {flightItem && (
                    <div className="flex items-center gap-2">
                      <Users className="w-4 h-4 text-gray-400" />
                      <div>
                        <p className="text-gray-500">Passengers</p>
                        <p className="font-medium">{flightItem.quantity}</p>
                      </div>
                    </div>
                  )}
                  <div>
                    <p className="text-gray-500">Total Paid</p>
                    <p className="font-bold text-lg text-primary">{fmt(booking?.total_price)}</p>
                  </div>
                </div>
              )
            })()}

            <hr />

            <div className="flex flex-col sm:flex-row gap-3">
              <button onClick={handleDownloadPDF}
                className="flex-1 flex items-center justify-center gap-2 border border-primary text-primary font-semibold py-2.5 rounded-lg hover:bg-primary/5">
                <Download className="w-4 h-4" /> {t('confirmation.downloadPdf')}
              </button>
              <Link to="/profile?tab=bookings"
                className="flex-1 flex items-center justify-center gap-2 bg-primary text-white font-semibold py-2.5 rounded-lg hover:bg-primary-dark">
                {t('confirmation.viewBookings')}
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </>
  )
}
