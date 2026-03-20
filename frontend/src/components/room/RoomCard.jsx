import { Users, Bed } from 'lucide-react'
import { formatCurrency } from '@/utils/formatters'

export default function RoomCard({ room, onReserve }) {
  const mainImage = room.images?.[0] || 'https://placehold.co/300x200?text=Room'

  return (
    <div className="border rounded-xl overflow-hidden flex flex-col md:flex-row hover:shadow-md transition-shadow">
      <div className="md:w-48 shrink-0">
        <img src={mainImage} alt={room.name} className="w-full h-40 md:h-full object-cover" />
      </div>
      <div className="flex-1 p-4 flex flex-col justify-between">
        <div>
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-heading font-bold text-gray-900">{room.name}</h3>
              <span className="inline-block mt-1 text-xs bg-blue-50 text-primary px-2 py-0.5 rounded capitalize">
                {room.room_type}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
            <span className="flex items-center gap-1"><Users className="w-4 h-4" /> {room.max_guests} guests</span>
            <span className="flex items-center gap-1"><Bed className="w-4 h-4" /> {room.room_type}</span>
          </div>
          {room.amenities?.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-2">
              {room.amenities.slice(0, 4).map((a) => (
                <span key={a} className="text-xs bg-gray-100 px-2 py-0.5 rounded capitalize">{a}</span>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-end justify-between mt-3 pt-3 border-t">
          <div>
            <p className="text-xl font-bold text-gray-900">{formatCurrency(room.price_per_night)}</p>
            <p className="text-xs text-gray-500">per night</p>
          </div>
          <button onClick={() => onReserve(room)}
            className="bg-accent hover:bg-accent-dark text-white font-semibold px-5 py-2.5 rounded-lg text-sm transition-colors">
            Reserve
          </button>
        </div>
      </div>
    </div>
  )
}
