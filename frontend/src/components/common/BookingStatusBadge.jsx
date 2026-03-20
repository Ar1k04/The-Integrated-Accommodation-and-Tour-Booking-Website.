const STATUS_STYLES = {
  pending: 'bg-yellow-100 text-yellow-800',
  confirmed: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
  completed: 'bg-blue-100 text-blue-800',
  unpaid: 'bg-gray-100 text-gray-800',
  paid: 'bg-green-100 text-green-800',
  refunded: 'bg-purple-100 text-purple-800',
}

export default function BookingStatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${STATUS_STYLES[status] || 'bg-gray-100 text-gray-800'}`}>
      {status}
    </span>
  )
}
