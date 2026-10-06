'use client'

import { useEffect, useState, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { Banknote, Calculator, CheckCircle2, Download, FileText, Edit2, Loader2, Lock, Save, RefreshCw, Trash2, AlertTriangle } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'

const MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

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

interface PayrollRecordItem {
  id: number
  employee_id: number
  employee_name?: string
  employee_code?: string
  biometric_code?: string
  department?: string
  total_working_days: number
  present_days: number
  half_days?: number
  leave_days?: number
  off_duty_days?: number
  payable_days?: number
  salary_part?: number
  absent_days: number
  paid_leave_days?: number
  loss_of_pay_days?: number
  lop_days?: number
  lop_deduction?: number
  security_fund_deduction?: number
  collection?: number
  ot_hours?: number
  basic_salary: number
  ot_amount?: number
  gross_salary?: number
  total_deductions?: number
  net_salary?: number
  total_salary?: number
  status: string
  salary_verified?: boolean
  salary_source?: string
  is_manual_override?: boolean
}

interface UnverifiedEmployee {
  id?: number
  employee_id: string
  biometric_code?: string
  name: string
  current_salary?: number
  basic_salary?: number
}

interface LateArrivalItem {
  date: string
  in_time: string
  shift: string
  late_minutes: number
  excess_minutes: number
}

interface LatenessBreakdownData {
  employee_name?: string
  month?: number
  year?: number
  late_count?: number
  qualifying_late_days?: number
  grace_minutes?: number
  lop_days?: number
  per_day_salary?: number
  lop_deduction?: number
  late_arrivals?: LateArrivalItem[]
}

function PayrollContent() {
  const router = useRouter()
  const searchParams = useSearchParams()

  const currentSystemDate = new Date()
  const currentSystemYear = currentSystemDate.getFullYear()
  const currentSystemMonth = currentSystemDate.getMonth() + 1

  const initialYear = Number(searchParams.get('year')) || currentSystemYear
  const initialMonth = Number(searchParams.get('month')) || currentSystemMonth

  const [year, setYear] = useState<number>(initialYear)
  const [month, setMonth] = useState<number>(initialMonth)

  const [currentPeriod, setCurrentPeriod] = useState<PayrollPeriodItem | null>(null)
  const [records, setRecords] = useState<PayrollRecordItem[]>([])
  const [totalStaff, setTotalStaff] = useState<number>(0)
  const [loading, setLoading] = useState(false)
  const [calculating, setCalculating] = useState(false)
  const [finalizing, setFinalizing] = useState(false)

  // Unverified salaries block modal state
  const [unverifiedEmployees, setUnverifiedEmployees] = useState<UnverifiedEmployee[]>([])
  const [showUnverifiedModal, setShowUnverifiedModal] = useState(false)

  // Lateness breakdown modal state
  const [breakdownRecord, setBreakdownRecord] = useState<PayrollRecordItem | null>(null)
  const [breakdownLoading, setBreakdownLoading] = useState(false)
  const [breakdownData, setBreakdownData] = useState<LatenessBreakdownData | null>(null)

  // Edit dialog state for manual calculator input override
  const [editingRecord, setEditingRecord] = useState<PayrollRecordItem | null>(null)
  const [editPresent, setEditPresent] = useState<number>(0)
  const [editHalf, setEditHalf] = useState<number>(0)
  const [editLeave, setEditLeave] = useState<number>(0)
  const [editOffDuty, setEditOffDuty] = useState<number>(0)
  const [editLOP, setEditLOP] = useState<number>(0)
  const [editCollection, setEditCollection] = useState<number>(0)
  const [savingEdit, setSavingEdit] = useState(false)

  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const refresh = () => {
    setLoading(true)
    setRefreshTrigger((n) => n + 1)
  }

  const handleYearChange = (newYear: number) => {
    let newMonth = month
    if (newYear === currentSystemYear && month > currentSystemMonth) {
      newMonth = currentSystemMonth
    }
    setYear(newYear)
    setMonth(newMonth)
    router.replace(`/payroll?year=${newYear}&month=${newMonth}`)
  }

  const handleMonthChange = (newMonth: number) => {
    setMonth(newMonth)
    router.replace(`/payroll?year=${year}&month=${newMonth}`)
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
        const activeStaffCount = lookupRes.data.active_staff_count || 0
        setCurrentPeriod(period)

        if (period) {
          const recRes = await api.get(`/payroll/periods/${period.id}/records`, {
            params: { page_size: 200 },
          })
          if (active) {
            setRecords(recRes.data.items || [])
            setTotalStaff(recRes.data.total || (recRes.data.items || []).length || activeStaffCount)
          }
        } else {
          setRecords([])
          setTotalStaff(activeStaffCount)
        }
      } catch (err) {
        console.error(err)
        if (active) {
          setCurrentPeriod(null)
          setRecords([])
          setTotalStaff(0)
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
  }, [year, month, refreshTrigger])

  const openLatenessBreakdown = async (rec: PayrollRecordItem) => {
    setBreakdownRecord(rec)
    setBreakdownLoading(true)
    try {
      const res = await api.get(`/payroll/records/${rec.id}/lateness-breakdown`)
      setBreakdownData(res.data)
    } catch (err) {
      console.error(err)
      setBreakdownData(null)
    } finally {
      setBreakdownLoading(false)
    }
  }

  const handleCalculatePayroll = async () => {
    setCalculating(true)
    try {
      const res = await api.post('/payroll/periods/calculate', { year, month })
      if (res.data.period) {
        setCurrentPeriod(res.data.period)
        const recRes = await api.get(`/payroll/periods/${res.data.period.id}/records`, {
          params: { page_size: 200 },
        })
        setRecords(recRes.data.items || [])
        setTotalStaff(recRes.data.total || (recRes.data.items || []).length)
      }
      refresh()
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: string | { message?: string } } } })?.response
      const detail = resp?.data?.detail
      const msg = typeof detail === 'string' ? detail : (detail?.message || 'Failed to calculate payroll.')
      alert(msg)
    } finally {
      setCalculating(false)
    }
  }

  const handleFinalize = async () => {
    if (!currentPeriod) return
    if (!confirm('Are you sure you want to finalize and lock this payroll period?')) return
    setFinalizing(true)
    try {
      await api.post(`/payroll/periods/${currentPeriod.id}/finalize`)
      refresh()
    } catch (err: unknown) {
      const resp = (err as { response?: { data?: { detail?: { unverified_employees?: UnverifiedEmployee[]; message?: string } | string } } })?.response
      const detail = resp?.data?.detail
      if (detail && typeof detail === 'object' && Array.isArray(detail.unverified_employees)) {
        setUnverifiedEmployees(detail.unverified_employees)
        setShowUnverifiedModal(true)
      } else {
        const msg = typeof detail === 'string' ? detail : (detail?.message || 'Failed to finalize payroll.')
        alert(msg)
      }
    } finally {
      setFinalizing(false)
    }
  }

  const handleReopen = async () => {
    if (!currentPeriod) return
    if (!confirm('Are you sure you want to reopen this finalized payroll period?')) return
    try {
      await api.post(`/payroll/periods/${currentPeriod.id}/reopen`)
      refresh()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to reopen period.'
      alert(msg)
    }
  }

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

  const openEditModal = (rec: PayrollRecordItem) => {
    setEditingRecord(rec)
    setEditPresent(rec.present_days || 0)
    setEditHalf(rec.half_days || 0)
    setEditLeave(rec.leave_days || 0)
    setEditOffDuty(rec.off_duty_days || 0)
    setEditLOP(rec.lop_days || rec.loss_of_pay_days || 0)
    setEditCollection(rec.collection || 0)
  }

  const handleSaveEdit = async () => {
    if (!editingRecord) return
    setSavingEdit(true)
    try {
      await api.put(`/payroll/records/${editingRecord.id}`, {
        present_days: editPresent,
        half_days: editHalf,
        leave_days: editLeave,
        off_duty_days: editOffDuty,
        loss_of_pay_days: editLOP,
        collection: editCollection,
      })
      refresh()
      setEditingRecord(null)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to update payroll record.'
      alert(msg)
    } finally {
      setSavingEdit(false)
    }
  }

  const handleResetOverride = async () => {
    if (!editingRecord) return
    setSavingEdit(true)
    try {
      await api.put(`/payroll/records/${editingRecord.id}`, {
        is_manual_override: false,
      })
      refresh()
      setEditingRecord(null)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to reset manual override.'
      alert(msg)
    } finally {
      setSavingEdit(false)
    }
  }

  const isFinalized = currentPeriod?.status === 'FINALIZED'
  const currentMonthLabel = `${MONTH_NAMES[month]} ${year}`

  const baseSalaryPreview = editingRecord?.basic_salary || 0
  const daysInMonthPreview = new Date(year, month, 0).getDate()
  const perDayPreview = daysInMonthPreview > 0 ? baseSalaryPreview / daysInMonthPreview : 0
  const effectivePresentPreview = Math.min(editPresent, daysInMonthPreview)
  const effectiveLeavePreview = Math.min(editLeave, 3.0)
  const payableDaysPreview = Number((effectivePresentPreview + (editHalf * 0.5) + effectiveLeavePreview + editOffDuty).toFixed(2))
  const salaryPartPreview = Number(Math.min(payableDaysPreview * perDayPreview, baseSalaryPreview).toFixed(2))
  const lopDedPreview = Number(Math.min(editLOP * perDayPreview, salaryPartPreview).toFixed(2))
  const fundDedPreview = Number((editingRecord?.security_fund_deduction || 0).toFixed(2))
  const netSalaryPreview = Number((Math.max(0, salaryPartPreview + editCollection - (lopDedPreview + fundDedPreview))).toFixed(2))

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Monthly Payroll & Salary Calculator</h1>
            <span className="text-[11px] font-bold bg-teal-100 text-teal-800 px-2.5 py-0.5 rounded-full border border-teal-200">
              Formula + Lateness LOP Rule (3 Late = 1 LOP Day)
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Payable Days = Present + (Half × 0.5) + min(Leave, 3) + OffDuty | Deductions = LOP (floor(Late/3) × PerDay) + Savings Fund | Net = (Salary Part + Collection) − Deductions
          </p>
        </div>

        <div className="flex items-center gap-2">
          {currentPeriod && (
            <>
              {isFinalized ? (
                <Button
                  onClick={handleReopen}
                  variant="outline"
                  className="border-amber-300 hover:bg-amber-50 text-amber-800 text-xs font-semibold gap-1.5"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Reopen Period
                </Button>
              ) : (
                <>
                  <Button
                    onClick={handleCalculatePayroll}
                    disabled={calculating}
                    className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2 shadow-xs"
                  >
                    {calculating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
                    Recalculate
                  </Button>
                  <Button
                    onClick={handleFinalize}
                    disabled={finalizing}
                    variant="outline"
                    className="border-slate-300 hover:bg-slate-50 text-slate-700 text-xs font-semibold gap-1.5"
                  >
                    {finalizing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Lock className="w-3.5 h-3.5" />}
                    Finalize Period
                  </Button>
                </>
              )}
            </>
          )}
          {!currentPeriod && (
            <Button
              onClick={handleCalculatePayroll}
              disabled={calculating}
              className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2 shadow-xs"
            >
              {calculating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
              Calculate Payroll
            </Button>
          )}
        </div>
      </div>

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

          <div className="flex items-center">
            {currentPeriod ? (
              currentPeriod.status === 'FINALIZED' ? (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200">
                  <CheckCircle2 className="w-3 h-3 text-emerald-600" /> FINALIZED
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-[11px] font-bold bg-amber-100 text-amber-800 border border-amber-200">
                  DRAFT
                </span>
              )
            ) : (
              <span className="inline-flex items-center px-2.5 py-1 rounded-md text-[11px] font-medium bg-slate-100 text-slate-600 border border-slate-200">
                NOT CALCULATED
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-600">
          <span>Active Staff: <strong className="text-slate-900 font-bold">{totalStaff || records.length}</strong></span>
          <span>•</span>
        </div>
      </div>

      {/* Records Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-12 flex justify-center text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
          </div>
        ) : records.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[11px]">
                <tr>
                  <th className="p-3 pl-4">Staff Member</th>
                  <th className="p-3">Base Salary</th>
                  <th className="p-3 text-center">Present</th>
                  <th className="p-3 text-center">Half</th>
                  <th className="p-3 text-center">Leave</th>
                  <th className="p-3 text-center">Off Duty</th>
                  <th className="p-3 text-center bg-slate-100/60 text-slate-900 font-bold">Payable Days</th>
                  <th className="p-3 text-right">Salary Part</th>
                  <th className="p-3 text-center text-rose-700 font-bold bg-rose-50/40">LOP (Days & Ded)</th>
                  <th className="p-3 text-right text-amber-700 font-semibold">Savings Fund</th>
                  <th className="p-3 text-right text-emerald-700">Collection</th>
                  <th className="p-3 text-right bg-teal-50/50 text-teal-900 font-extrabold">Net Salary</th>
                  <th className="p-3 text-center pr-4">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {records.map((rec) => {
                  const lopDays = rec.lop_days || rec.loss_of_pay_days || 0
                  const lopDed = rec.lop_deduction || 0
                  const fundDed = rec.security_fund_deduction || 0
                  return (
                    <tr key={rec.id} className="hover:bg-slate-50/80">
                      <td className="p-3 pl-4">
                        <div className="font-bold text-slate-900 flex items-center gap-1.5">
                          {rec.employee_name || 'Staff'}
                          {(rec.salary_verified === false || rec.salary_source === 'PLACEHOLDER') && (
                            <span
                              className="px-1.5 py-0.5 rounded text-[9px] bg-amber-100 text-amber-800 font-bold border border-amber-300"
                              title="Salary unverified — please configure verified basic salary before finalization"
                            >
                              Unverified Salary
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono">
                          {rec.biometric_code ? `Bio: ${rec.biometric_code}` : rec.employee_code} • {rec.department || '—'}
                          {rec.is_manual_override && <span className="ml-1 text-amber-700 font-bold">(Overridden)</span>}
                        </div>
                      </td>
                      <td className="p-3 font-mono font-semibold text-slate-900">
                        ₹ {rec.basic_salary?.toLocaleString('en-IN')}
                      </td>
                      <td className="p-3 text-center font-mono font-bold text-emerald-700">{rec.present_days}</td>
                      <td className="p-3 text-center font-mono text-amber-700">{rec.half_days || 0}</td>
                      <td className="p-3 text-center font-mono text-blue-700">{rec.leave_days || 0}</td>
                      <td className="p-3 text-center font-mono text-purple-700">{rec.off_duty_days || 0}</td>
                      <td className="p-3 text-center font-mono font-extrabold bg-slate-100/60 text-slate-900">
                        {rec.payable_days}
                      </td>
                      <td className="p-3 text-right font-mono font-semibold text-slate-800">
                        ₹ {rec.salary_part?.toLocaleString('en-IN')}
                      </td>
                      <td
                        className={`p-3 text-center font-mono font-bold bg-rose-50/40 ${lopDays > 0 ? 'cursor-pointer hover:bg-rose-100/60 transition-colors' : ''}`}
                        onClick={() => lopDays > 0 && openLatenessBreakdown(rec)}
                        title={lopDays > 0 ? "Click to view late arrivals breakdown dates" : "No LOP deduction"}
                      >
                        {lopDays > 0 ? (
                          <div>
                            <span className="text-rose-700 block text-xs underline decoration-dotted decoration-rose-400">-{lopDays} d</span>
                            <span className="text-[10px] text-rose-600 block">-₹ {lopDed.toLocaleString('en-IN')}</span>
                          </div>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>
                      <td className="p-3 text-right font-mono text-amber-800 font-medium">
                        {fundDed > 0 ? `-₹ ${fundDed.toLocaleString('en-IN')}` : '—'}
                      </td>
                      <td className="p-3 text-right font-mono font-semibold text-emerald-700">
                        {(rec.collection ?? 0) > 0 ? `+₹ ${rec.collection?.toLocaleString('en-IN')}` : '₹ 0'}
                      </td>
                      <td className="p-3 text-right font-mono font-extrabold bg-teal-50/40 text-teal-700 text-sm">
                        ₹ {(rec.net_salary ?? rec.total_salary)?.toLocaleString('en-IN')}
                      </td>
                      <td className="p-3 text-center pr-4">
                        <div className="flex items-center justify-center gap-1.5">
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => openEditModal(rec)}
                            disabled={isFinalized}
                            className="h-7 px-2 text-slate-600 hover:text-teal-700 hover:bg-teal-50"
                          >
                            <Edit2 className="w-3.5 h-3.5 mr-1" />
                            Edit
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDownloadSlip(rec.id)}
                            className="h-7 px-2 text-xs text-teal-700 border-teal-200 hover:bg-teal-50"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-16 text-center text-slate-500 space-y-4">
            <div className="w-14 h-14 mx-auto rounded-full bg-teal-50 border border-teal-100 flex items-center justify-center text-teal-600">
              <Calculator className="w-7 h-7" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-800">No payroll calculated for {currentMonthLabel}</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto mt-1">
                Attendance and salary records have not been processed yet for this month. Click below to calculate in one step.
              </p>
            </div>
            <Button
              onClick={handleCalculatePayroll}
              disabled={calculating}
              className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2 shadow-sm"
            >
              {calculating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Calculator className="w-4 h-4" />}
              Calculate Payroll
            </Button>
          </div>
        )}
      </div>

      {/* Lateness Breakdown Modal */}
      <Dialog open={!!breakdownRecord} onOpenChange={(open) => !open && setBreakdownRecord(null)}>
        <DialogContent className="sm:max-w-xl">
          <DialogHeader>
            <DialogTitle className="text-base font-bold text-slate-900">
              Late Arrivals Breakdown — {breakdownRecord?.employee_name}
            </DialogTitle>
          </DialogHeader>

          {breakdownLoading ? (
            <div className="py-12 flex justify-center text-teal-600">
              <Loader2 className="w-6 h-6 animate-spin" />
            </div>
          ) : breakdownData ? (
            <div className="space-y-3 py-2 text-xs">
              <div className="p-3 bg-rose-50 rounded-lg border border-rose-200 flex items-center justify-between text-rose-950">
                <div>
                  <span className="text-xs font-semibold">Late Arrivals (&gt;{breakdownData?.grace_minutes ?? 5}m Grace): </span>
                  <strong className="text-sm font-bold text-rose-700">{breakdownData.qualifying_late_days} dates</strong>
                </div>
                <div>
                  <span className="text-xs font-semibold">LOP Days: </span>
                  <strong className="text-sm font-bold text-rose-700">{breakdownData.lop_days} days (₹{breakdownData.lop_deduction?.toLocaleString('en-IN')})</strong>
                </div>
              </div>

              <div className="max-h-72 overflow-y-auto border border-slate-200 rounded-lg">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold text-[11px] sticky top-0">
                    <tr>
                      <th className="p-2.5 pl-3">Date</th>
                      <th className="p-2.5">In-Time</th>
                      <th className="p-2.5">Shift</th>
                      <th className="p-2.5 text-right">Late Mins</th>
                      <th className="p-2.5 text-right pr-3 text-rose-700 font-bold">Past Grace</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                    {breakdownData.late_arrivals?.map((la: LateArrivalItem, i: number) => (
                      <tr key={i} className="hover:bg-slate-50/80">
                        <td className="p-2.5 pl-3 font-medium text-slate-900">{la.date}</td>
                        <td className="p-2.5 font-mono">{la.in_time}</td>
                        <td className="p-2.5 text-slate-600">{la.shift}</td>
                        <td className="p-2.5 text-right font-mono text-amber-700">{la.late_minutes}m</td>
                        <td className="p-2.5 text-right pr-3 font-mono font-bold text-rose-700">+{la.excess_minutes}m</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p className="text-xs text-slate-500 py-4">No qualifying late arrival details available.</p>
          )}

          <DialogFooter>
            <Button variant="outline" size="sm" onClick={() => setBreakdownRecord(null)} className="text-xs">
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Manual Calculator Edit Dialog */}
      <Dialog open={!!editingRecord} onOpenChange={(open) => !open && setEditingRecord(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold text-slate-900">
              Edit Salary & LOP Inputs — {editingRecord?.employee_name}
            </DialogTitle>
          </DialogHeader>

          {editingRecord && (
            <div className="space-y-4 py-2 text-xs">
              <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-500">Base Salary:</span>
                  <span className="font-bold text-slate-900 font-mono">₹ {baseSalaryPreview.toLocaleString('en-IN')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Per Day Rate ({daysInMonthPreview} days):</span>
                  <span className="font-mono text-slate-700">₹ {perDayPreview.toFixed(2)}</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-xs text-slate-700 font-semibold">Present Days</Label>
                  <Input
                    type="number"
                    step="0.5"
                    value={editPresent}
                    onChange={(e) => setEditPresent(Number(e.target.value))}
                    className="h-8 text-xs mt-1 font-mono"
                  />
                </div>
                <div>
                  <Label className="text-xs text-slate-700 font-semibold">Half Days (× 0.5)</Label>
                  <Input
                    type="number"
                    step="1"
                    value={editHalf}
                    onChange={(e) => setEditHalf(Number(e.target.value))}
                    className="h-8 text-xs mt-1 font-mono"
                  />
                </div>
                <div>
                  <Label className="text-xs text-slate-700 font-semibold">Leave Days (Max 3 Paid)</Label>
                  <Input
                    type="number"
                    step="1"
                    value={editLeave}
                    onChange={(e) => setEditLeave(Number(e.target.value))}
                    className="h-8 text-xs mt-1 font-mono"
                  />
                </div>
                <div>
                  <Label className="text-xs text-slate-700 font-semibold">Off Duty Days (Paid)</Label>
                  <Input
                    type="number"
                    step="1"
                    value={editOffDuty}
                    onChange={(e) => setEditOffDuty(Number(e.target.value))}
                    className="h-8 text-xs mt-1 font-mono"
                  />
                </div>
                <div className="col-span-2">
                  <Label className="text-xs text-rose-700 font-bold">Lateness LOP Days (Deducted from Pay)</Label>
                  <Input
                    type="number"
                    step="1"
                    value={editLOP}
                    onChange={(e) => setEditLOP(Number(e.target.value))}
                    className="h-8 text-xs mt-1 font-mono font-bold text-rose-700 border-rose-300 bg-rose-50/30"
                  />
                </div>
              </div>

              <div>
                <Label className="text-xs text-slate-700 font-semibold">Collection (₹ Added to Salary)</Label>
                <Input
                  type="number"
                  step="100"
                  value={editCollection}
                  onChange={(e) => setEditCollection(Number(e.target.value))}
                  className="h-8 text-xs mt-1 font-mono font-bold text-emerald-700"
                />
              </div>

              {/* Live Preview Box */}
              {(() => {
                const effPres = Math.min(editPresent, daysInMonthPreview)
                const effLeave = Math.min(editLeave, 3)
                const payDays = Number((effPres + editHalf * 0.5 + effLeave + editOffDuty).toFixed(2))
                const salPart = Number(Math.min(payDays * perDayPreview, baseSalaryPreview).toFixed(2))
                const lopDed = Number(Math.min(editLOP * perDayPreview, salPart).toFixed(2))
                const fundDed = Number((editingRecord.security_fund_deduction || 0).toFixed(2))
                const totDed = Number((lopDed + fundDed).toFixed(2))
                const netSal = Number((Math.max(0, salPart + editCollection - totDed)).toFixed(2))

                return (
                  <div className="p-3.5 bg-teal-50/70 rounded-lg border border-teal-200 space-y-1.5 text-teal-900">
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold">Payable Days:</span>
                      <span className="font-mono font-bold">{payDays} days</span>
                    </div>
                    <div className="flex justify-between items-center text-xs">
                      <span className="font-semibold">Salary Part:</span>
                      <span className="font-mono font-bold">₹ {salPart.toLocaleString('en-IN')}</span>
                    </div>
                    <div className="flex justify-between items-center text-xs text-rose-800">
                      <span className="font-semibold">Lateness LOP ({editLOP} days):</span>
                      <span className="font-mono font-bold">-₹ {lopDed.toLocaleString('en-IN')}</span>
                    </div>
                    {fundDed > 0 && (
                      <div className="flex justify-between items-center text-xs text-amber-800">
                        <span className="font-semibold">Savings Fund Deduction:</span>
                        <span className="font-mono font-bold">-₹ {fundDed.toLocaleString('en-IN')}</span>
                      </div>
                    )}
                    {editCollection > 0 && (
                      <div className="flex justify-between items-center text-xs text-emerald-800">
                        <span className="font-semibold">Collection:</span>
                        <span className="font-mono font-bold">+₹ {editCollection.toLocaleString('en-IN')}</span>
                      </div>
                    )}
                    <div className="flex justify-between items-center text-xs border-t border-teal-200 pt-1.5">
                      <span className="font-extrabold text-slate-900">Net Salary Payout:</span>
                      <span className="font-extrabold font-mono text-base text-teal-700">₹ {netSal.toLocaleString('en-IN')}</span>
                    </div>
                  </div>
                )
              })()}
            </div>
          )}

          <DialogFooter className="flex items-center justify-between gap-2 sm:justify-between">
            <div>
              {editingRecord?.is_manual_override && (
                <Button variant="outline" size="sm" onClick={handleResetOverride} disabled={savingEdit} className="text-xs text-amber-700 border-amber-300 hover:bg-amber-50">
                  Reset Override
                </Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditingRecord(null)} className="text-xs">
                Cancel
              </Button>
              <Button size="sm" onClick={handleSaveEdit} disabled={savingEdit} className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-1.5">
                {savingEdit ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                Save Override
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Unverified Salaries Block Modal */}
      {showUnverifiedModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-lg w-full p-6 space-y-4 shadow-xl border border-slate-200">
            <div className="flex items-center gap-2.5 text-amber-700">
              <AlertTriangle className="w-5 h-5 text-amber-600" />
              <h2 className="text-base font-bold text-slate-900">
                Unverified Salaries Block Finalization ({unverifiedEmployees.length})
              </h2>
            </div>
            <p className="text-xs text-slate-600">
              The following employees have unverified or placeholder basic salaries. Configure their verified salaries to finalize payroll:
            </p>

            <div className="max-h-64 overflow-y-auto border border-slate-200 rounded-lg">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="p-2.5 pl-3">Employee</th>
                    <th className="p-2.5">Current Salary</th>
                    <th className="p-2.5 text-right pr-3">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {unverifiedEmployees.map((emp) => (
                    <tr key={emp.id} className="hover:bg-slate-50/60">
                      <td className="p-2.5 pl-3">
                        <div className="font-bold text-slate-900">{emp.name}</div>
                        <div className="text-[10px] text-slate-500 font-mono">
                          {emp.employee_id} {emp.biometric_code ? `(Bio: ${emp.biometric_code})` : ''}
                        </div>
                      </td>
                      <td className="p-2.5 font-mono text-slate-700">
                        ₹ {emp.basic_salary?.toLocaleString('en-IN')}
                      </td>
                      <td className="p-2.5 text-right pr-3">
                        <Link
                          href={`/employees/${emp.id}/edit`}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-teal-700 bg-teal-50 hover:bg-teal-100 px-2.5 py-1 rounded border border-teal-200 transition-colors"
                        >
                          <Edit2 className="w-3 h-3" />
                          Edit Salary
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowUnverifiedModal(false)}
                className="text-xs h-8"
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default function PayrollPage() {
  return (
    <Suspense fallback={<div className="p-12 flex justify-center text-teal-600"><Loader2 className="w-6 h-6 animate-spin" /></div>}>
      <PayrollContent />
    </Suspense>
  )
}
