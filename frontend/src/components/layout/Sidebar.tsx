'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard,
  Users,
  Building2,
  Clock,
  CalendarDays,
  Calendar,
  Upload,
  History,
  AlertTriangle,
  CalendarOff,
  Banknote,
  FileText,
  BarChart2,
  Shield,
  Settings,
  LogOut,
  Cross,
  TrendingDown,
} from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'

interface NavItem {
  title: string
  href: string
  icon: React.ReactNode
  roles?: string[]
}

interface NavGroup {
  group: string
  items: NavItem[]
}

interface SidebarProps {
  isOpen?: boolean
  onClose?: () => void
}

export function Sidebar({ isOpen, onClose }: SidebarProps) {
  const pathname = usePathname()
  const { user, logout } = useAuth()

  const navGroups: NavGroup[] = [
    {
      group: 'MAIN',
      items: [
        { title: 'Dashboard', href: '/dashboard', icon: <LayoutDashboard className="w-4 h-4" /> },
      ],
    },
    {
      group: 'EMPLOYEES',
      items: [
        { title: 'Employees', href: '/employees', icon: <Users className="w-4 h-4" /> },
        { title: 'Departments', href: '/departments', icon: <Building2 className="w-4 h-4" /> },
        { title: 'Shifts', href: '/shifts', icon: <Clock className="w-4 h-4" /> },
      ],
    },
    {
      group: 'ATTENDANCE',
      items: [
        { title: 'Daily Attendance', href: '/attendance', icon: <CalendarDays className="w-4 h-4" /> },
        { title: 'Monthly Summary', href: '/attendance/monthly', icon: <Calendar className="w-4 h-4" /> },
        { title: 'Lateness & LOP', href: '/attendance/lateness', icon: <TrendingDown className="w-4 h-4" /> },
        { title: 'Import PDF', href: '/attendance/import', icon: <Upload className="w-4 h-4" /> },
        { title: 'Import History', href: '/attendance/import-history', icon: <History className="w-4 h-4" /> },
        { title: 'Exceptions', href: '/attendance/exceptions', icon: <AlertTriangle className="w-4 h-4" /> },
      ],
    },
    {
      group: 'LEAVE',
      items: [
        { title: 'Leave Management', href: '/leave', icon: <CalendarOff className="w-4 h-4" /> },
      ],
    },
    {
      group: 'PAYROLL',
      items: [
        { title: 'Monthly Payroll', href: '/payroll', icon: <Banknote className="w-4 h-4" />, roles: ['SUPER_ADMIN', 'HR_ADMIN'] },
        { title: 'Salary Slips', href: '/payroll/salary-slips', icon: <FileText className="w-4 h-4" /> },
      ],
    },
    {
      group: 'REPORTS',
      items: [
        { title: 'Reports Hub', href: '/reports', icon: <BarChart2 className="w-4 h-4" /> },
      ],
    },
    {
      group: 'SYSTEM',
      items: [
        { title: 'Users', href: '/settings/users', icon: <Users className="w-4 h-4" />, roles: ['SUPER_ADMIN'] },
        { title: 'Audit Logs', href: '/audit-logs', icon: <Shield className="w-4 h-4" />, roles: ['SUPER_ADMIN', 'HR_ADMIN'] },
        { title: 'Settings', href: '/settings', icon: <Settings className="w-4 h-4" />, roles: ['SUPER_ADMIN', 'HR_ADMIN'] },
      ],
    },
  ]

  // Find single active item: match longest href that is a path prefix of pathname
  // Dashboard ('/' or '/dashboard') and '/attendance' must match exactly.
  const allItems = navGroups.flatMap((g) => g.items)
  const matchingItems = allItems.filter((item) => {
    if (item.href === '/dashboard' || item.href === '/' || item.href === '/attendance') {
      return pathname === item.href
    }
    return pathname === item.href || pathname.startsWith(item.href + '/')
  })

  let activeHref = ''
  if (matchingItems.length > 0) {
    matchingItems.sort((a, b) => b.href.length - a.href.length)
    activeHref = matchingItems[0].href
  }

  return (
    <aside
      className={cn(
        'bg-slate-900 text-slate-300 flex flex-col h-screen border-r border-slate-800 select-none',
        'fixed inset-y-0 left-0 z-50 w-64 shadow-2xl transition-transform duration-200 md:sticky md:top-0 md:z-40 md:shadow-none md:translate-x-0',
        isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
      )}
    >
      {/* Header / Logo */}
      <div className="p-5 flex items-center gap-3 border-b border-slate-800 bg-slate-950/40 shrink-0">
        <div className="w-9 h-9 rounded-lg bg-teal-500 flex items-center justify-center text-slate-950 font-bold shadow-md shadow-teal-500/20">
          <Cross className="w-5 h-5 fill-slate-950" />
        </div>
        <div>
          <h1 className="font-bold text-white tracking-wide text-base leading-none">SPT HOSPITAL</h1>
          <p className="text-[11px] text-teal-400 font-medium tracking-wider mt-1 uppercase">Attendance & Payroll</p>
        </div>
      </div>

      {/* Navigation */}
      <nav aria-label="Sidebar navigation" className="flex-1 min-h-0 overflow-y-auto px-3 py-4 space-y-6 scrollbar-thin scrollbar-thumb-slate-800">
        {navGroups.map((group, idx) => (
          <div key={idx} className="space-y-1">
            <h2 className="px-3 text-[10px] font-semibold text-slate-400 tracking-wider uppercase">
              {group.group}
            </h2>
            {group.items.map((item, itemIdx) => {
              // Role check
              if (item.roles && user?.role && !item.roles.includes(user.role)) {
                return null
              }

              const isActive = item.href === activeHref

              return (
                <Link
                  key={itemIdx}
                  href={item.href}
                  onClick={() => onClose?.()}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-md text-xs font-medium transition-all duration-150',
                    isActive
                      ? 'bg-teal-600 text-white font-semibold shadow-sm shadow-teal-600/30'
                      : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                  )}
                >
                  <span className={cn(isActive ? 'text-white' : 'text-slate-400')}>{item.icon}</span>
                  <span>{item.title}</span>
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      {/* Profile & Logout Footer */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/50 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5 overflow-hidden">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs font-semibold text-teal-400">
            {user?.full_name?.substring(0, 2).toUpperCase() || 'US'}
          </div>
          <div className="overflow-hidden">
            <p className="text-xs font-medium text-white truncate">{user?.full_name || 'Admin User'}</p>
            <span className="inline-block text-[10px] text-teal-400 font-mono tracking-tight bg-teal-950/80 px-1.5 py-0.2 rounded border border-teal-800/40">
              {user?.role || 'SUPER_ADMIN'}
            </span>
          </div>
        </div>
        <button
          onClick={logout}
          title="Logout"
          className="p-1.5 rounded-md text-slate-400 hover:text-rose-400 hover:bg-slate-800 transition-colors"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </aside>
  )
}
