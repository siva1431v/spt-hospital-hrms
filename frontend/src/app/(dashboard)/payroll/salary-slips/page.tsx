'use client'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { FileText, Download, Search, Loader2, Calculator } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { PayrollRecord } from '@/types'

const MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

function SalarySlipsContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const currentSystemDate = new Date()
  const currentSystemYear = currentSystemDate.getFullYear()
  const currentSystemMonth = currentSystemDate.getMonth() + 1

  const initialYear = Number(searchParams.get('year')) || 2026
  const initialMonth = Number(searchParams.get('month')) || 8

interface PayrollPeriodItem {
  id: number
  period_name: string
  year: number
  month: number
  status: string
  total_employees?: number
  total_gross_amount?: number
  total_net_amount?: number
}

  const [year, setYear] = useState<number>(initialYear)
  const [month, setMonth] = useState<number>(initialMonth)

  const [currentPeriod, setCurrentPeriod] = useState<PayrollPeriodItem | null>(null)
  const [records, setRecords] = useState<PayrollRecord[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')

  const handleYearChange = (newYear: number) => {
    let newMonth = month
    if (newYear === currentSystemYear && month > currentSystemMonth) {
      newMonth = currentSystemMonth
    }
    setYear(newYear)
    setMonth(newMonth)
    router.replace(`/payroll/salary-slips?year=${newYear}&month=${newMonth}`)
  }

  const handleMonthChange = (newMonth: number) => {
    setMonth(newMonth)
    router.replace(`/payroll/salary-slips?year=${year}&month=${newMonth}`)
  }

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const lookupRes = await api.get('/payroll/periods/lookup', {
          params: { year, month },
        })
        if (!active) return
        const period = lookupRes.data.period
        setCurrentPeriod(period)

        if (period) {
          const res = await api.get(`/payroll/periods/${period.id}/records`, {
            params: { page_size: 200 },
          })
          if (active) {
            setRecords(res.data.items || [])
            setTotalCount(res.data.total || (res.data.items || []).length)
          }
        } else {
          setRecords([])
          setTotalCount(0)
        }
      } catch (err) {
        console.error(err)
        if (active) {
          setCurrentPeriod(null)
          setRecords([])
          setTotalCount(0)
        }
      } finally {
        if (active) {
          setLoading(false)
        }
      }
    }
    load()
    return () => {
      active = false
    }
  }, [year, month])

  const handleDownloadSlip = async (recordId: number) => {
    try {
      const response = await api.get(`/salary-slips/${recordId}`, {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `Salary_Slip_${recordId}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
    } catch (err) {
      alert('Failed to download salary slip PDF.')
    }
  }

  const filteredRecords = records.filter((r) => {
    if (!search) return true
    const term = search.toLowerCase()
    return (
      r.employee_name?.toLowerCase().includes(term) ||
      r.employee_code?.toLowerCase().includes(term) ||
      r.department?.toLowerCase().includes(term)
    )
  })

  const currentMonthLabel = `${MONTH_NAMES[month]} ${year}`

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200/80 pb-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-600 flex items-center justify-center font-bold">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Salary Slips Directory</h1>
            <p className="text-xs text-slate-500 mt-0.5">Generate and download official PDF salary slips per employee</p>
          </div>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-700">Month & Year:</span>
            <select
              value={month}
              onChange={(e) => handleMonthChange(Number(e.target.value))}
              className="h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 font-semibold"
            >
              {MONTH_NAMES.slice(1).map((mName, idx) => {
                const mNum = idx + 1
                const isFuture = year > currentSystemYear || (year === currentSystemYear && mNum > currentSystemMonth)
                return (
                  <option key={mNum} value={mNum} disabled={isFuture}>
                    {mName} {isFuture ? '(Future)' : ''}
                  </option>
                )
              })}
            </select>
            <select
              value={year}
              onChange={(e) => handleYearChange(Number(e.target.value))}
              className="h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 font-semibold"
            >
              {[2024, 2025, 2026, 2027, 2028].filter(y => y <= currentSystemYear).map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter staff by name or code..."
              className="text-xs h-9 pl-8 w-48 sm:w-60"
            >
            </Input>
          </div>
        </div>

        <div className="text-xs text-slate-500 font-medium">
          Total Slips: <strong className="text-slate-900">{search ? filteredRecords.length : totalCount}</strong>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-12 flex justify-center text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
          </div>
        ) : filteredRecords.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[11px]">
                <tr>
                  <th className="p-3.5 pl-5">Emp Code</th>
                  <th className="p-3.5">Employee Name</th>
                  <th className="p-3.5">Department</th>
                  <th className="p-3.5">Basic Salary</th>
                  <th className="p-3.5">Gross Salary</th>
                  <th className="p-3.5">Deductions</th>
                  <th className="p-3.5">Net Salary</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5 text-right pr-5">Download Slip</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {filteredRecords.map((rec) => (
                  <tr key={rec.id} className="hover:bg-slate-50/80">
                    <td className="p-3.5 pl-5 font-mono text-slate-900 font-bold">{rec.employee_code || rec.biometric_code || rec.employee_id}</td>
                    <td className="p-3.5 font-semibold text-slate-900">{rec.employee_name || 'Staff'}</td>
                    <td className="p-3.5 text-slate-600">{rec.department || rec.department_name || '—'}</td>
                    <td className="p-3.5 font-mono font-medium">₹ {(Number(rec.basic_salary) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td className="p-3.5 font-mono font-semibold text-slate-900">₹ {(Number(rec.gross_salary ?? rec.basic_salary) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td className="p-3.5 font-mono text-rose-700 font-medium">₹ {(Number(rec.total_deductions ?? rec.deductions) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td className="p-3.5 font-mono font-extrabold text-teal-700 text-sm">₹ {(Number(rec.net_salary ?? rec.total_salary) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td className="p-3.5">
                      {rec.status === 'FINALIZED' ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">FINALIZED</span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">{rec.status}</span>
                      )}
                    </td>
                    <td className="p-3.5 text-right pr-5">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleDownloadSlip(rec.id)}
                        className="h-7 px-2.5 text-xs text-teal-700 border-teal-200 hover:bg-teal-50 gap-1.5"
                      >
                        <Download className="w-3.5 h-3.5" />
                        PDF Slip
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-16 text-center text-slate-500 space-y-4">
            <div className="w-14 h-14 mx-auto rounded-full bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-600">
              <FileText className="w-7 h-7" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-800">No salary slips found for {currentMonthLabel}</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
                Payroll has not been calculated for this month yet. Process payroll to generate official salary slips.
              </p>
            </div>
            <Link href={`/payroll?year=${year}&month=${month}`}>
              <Button className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2 shadow-sm">
                <Calculator className="w-4 h-4" />
                Go to Payroll & Calculate
              </Button>
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}

export default function SalarySlipsPage() {
  return (
    <Suspense fallback={<div className="p-12 flex justify-center text-teal-600"><Loader2 className="w-6 h-6 animate-spin" /></div>}>
      <SalarySlipsContent />
    </Suspense>
  )
}
