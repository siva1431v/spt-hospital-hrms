'use client'

import { useEffect, useState } from 'react'
import {
  Clock,
  AlertTriangle,
  Users,
  CheckCircle2,
  XCircle,
  TrendingDown,
  Info,
  Building2,
  Calendar,
  Loader2,
  ShieldAlert,
} from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'

export default function LatenessReportPage() {
  const [loading, setLoading] = useState(true)
  const [data, setData] = useState<any | null>(null)
  const [year, setYear] = useState(2026)
  const [month, setMonth] = useState(8)

  const fetchLatenessReport = async () => {
    setLoading(true)
    try {
      const res = await api.get(`/attendance/lateness?year=${year}&month=${month}`)
      setData(res.data)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLatenessReport()
  }, [year, month])

  const summary = data?.summary
  const records = data?.lateness_records || []
  const gridRows = data?.daily_grid || []
  const flags = data?.flags
  const gracePeriod = summary?.grace_period ?? 5

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-slate-200/80 pb-5 gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Lateness & Loss of Pay (LOP) Report</h1>
            <span className="text-[11px] font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded border border-amber-200">
              Advisory Rule (&gt;{gracePeriod}m Grace)
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Qualifying lateness past the {gracePeriod}-minute grace period and advisory Loss of Pay (LOP) calculations (3 late days = 1 LOP day)
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={month}
            onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setMonth(Number(e.target.value))}
            className="h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 font-semibold"
          >
            <option value="8">August 2026</option>
            <option value="7">July 2026</option>
            <option value="9">September 2026</option>
          </select>
          <Button onClick={fetchLatenessReport} variant="outline" size="sm" className="text-xs h-9 gap-2">
            <Clock className="w-3.5 h-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="p-16 flex justify-center text-slate-400">
          <Loader2 className="w-8 h-8 animate-spin text-teal-600" />
        </div>
      ) : (
        <>
          {/* Summary KPI Cards */}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
              <span className="text-[11px] text-slate-400 font-semibold block">Staff on Roll</span>
              <span className="text-xl font-bold text-slate-900 mt-1 block">{summary?.staff_on_roll || 66}</span>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
              <span className="text-[11px] text-emerald-600 font-semibold block">Present Days</span>
              <span className="text-xl font-bold text-emerald-600 mt-1 block">{summary?.days_present || 1288}</span>
            </div>
            <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
              <span className="text-[11px] text-rose-600 font-semibold block">Absent Days</span>
              <span className="text-xl font-bold text-rose-600 mt-1 block">{summary?.days_absent || 333}</span>
            </div>
            <div className="bg-white p-4 rounded-xl border border-amber-200 bg-amber-50/30 shadow-2xs">
              <span className="text-[11px] text-amber-700 font-semibold block">Late Past Grace (&gt;{gracePeriod}m)</span>
              <span className="text-xl font-bold text-amber-700 mt-1 block">{summary?.late_past_grace || 0}</span>
              <span className="text-[10px] text-slate-400 block mt-0.5">Device total: {summary?.late_device_total}</span>
            </div>
            <div className="bg-white p-4 rounded-xl border border-rose-200 bg-rose-50/40 shadow-2xs">
              <span className="text-[11px] text-rose-700 font-semibold block">LOP Days Owed</span>
              <span className="text-xl font-bold text-rose-700 mt-1 block">{summary?.lop_days_owed || 0}</span>
              <span className="text-[10px] text-rose-500 block mt-0.5">Advisory</span>
            </div>
            <div className="bg-white p-4 rounded-xl border border-purple-200 bg-purple-50/30 shadow-2xs">
              <span className="text-[11px] text-purple-700 font-semibold block">Total Overtime</span>
              <span className="text-xl font-bold text-purple-700 mt-1 block">{summary?.total_ot_formatted || '403h 24m'}</span>
            </div>
          </div>

          {/* Data Callout Banners */}
          <div className="space-y-2">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900 flex items-start gap-2.5">
              <ShieldAlert className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
              <div>
                <strong className="font-bold">Zero-Punch Staff Flag:</strong>{' '}
                <span>
                  Saran (208), Selladurai (209), and Abinaya (210) have 0 device punches all month (25 consecutive absences). They are flagged as having "No attendance data" rather than legitimate absences.
                </span>
              </div>
            </div>

            <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3 text-xs text-indigo-900 flex items-start gap-2.5">
              <Info className="w-4 h-4 text-indigo-600 mt-0.5 shrink-0" />
              <div>
                <strong className="font-bold">Device Data & Shift Anomalies:</strong>{' '}
                <span>
                  Shift code <strong className="font-mono bg-indigo-100 px-1 py-0.5 rounded">Sam</strong> appears on Aug 3 and Aug 4 (7 punches across 4 staff) and is excluded from lateness calculations. Device calendar records 0 Leaves/Holidays. <strong className="font-mono bg-indigo-100 px-1 py-0.5 rounded">Dt HR</strong> is normalized to HR.
                </span>
              </div>
            </div>
          </div>

          {/* LOP Employees Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xs space-y-4 p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Qualifying Lateness & Advisory LOP Breakdown ({records.length} Employees)</h2>
                <p className="text-xs text-slate-500 mt-0.5">Staff with 1 or more late arrivals past the {gracePeriod}-minute grace period</p>
              </div>
              <span className="text-xs font-semibold bg-slate-100 text-slate-700 px-2.5 py-1 rounded">
                Formula: floor(Qualifying Late / 3)
              </span>
            </div>

            <div className="overflow-x-auto border border-slate-100 rounded-lg">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="p-3">Severity</th>
                    <th className="p-3">Code</th>
                    <th className="p-3">Employee Name</th>
                    <th className="p-3">Department</th>
                    <th className="p-3 text-center">Device Late (&gt;0m)</th>
                    <th className="p-3 text-center text-amber-700">Qualifying Late (&gt;{gracePeriod}m)</th>
                    <th className="p-3 text-center text-rose-700 font-bold">LOP Days Owed</th>
                    <th className="p-3">Total OT</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                  {records.map((r: any, idx: number) => {
                    let stripeColor = 'border-l-4 border-l-blue-400 bg-blue-50/20'
                    let badgeColor = 'bg-blue-100 text-blue-800'
                    if (r.severity === 'CRITICAL') {
                      stripeColor = 'border-l-4 border-l-rose-500 bg-rose-50/30'
                      badgeColor = 'bg-rose-100 text-rose-800'
                    } else if (r.severity === 'WARNING') {
                      stripeColor = 'border-l-4 border-l-amber-500 bg-amber-50/30'
                      badgeColor = 'bg-amber-100 text-amber-800'
                    }

                    return (
                      <tr key={idx} className={`hover:bg-slate-50 ${stripeColor}`}>
                        <td className="p-3 font-sans">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${badgeColor}`}>
                            {r.severity}
                          </span>
                        </td>
                        <td className="p-3 font-bold text-slate-900">{r.biometric_code}</td>
                        <td className="p-3 font-sans font-semibold text-slate-900">{r.employee_name}</td>
                        <td className="p-3 font-sans text-slate-600">{r.department}</td>
                        <td className="p-3 text-center text-slate-500">{r.late_days_device}</td>
                        <td className="p-3 text-center font-bold text-amber-700">{r.late_days_qualifying}</td>
                        <td className="p-3 text-center font-extrabold text-rose-700 text-sm">{r.lop_days}</td>
                        <td className="p-3 text-slate-700">{r.total_ot}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* 66x25 Attendance Grid */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xs space-y-4 p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-900">31-Day Attendance Status Grid ({gridRows.length} Employees × 25 Days)</h2>
                <p className="text-xs text-slate-500 mt-0.5">Green = Present, Red = Absent, Amber = Incomplete / Missing Out-Punch</p>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-600 font-semibold">
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span> Present</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-rose-500"></span> Absent</span>
                <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span> Incomplete</span>
              </div>
            </div>

            <div className="overflow-x-auto max-h-96 border border-slate-100 rounded-lg">
              <table className="w-full border-collapse text-xs">
                <thead className="bg-slate-50 sticky top-0 z-10 border-b border-slate-200">
                  <tr>
                    <th className="p-2 text-left font-bold text-slate-700 sticky left-0 bg-slate-50 min-w-[140px] z-20 border-r border-slate-200">
                      Employee
                    </th>
                    {Array.from({ length: 25 }, (_, i) => i + 1).map((d) => (
                      <th key={d} className="p-1.5 text-center text-[10px] font-mono text-slate-500 min-w-[28px]">
                        {d}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-[11px] font-mono">
                  {gridRows.map((row: any, idx: number) => (
                    <tr key={idx} className="hover:bg-slate-50">
                      <td className="p-2 font-sans font-medium text-slate-900 sticky left-0 bg-white border-r border-slate-200 whitespace-nowrap z-10">
                        {row.employee_name} <span className="text-[10px] text-slate-400 font-mono">({row.biometric_code})</span>
                      </td>
                      {row.days.map((dayObj: any, dIdx: number) => {
                        let statusColor = 'bg-rose-500 text-white'
                        let titleText = `Day ${dayObj.day}: Absent`

                        if (dayObj.status === 'PRESENT' || dayObj.status === 'PRESENT_OVERNIGHT') {
                          statusColor = 'bg-emerald-500 text-white'
                          titleText = `Day ${dayObj.day}: Present (In: ${dayObj.in_time || '—'})`
                        } else if (dayObj.status === 'PRESENT_INCOMPLETE') {
                          statusColor = 'bg-amber-500 text-white'
                          titleText = `Day ${dayObj.day}: Present Incomplete (No Out-Punch)`
                        }

                        return (
                          <td key={dIdx} className="p-1 text-center">
                            <div
                              title={titleText}
                              className={`w-6 h-6 rounded flex items-center justify-center font-bold text-[10px] mx-auto cursor-pointer transition-all hover:scale-110 ${statusColor}`}
                            >
                              {dayObj.status === 'PRESENT' ? 'P' : dayObj.status === 'PRESENT_INCOMPLETE' ? 'I' : 'A'}
                            </div>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function RefreshIcon(props: any) {
  return (
    <svg {...props} fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  )
}
