'use client'

import { useEffect, useState } from 'react'
import { Calendar, Filter, Search, Download, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

interface MonthlySummaryItem {
  employee_id: number
  employee_code: string
  biometric_code?: string
  employee_name: string
  department: string | null
  present: number
  absent: number
  incomplete: number
  leave: number
  late_days_device?: number
  late_days_qualifying?: number
  lop_days?: number
  ot_hours: number | string
  total_work_hours: number | string
  average_working_hrs?: string
  total_records: number
}

const MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

export default function MonthlyAttendanceSummaryPage() {
  const [summaries, setSummaries] = useState<MonthlySummaryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [gracePeriod, setGracePeriod] = useState(5)

  const [year, setYear] = useState(2026)
  const [month, setMonth] = useState(8)
  const [search, setSearch] = useState('')

  const fetchMonthlySummary = async () => {
    setLoading(true)
    try {
      const res = await api.get('/attendance/monthly', {
        params: { year, month, search: search || undefined, sort_by: 'lop_days', sort_order: 'desc' },
      })
      setSummaries(res.data.items || [])
      if (res.data.grace_period) setGracePeriod(res.data.grace_period)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchMonthlySummary()
  }, [year, month])

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    fetchMonthlySummary()
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-600 flex items-center justify-center font-bold">
            <Calendar className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Monthly Attendance Summary</h1>
            <p className="text-xs text-slate-500 mt-0.5">Aggregated attendance days, qualifying lateness (&gt;{gracePeriod}m), advisory LOP days, and OT per employee</p>
          </div>
        </div>
      </div>

      {/* Filter bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-700">Month & Year:</span>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 font-semibold"
            >
              {MONTH_NAMES.slice(1).map((mName, idx) => (
                <option key={idx + 1} value={idx + 1}>{mName}</option>
              ))}
            </select>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 font-semibold"
            >
              {[2025, 2026, 2027].map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          <form onSubmit={handleSearchSubmit} className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search staff name or code..."
                className="text-xs h-9 pl-8 w-48 sm:w-60"
              />
            </div>
            <Button type="submit" size="sm" variant="outline" className="h-9 px-3 text-xs">
              Search
            </Button>
          </form>
        </div>

        <div className="text-xs text-slate-500 font-medium">
          Default sort: <strong className="text-amber-800 bg-amber-50 px-2 py-0.5 rounded">LOP Days (Desc)</strong>
        </div>
      </div>

      {/* Summary Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-12 flex justify-center text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
          </div>
        ) : summaries.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[11px]">
                <tr>
                  <th className="p-3 pl-5">Code</th>
                  <th className="p-3">Employee Name</th>
                  <th className="p-3">Department</th>
                  <th className="p-3 text-center text-emerald-700">Present (Payable)</th>
                  <th className="p-3 text-center text-amber-600">Incomplete</th>
                  <th className="p-3 text-center">Absent</th>
                  <th className="p-3 text-center text-blue-700">Leave</th>
                  <th className="p-3 text-center text-amber-700">Late (&gt;{gracePeriod}m)</th>
                  <th className="p-3 text-center text-rose-700">LOP Days</th>
                  <th className="p-3">OT Hours</th>
                  <th className="p-3">Total Work</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {summaries.map((item) => (
                  <tr key={item.employee_id} className="hover:bg-slate-50/80">
                    <td className="p-3 pl-5 font-mono text-slate-900 font-bold">{item.biometric_code || item.employee_code}</td>
                    <td className="p-3 font-semibold text-slate-900">{item.employee_name}</td>
                    <td className="p-3 text-slate-600">{item.department || '—'}</td>
                    <td className="p-3 text-center font-mono text-emerald-700 font-bold">{item.present}</td>
                    <td className="p-3 text-center font-mono text-amber-600 font-semibold">{item.incomplete || 0}</td>
                    <td className="p-3 text-center font-mono text-rose-600 font-bold">{item.absent}</td>
                    <td className="p-3 text-center font-mono text-blue-700 font-bold">{item.leave ?? 0}</td>
                    <td className="p-3 text-center font-mono text-amber-700 font-bold">{item.late_days_qualifying ?? 0}</td>
                    <td className="p-3 text-center font-mono text-rose-700 font-extrabold">{item.lop_days ?? 0}</td>
                    <td className="p-3 font-mono text-purple-700 font-bold">{typeof item.ot_hours === 'number' ? item.ot_hours.toFixed(2) : (item.ot_hours || '0.00')}</td>
                    <td className="p-3 font-mono font-bold text-slate-900">{typeof item.total_work_hours === 'number' ? item.total_work_hours.toFixed(2) : (item.total_work_hours || '0.00')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center text-slate-400 space-y-1">
            <p className="text-sm font-semibold text-slate-600">No attendance data recorded for {MONTH_NAMES[month]} {year}.</p>
            <p className="text-xs text-slate-400">Import attendance PDFs or log daily attendance to populate monthly totals.</p>
          </div>
        )}
      </div>
    </div>
  )
}
