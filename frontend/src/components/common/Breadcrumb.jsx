import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'

export default function Breadcrumb({ items }) {
  return (
    <nav className="flex items-center gap-1 text-sm text-gray-500 py-3">
      {items.map((item, idx) => (
        <span key={idx} className="flex items-center gap-1">
          {idx > 0 && <ChevronRight className="w-3.5 h-3.5" />}
          {item.to ? (
            <Link to={item.to} className="hover:text-primary transition-colors">{item.label}</Link>
          ) : (
            <span className="text-gray-800 font-medium">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  )
}
