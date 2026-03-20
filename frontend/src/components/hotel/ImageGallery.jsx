import { useState } from 'react'
import { X, ChevronLeft, ChevronRight } from 'lucide-react'

export default function ImageGallery({ images = [] }) {
  const [lightboxIdx, setLightboxIdx] = useState(null)
  const placeholders = images.length ? images : ['https://placehold.co/800x400?text=No+Images']

  return (
    <>
      <div className="grid grid-cols-4 grid-rows-2 gap-2 h-72 md:h-96 rounded-xl overflow-hidden">
        <div className="col-span-2 row-span-2 cursor-pointer" onClick={() => setLightboxIdx(0)}>
          <img src={placeholders[0]} alt="" className="w-full h-full object-cover hover:brightness-90 transition" />
        </div>
        {placeholders.slice(1, 5).map((img, i) => (
          <div key={i} className="cursor-pointer relative" onClick={() => setLightboxIdx(i + 1)}>
            <img src={img} alt="" className="w-full h-full object-cover hover:brightness-90 transition" />
            {i === 3 && images.length > 5 && (
              <div className="absolute inset-0 bg-black/50 flex items-center justify-center text-white font-bold text-lg">
                +{images.length - 5}
              </div>
            )}
          </div>
        ))}
      </div>

      {lightboxIdx !== null && (
        <div className="fixed inset-0 z-[100] bg-black/90 flex items-center justify-center" onClick={() => setLightboxIdx(null)}>
          <button className="absolute top-4 right-4 text-white" onClick={() => setLightboxIdx(null)}>
            <X className="w-8 h-8" />
          </button>
          <button className="absolute left-4 text-white" onClick={(e) => { e.stopPropagation(); setLightboxIdx(Math.max(0, lightboxIdx - 1)) }}>
            <ChevronLeft className="w-10 h-10" />
          </button>
          <img src={placeholders[lightboxIdx]} alt="" className="max-h-[80vh] max-w-[90vw] object-contain" onClick={(e) => e.stopPropagation()} />
          <button className="absolute right-4 text-white" onClick={(e) => { e.stopPropagation(); setLightboxIdx(Math.min(placeholders.length - 1, lightboxIdx + 1)) }}>
            <ChevronRight className="w-10 h-10" />
          </button>
          <p className="absolute bottom-4 text-white text-sm">{lightboxIdx + 1} / {placeholders.length}</p>
        </div>
      )}
    </>
  )
}
