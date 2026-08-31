'use client'

import { useState } from 'react'
import { FileSpreadsheet, Download, Calendar, AlertTriangle, Clock, Banknote, Timer, Filter } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

export default function ReportsPage() {
  const [downloading, setDownloading] = useState<string | null>(null)
  const [selectedYear, setSelectedYear] = useState('2026')
  const [selectedMonth, setSelectedMonth] = useState('8')

  const handleExportExcel = async (reportType: string, endpoint: string) => {
    setDownloading(reportType)
    try {
      const response = await api.get(endpoint, {
        params: {
          format: 'excel',
          year: parseInt(selectedYear),
          month: parseInt(selectedMonth),
        },
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${reportType}_${selectedYear}_${selectedMonth.padStart(2, '0')}.xlsx`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      toast.success(`${reportType} Excel report downloaded successfully!`)
    } catch (err) {
      toast.error(`Failed to export ${reportType} report.`)
    } finally {
      setDownloading(null)
    }
  }

  const reports = [
    {
      id: 'lateness-lop',
      name: 'Lateness & LOP Deduction Report',
      desc: 'Summary of qualifying late arrivals past grace period, calculated LOP days (late/3), and exact deduction amounts.',
      endpoint: '/reports/lateness-lop',
      icon: <Timer className="w-6 h-6 text-rose-600" />,
    },
    {
      id: 'salary-register',
      name: 'Monthly Salary Register',
      desc: 'Master payroll register with basic salary, attendance parts, collections, deductions, and net payouts.',
      endpoint: '/reports/salary-register',
      icon: <Banknote className="w-6 h-6 text-emerald-600" />,
    },
    {
      id: 'attendance',
      name: 'Attendance Log Report',
      desc: 'Complete daily punch times, work durations, and shift assignments across all departments.',
      endpoint: '/reports/attendance',
      icon: <Calendar className="w-6 h-6 text-teal-600" />,
    },
    {
      id: 'missing-punch',
      name: 'Missing Out-Punch Report',
      desc: 'Audit list of staff with check-in records but missing out-time punches for HR resolution.',
      endpoint: '/reports/missing-punch',
      icon: <AlertTriangle className="w-6 h-6 text-amber-600" />,
    },
    {
      id: 'overtime',
      name: 'Overtime & Excess Hours Report',
      desc: 'Detailed breakdown of overtime minutes and rates aggregated per department.',
      endpoint: '/reports/overtime',
      icon: <Clock className="w-6 h-6 text-purple-600" />,
    },
  ]

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Reports & Analytics Hub</h1>
          <p className="text-xs text-slate-500 mt-1">Generate official Excel spreadsheets and audit summaries for management and payroll records</p>
        </div>

        {/* Period Picker Filter */}
        <div className="bg-white p-2 px-3 rounded-xl border border-slate-200 shadow-2xs flex items-center gap-2">
          <Filter className="w-4 h-4 text-teal-600" />
          <span className="text-xs font-semibold text-slate-700">Period:</span>
          <select
            value={selectedMonth}
            onChange={(e) => setSelectedMonth(e.target.value)}
            className="h-8 px-2.5 rounded-md border border-slate-200 bg-slate-50 text-xs font-bold text-slate-800"
          >
            <option value="1">January</option>
            <option value="2">February</option>
            <option value="3">March</option>
            <option value="4">April</option>
            <option value="5">May</option>
            <option value="6">June</option>
            <option value="7">July</option>
            <option value="8">August</option>
            <option value="9">September</option>
            <option value="10">October</option>
            <option value="11">November</option>
            <option value="12">December</option>
          </select>
          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(e.target.value)}
            className="h-8 px-2.5 rounded-md border border-slate-200 bg-slate-50 text-xs font-bold text-slate-800"
          >
            <option value="2025">2025</option>
            <option value="2026">2026</option>
            <option value="2027">2027</option>
          </select>
        </div>
      </div>

      {/* Report Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {reports.map((r) => (
          <div key={r.id} className="bg-white p-6 rounded-xl border border-slate-200 space-y-4 shadow-xs hover:shadow-md transition-all">
            <div className="flex items-start gap-4">
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 shrink-0">{r.icon}</div>
              <div>
                <h3 className="text-sm font-bold text-slate-900">{r.name}</h3>
                <p className="text-xs text-slate-500 mt-1 leading-relaxed">{r.desc}</p>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100 flex justify-end">
              <Button
                onClick={() => handleExportExcel(r.id, r.endpoint)}
                disabled={downloading === r.id}
                className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2 shadow-xs"
              >
                <FileSpreadsheet className="w-4 h-4" />
                {downloading === r.id ? 'Exporting...' : 'Export Excel (.xlsx)'}
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
