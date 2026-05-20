import { ChevronLeft, ChevronRight } from 'lucide-react'

function getPageNumbers(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)

  const pages = []
  pages.push(1)

  const rangeStart = Math.max(2, current - 2)
  const rangeEnd = Math.min(total - 1, current + 2)

  if (rangeStart > 2) pages.push('...')
  for (let i = rangeStart; i <= rangeEnd; i++) pages.push(i)
  if (rangeEnd < total - 1) pages.push('...')

  pages.push(total)
  return pages
}

export default function Pagination({ currentPage, totalPages, onPageChange }) {
  if (totalPages <= 1) return null

  const pages = getPageNumbers(currentPage, totalPages)

  const navBtn =
    'p-1.5 rounded-lg border border-gray-200 text-gray-600 transition-all duration-150 ' +
    'hover:bg-primary hover:text-white hover:border-primary hover:-translate-y-0.5 hover:shadow-md ' +
    'active:translate-y-0 active:shadow-sm ' +
    'disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-white disabled:hover:text-gray-600 ' +
    'disabled:hover:border-gray-200 disabled:hover:translate-y-0 disabled:hover:shadow-none'

  return (
    <div className="flex items-center justify-center gap-1.5 mt-6">
      <button
        type="button"
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
        className={navBtn}
        aria-label="Previous page"
      >
        <ChevronLeft className="w-4 h-4" />
      </button>

      {pages.map((p, i) =>
        p === '...' ? (
          <span key={`ellipsis-${i}`} className="px-2 text-gray-400 select-none">
            ...
          </span>
        ) : (
          <button
            key={p}
            type="button"
            onClick={() => onPageChange(p)}
            aria-current={p === currentPage ? 'page' : undefined}
            className={`min-w-[36px] h-9 px-2 rounded-lg text-sm font-medium border transition-all duration-150 ${
              p === currentPage
                ? 'bg-primary text-white border-primary shadow-md scale-105 cursor-default'
                : 'bg-white text-gray-700 border-gray-200 hover:bg-primary/10 hover:text-primary hover:border-primary hover:-translate-y-0.5 hover:shadow-md active:translate-y-0 active:shadow-sm'
            }`}
          >
            {p}
          </button>
        )
      )}

      <button
        type="button"
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
        className={navBtn}
        aria-label="Next page"
      >
        <ChevronRight className="w-4 h-4" />
      </button>
    </div>
  )
}
