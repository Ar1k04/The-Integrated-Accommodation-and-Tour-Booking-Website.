import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { useEscapeKey } from '@/hooks/useEscapeKey'
import HotelsMapPanel from './HotelsMapPanel'

export default function HotelsMapModal({ open, onClose, hotels = [], title = 'Map of all hotels' }) {
  useEscapeKey(onClose, open)
  useEffect(() => {
    if (!open) return
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = prev
    }
  }, [open])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-[1000] flex items-start justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="relative mx-auto my-8 w-full max-w-6xl rounded-2xl bg-white overflow-hidden shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200">
          <h2 className="font-heading font-bold text-lg text-gray-900">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close map"
            className="p-1.5 rounded-full hover:bg-gray-100 text-gray-500"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <HotelsMapPanel hotels={hotels} height="h-[75vh]" />
      </div>
    </div>,
    document.body
  )
}
