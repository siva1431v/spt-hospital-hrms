'use client'

import { usePathname } from 'next/navigation'
import { Bell, ChevronRight, Menu, User as UserIcon } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'

interface TopNavProps {
  onMenuToggle?: () => void
}

export function TopNav({ onMenuToggle }: TopNavProps) {
  const pathname = usePathname()
  const { user } = useAuth()

  // Generate breadcrumb from path
  const pathSegments = pathname.split('/').filter(Boolean)
  const formattedSegments = pathSegments.map((segment, idx) => {
    if (/^\d+$/.test(segment)) {
      const prev = pathSegments[idx - 1]?.toLowerCase()
      if (prev === 'employees') return 'Profile'
      if (prev === 'imports' || prev === 'import-history') return 'Detail'
      return `Item #${segment}`
    }
    return segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, ' ')
  })

  return (
    <header className="h-16 border-b border-slate-200 bg-white px-6 flex items-center justify-between sticky top-0 z-30 shadow-xs">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
        {onMenuToggle && (
          <button
            onClick={onMenuToggle}
            className="md:hidden p-2 -ml-2 mr-2 rounded-lg text-slate-600 hover:bg-slate-100"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}
        <span className="text-slate-400">SPT HRMS</span>
        {formattedSegments.map((segment, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <ChevronRight className="w-3 h-3 text-slate-400" />
            <span className={idx === formattedSegments.length - 1 ? 'text-slate-900 font-semibold' : 'text-slate-500'}>
              {segment}
            </span>
          </div>
        ))}
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-4">
        {/* User Info */}
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-teal-50 border border-teal-200 text-teal-700 flex items-center justify-center text-xs font-bold">
            <UserIcon className="w-3.5 h-3.5 text-teal-600" />
          </div>
          <span className="text-xs font-semibold text-slate-800">{user?.full_name || 'Administrator'}</span>
        </div>
      </div>
    </header>
  )
}
