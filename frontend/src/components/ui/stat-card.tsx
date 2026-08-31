'use client'

import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface StatCardProps {
  title: string
  value: string | number
  icon: React.ReactNode
  subtitle?: string
  trend?: {
    value: number
    label: string
    isPositive?: boolean
  }
  variant?: 'default' | 'emerald' | 'rose' | 'amber' | 'teal' | 'purple' | 'blue'
}

export function StatCard({
  title,
  value,
  icon,
  subtitle,
  trend,
  variant = 'default',
}: StatCardProps) {
  const variantStyles = {
    default: 'bg-slate-50 text-slate-700 border-slate-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    rose: 'bg-rose-50 text-rose-700 border-rose-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    teal: 'bg-teal-50 text-teal-700 border-teal-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
  }

  return (
    <Card className="border-slate-200/80 shadow-xs hover:shadow-md transition-all duration-200">
      <CardContent className="p-5 flex items-center justify-between">
        <div className="space-y-1">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</p>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl font-extrabold text-slate-900 tracking-tight">{value}</span>
            {trend && (
              <span
                className={cn(
                  'text-[11px] font-semibold px-1.5 py-0.5 rounded-full',
                  trend.isPositive ? 'bg-emerald-100 text-emerald-800' : 'bg-rose-100 text-rose-800'
                )}
              >
                {trend.isPositive ? '+' : ''}{trend.value}%
              </span>
            )}
          </div>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </div>

        <div className={cn('p-3 rounded-xl border flex items-center justify-center', variantStyles[variant])}>
          {icon}
        </div>
      </CardContent>
    </Card>
  )
}
