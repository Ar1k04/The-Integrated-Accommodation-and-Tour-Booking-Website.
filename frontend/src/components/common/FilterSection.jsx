import { ChevronDown, ChevronUp } from 'lucide-react'

export default function FilterSection({ title, expanded, onToggle, children }) {
  return (
    <div className="bg-white rounded-xl p-4 shadow-sm">
      <button onClick={onToggle} className="flex items-center justify-between w-full text-left">
        <h3 className="font-semibold text-sm text-gray-900">{title}</h3>
        {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
      </button>
      {expanded && <div className="mt-3">{children}</div>}
    </div>
  )
}
