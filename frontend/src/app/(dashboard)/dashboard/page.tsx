'use client'

import { useEffect, useState } from 'react'
import {
  Users,
  UserCheck,
  UserX,
  AlertCircle,
  Clock,
  CalendarOff,
  Timer,
  IndianRupee,
  Upload,
  UserPlus,
  RefreshCw,
  ArrowUpRight,
} from 'lucide-react'
import api from '@/lib/api'
import { StatCard } from '@/components/ui/stat-card'
import { DashboardStats } from '@/types'
import Link from 'next/link'

interface ActivityItem {
  id: number | string
  description: string
  user_name?: string
  entity_type?: string
  created_at: string
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [, setTrendData] = useState<Record<string, unknown>[]>([])
  const [, setDeptData] = useState<Record<string, unknown>[]>([])
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  const refresh = () => {
    setLoading(true)
    setRefreshTrigger((n) => n + 1)
  }

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const [statsRes, trendRes, deptRes, activityRes] = await Promise.allSettled([
          api.get('/dashboard/stats'),
          api.get('/dashboard/attendance-trend'),
          api.get('/dashboard/dept-attendance'),
          api.get('/dashboard/recent-activity'),
        ])

        if (active) {
          if (statsRes.status === 'fulfilled') setStats(statsRes.value.data)
          if (trendRes.status === 'fulfilled') setTrendData(trendRes.value.data.data || [])
          if (deptRes.status === 'fulfilled') setDeptData(deptRes.value.data.data || [])
          if (activityRes.status === 'fulfilled') setActivities(activityRes.value.data.items || [])
        }
      } catch (err) {
        console.error('Failed to fetch dashboard stats', err)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [refreshTrigger])

  return (
    <div className="space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Hospital Overview</h1>
          <p className="text-xs text-slate-500 mt-1">Real-time attendance & payroll metrics for SPT Hospital</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={refresh}
            className="p-2 rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 text-xs font-semibold flex items-center gap-1.5 shadow-2xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          <Link
            href="/attendance/import"
            className="px-3.5 py-2 rounded-lg bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold flex items-center gap-2 shadow-sm shadow-teal-600/20"
          >
            <Upload className="w-3.5 h-3.5" />
            Import eSSL PDF
          </Link>
        </div>
      </div>

      {/* KPI Cards Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Employees"
          value={stats?.total_employees ?? '—'}
          icon={<Users className="w-5 h-5 text-slate-700" />}
          subtitle="Active Hospital Staff"
          variant="default"
        />
        <StatCard
          title="Present Today"
          value={stats?.present_today ?? '—'}
          icon={<UserCheck className="w-5 h-5 text-emerald-700" />}
          subtitle="Checked In"
          variant="emerald"
        />
        <StatCard
          title="Absent Today"
          value={stats?.absent_today ?? '—'}
          icon={<UserX className="w-5 h-5 text-rose-700" />}
          subtitle="Unexcused Absence"
          variant="rose"
        />
        <StatCard
          title="No Out Punch"
          value={stats?.incomplete_today ?? '—'}
          icon={<AlertCircle className="w-5 h-5 text-amber-700" />}
          subtitle="Missing Punch Out"
          variant="amber"
        />
        <StatCard
          title="Late Arrivals"
          value={stats?.late_today ?? '—'}
          icon={<Clock className="w-5 h-5 text-amber-700" />}
          subtitle="Exceeded Grace Period"
          variant="amber"
        />
        <StatCard
          title="On Leave"
          value={stats?.on_leave_today ?? '—'}
          icon={<CalendarOff className="w-5 h-5 text-blue-700" />}
          subtitle="Approved Leave Days"
          variant="blue"
        />
        <StatCard
          title="OT Hours Today"
          value={stats?.ot_hours_today != null ? `${stats.ot_hours_today} hrs` : '—'}
          icon={<Timer className="w-5 h-5 text-purple-700" />}
          subtitle="Overtime Recorded"
          variant="purple"
        />
        <StatCard
          title="Current Payroll"
          value={stats?.monthly_payroll != null ? `₹ ${stats.monthly_payroll.toLocaleString('en-IN')}` : '₹ 0'}
          icon={<IndianRupee className="w-5 h-5 text-teal-700" />}
          subtitle="This Month Total"
          variant="teal"
        />
      </div>

      {/* Main Grid: Activity & Shortcuts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Quick Actions Card */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4 shadow-xs">
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Quick Actions</h2>
          <div className="space-y-2">
            <Link
              href="/attendance/import"
              className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50 hover:bg-teal-50 hover:border-teal-200 group transition-all"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-md bg-teal-100 text-teal-700">
                  <Upload className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-900 group-hover:text-teal-700">Upload Attendance PDF</p>
                  <p className="text-[11px] text-slate-500">Import eSSL biometric report</p>
                </div>
              </div>
              <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-teal-600" />
            </Link>

            <Link
              href="/employees/new"
              className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50 hover:bg-teal-50 hover:border-teal-200 group transition-all"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-md bg-slate-200 text-slate-700">
                  <UserPlus className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-900 group-hover:text-teal-700">Add New Employee</p>
                  <p className="text-[11px] text-slate-500">Register new medical or admin staff</p>
                </div>
              </div>
              <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-teal-600" />
            </Link>

            <Link
              href="/payroll"
              className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-slate-50 hover:bg-teal-50 hover:border-teal-200 group transition-all"
            >
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-md bg-emerald-100 text-emerald-700">
                  <IndianRupee className="w-4 h-4" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-slate-900 group-hover:text-teal-700">Run Monthly Payroll</p>
                  <p className="text-[11px] text-slate-500">Calculate salary & generate slips</p>
                </div>
              </div>
              <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-teal-600" />
            </Link>
          </div>
        </div>

        {/* Recent Audit Log Activity */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 space-y-4 shadow-xs">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Recent System Activity</h2>
            <Link href="/audit-logs" className="text-xs font-semibold text-teal-600 hover:underline">
              View All Logs
            </Link>
          </div>

          <div className="divide-y divide-slate-100 max-h-[280px] overflow-y-auto">
            {activities.length > 0 ? (
              activities.map((act) => (
                <div key={act.id} className="py-2.5 flex items-start justify-between text-xs">
                  <div className="space-y-0.5">
                    <span className="font-semibold text-slate-800">{act.description}</span>
                    <p className="text-[11px] text-slate-500">
                      By <span className="font-medium text-slate-700">{act.user_name}</span> • Entity: {act.entity_type}
                    </p>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono">
                    {new Date(act.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              ))
            ) : (
              <div className="py-8 text-center text-xs text-slate-400">
                No recent activity logged yet.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
