'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ArrowRight,
  ShieldAlert,
  UserCheck,
  UserPlus,
  UserX,
  ExternalLink,
  Calculator,
  Calendar,
  Layers,
  HelpCircle,
} from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Employee, Department } from '@/types'

interface PreviewRecord {
  attendance_date?: string
  employee_code?: string
  employee_name?: string
  department_name?: string
  in_time?: string
  out_time?: string
  status?: string
  is_unknown_employee?: boolean
  is_unknown_department?: boolean
  is_duplicate?: boolean
  errors?: string[]
}

interface MonthlyAggregatePreview {
  employee_code: string
  employee_name: string
  department_name: string
  present_count: number
  absent_count: number
  late_by_days: number
  total_work_duration?: string
  total_ot?: string
}

export interface ReviewRowItem {
  company: string
  employee_code: string
  employee_name: string
  pdf_department?: string
  status: 'MATCHED' | 'NAME_MISMATCH' | 'NEW_EMPLOYEE' | 'DUPLICATE_SUSPECT' | string
  default_action?: 'link' | 'create' | 'ignore'
  action?: 'link' | 'create' | 'ignore'
  suggested_action?: 'link' | 'create' | 'ignore'
  save_as_alias?: boolean
  matched_employee_id?: number | null
  mapped_employee_id?: number | null
  matched_employee_name?: string | null
  mapped_employee_name?: string | null
  summary?: {
    P?: number
    A?: number
    L?: number
    H?: number
    HP?: number
    WO?: number
    WOP?: number
    NO_DATA?: number
  }
  computed_totals?: { [code: string]: number }
  printed_totals?: { [code: string]: number }
  checksum_valid?: boolean
  checksum_errors?: string[]
}

interface ImportPreviewData {
  session_token?: string
  _temp_path?: string
  report_type?: string
  company?: string
  company_name?: string
  date_range_start?: string
  date_range_end?: string
  period_year?: number
  period_month?: number
  period_name?: string
  is_payroll_finalized?: boolean
  payroll_finalized_reason?: string
  attendance_already_exists?: boolean
  existing_attendance_count?: number
  existing_attendance_message?: string
  review_rows?: ReviewRowItem[]
  is_duplicate_file?: boolean
  existing_import?: {
    id: number
    filename: string
    imported_at?: string
    records_imported?: number
    records_duplicate?: number
    status?: string
  }
  unknown_employee_codes?: string[]
  unknown_departments?: string[]
  unknown_department_names?: string[]
  unmapped_shift_codes?: string[]
  records?: PreviewRecord[]
  monthly_aggregates?: MonthlyAggregatePreview[]
  statistics?: {
    total_records?: number
    records_present?: number
    records_absent?: number
    records_incomplete?: number
    records_overnight?: number
    duplicates?: number
    duplicate?: number
    unknown_employees?: number
    errors?: number
    warnings?: number
  }
}

interface ImportSummaryData {
  import_id?: number
  imported?: number
  updated?: number
  skipped?: number
  duplicates?: number
  errors?: number
  status?: string
}

interface ReviewActionState {
  action: 'link' | 'create' | 'ignore'
  employee_id: number | null
  save_as_alias: boolean
}

export default function ImportPdfWizardPage() {
  const router = useRouter()
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewData, setPreviewData] = useState<ImportPreviewData | null>(null)
  const [sessionToken, setSessionToken] = useState<string | null>(null)

  const [uploading, setUploading] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [calculatingPayroll, setCalculatingPayroll] = useState(false)
  const [duplicateHandling, setDuplicateHandling] = useState<'SKIP' | 'OVERWRITE'>('SKIP')
  const [importSummary, setImportSummary] = useState<ImportSummaryData | null>(null)

  const [employees, setEmployees] = useState<Employee[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [employeeMappings, setEmployeeMappings] = useState<{ [code: string]: string }>({})
  const [departmentMappings, setDepartmentMappings] = useState<{ [name: string]: string }>({})

  // Review table actions for basic status reports
  const [reviewActions, setReviewActions] = useState<{ [key: string]: ReviewActionState }>({})
  const [reviewFilter, setReviewFilter] = useState<'ALL' | 'MATCHED' | 'NAME_MISMATCH' | 'NEW_EMPLOYEE' | 'DUPLICATE_SUSPECT'>('ALL')

  // Step 1: File selection
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0])
    }
  }

  // Step 2: Upload & Parse PDF Preview
  const handleUploadPreview = async () => {
    if (!selectedFile) return
    setUploading(true)
    setStep(2)

    try {
      const formData = new FormData()
      formData.append('file', selectedFile)

      const response = await api.post('/attendance/import/preview', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })

      // Fetch active employees and departments
      const [empRes, deptRes] = await Promise.all([
        api.get('/employees?page_size=1000'),
        api.get('/departments?is_active=true'),
      ])

      setEmployees(empRes.data.items || [])
      setDepartments(deptRes.data.items || [])

      const data: ImportPreviewData = response.data
      setPreviewData(data)
      setSessionToken(data.session_token || data._temp_path || 'valid')

      // Initialize reviewActions if review_rows present
      if (data.review_rows && data.review_rows.length > 0) {
        const initialMap: { [key: string]: ReviewActionState } = {}
        data.review_rows.forEach((row) => {
          const key = `${row.company}_${row.employee_code}`
          const act = (row.default_action || row.action || row.suggested_action || 'link') as 'link' | 'create' | 'ignore'
          initialMap[key] = {
            action: act,
            employee_id: row.matched_employee_id ?? row.mapped_employee_id ?? null,
            save_as_alias: Boolean(row.save_as_alias),
          }
        })
        setReviewActions(initialMap)
      }

      if (data.statistics?.total_records === 0 && (!data.review_rows || data.review_rows.length === 0)) {
        alert(
          'Warning: The eSSL PDF parser extracted 0 attendance records from this file. Please verify that the PDF is a valid eSSL attendance report.'
        )
      }

      setStep(3)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || 'Failed to parse attendance PDF report.')
      setStep(1)
    } finally {
      setUploading(false)
    }
  }

  // Update a single row's action
  const updateReviewAction = (key: string, updates: Partial<ReviewActionState>) => {
    setReviewActions((prev) => ({
      ...prev,
      [key]: {
        ...(prev[key] || { action: 'link', employee_id: null, save_as_alias: false }),
        ...updates,
      },
    }))
  }

  // Step 4: Commit Import
  const handleConfirmCommit = async () => {
    if (!previewData) return
    if (previewData.is_payroll_finalized) {
      alert(`Cannot import attendance: Payroll for ${previewData.period_name || 'this period'} is already finalized.`)
      return
    }

    setCommitting(true)
    setStep(4)

    try {
      // Serialize review actions
      const review_actions = (previewData.review_rows || []).map((row) => {
        const key = `${row.company}_${row.employee_code}`
        const current = reviewActions[key] || {
          action: row.default_action,
          employee_id: row.matched_employee_id,
          save_as_alias: row.save_as_alias,
        }
        return {
          company: row.company,
          employee_code: row.employee_code,
          action: current.action,
          employee_id: current.employee_id,
          save_as_alias: current.save_as_alias,
        }
      })

      const payload = {
        ...previewData,
        session_token: sessionToken || previewData.session_token,
        duplicate_action: duplicateHandling.toLowerCase(),
        employee_mappings: employeeMappings,
        department_mappings: departmentMappings,
        review_actions: review_actions,
      }
      const response = await api.post('/attendance/import/commit', payload)

      setImportSummary(response.data)
      setStep(5)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || 'Failed to commit attendance records.')
      setStep(3)
    } finally {
      setCommitting(false)
    }
  }

  // Calculate payroll on success
  const handleCalculatePayroll = async () => {
    if (!previewData?.period_year || !previewData?.period_month) {
      router.push('/payroll')
      return
    }
    setCalculatingPayroll(true)
    try {
      await api.post('/payroll/periods/calculate', {
        year: previewData.period_year,
        month: previewData.period_month,
      })
      router.push(`/payroll?year=${previewData.period_year}&month=${previewData.period_month}`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || 'Payroll calculated or redirected.')
      router.push(`/payroll?year=${previewData.period_year}&month=${previewData.period_month}`)
    } finally {
      setCalculatingPayroll(false)
    }
  }

  // Filtered review rows
  const filteredReviewRows = (previewData?.review_rows || []).filter((row) => {
    if (reviewFilter === 'ALL') return true
    return row.status === reviewFilter
  })

  const reviewCounts = {
    all: previewData?.review_rows?.length || 0,
    matched: previewData?.review_rows?.filter((r) => r.status === 'MATCHED').length || 0,
    mismatch: previewData?.review_rows?.filter((r) => r.status === 'NAME_MISMATCH').length || 0,
    newStaff: previewData?.review_rows?.filter((r) => r.status === 'NEW_EMPLOYEE').length || 0,
    dups: previewData?.review_rows?.filter((r) => r.status === 'DUPLICATE_SUSPECT').length || 0,
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Page Title */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">eSSL PDF Attendance Import Wizard</h1>
          <p className="text-xs text-slate-500 mt-1">
            Upload hospital eSSL biometric PDF attendance reports (Monthly Status Report or Daily Punch Detail)
          </p>
        </div>
        <Link
          href="/docs/monthly-import"
          className="inline-flex items-center gap-1.5 text-xs text-teal-700 hover:text-teal-800 font-semibold bg-teal-50 px-3 py-1.5 rounded-lg border border-teal-200"
        >
          <HelpCircle className="w-3.5 h-3.5" />
          Import Guide & FAQs
        </Link>
      </div>

      {/* Stepper Progress */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
        {[
          { num: 1, label: 'Upload PDF' },
          { num: 2, label: 'Parsing' },
          { num: 3, label: 'Review & Verify' },
          { num: 4, label: 'Committing' },
          { num: 5, label: 'Import Complete' },
        ].map((s, idx) => (
          <div key={s.num} className="flex items-center gap-2">
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${
                step === s.num
                  ? 'bg-teal-600 text-white shadow-xs'
                  : step > s.num
                  ? 'bg-emerald-500 text-white'
                  : 'bg-slate-100 text-slate-400'
              }`}
            >
              {step > s.num ? <CheckCircle2 className="w-4 h-4" /> : s.num}
            </div>
            <span
              className={`text-xs font-semibold hidden sm:inline ${
                step === s.num ? 'text-slate-900' : 'text-slate-400'
              }`}
            >
              {s.label}
            </span>
            {idx < 4 && <div className="h-[1px] w-6 bg-slate-200 mx-1 hidden md:block" />}
          </div>
        ))}
      </div>

      {/* STEP 1: Upload File */}
      {step === 1 && (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-xs text-center space-y-6">
          <div className="max-w-md mx-auto border-2 border-dashed border-slate-200 hover:border-teal-500 rounded-2xl p-8 bg-slate-50/50 transition-all cursor-pointer">
            <input
              type="file"
              accept=".pdf"
              onChange={handleFileChange}
              className="hidden"
              id="pdf-upload-input"
            />
            <label htmlFor="pdf-upload-input" className="cursor-pointer space-y-3 block">
              <div className="w-12 h-12 rounded-full bg-teal-100 text-teal-700 flex items-center justify-center mx-auto">
                <Upload className="w-6 h-6" />
              </div>
              <div>
                <p className="text-sm font-bold text-slate-900">
                  {selectedFile ? selectedFile.name : 'Click to select eSSL Attendance PDF'}
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Supports eSSL standard Monthly Status Reports and Daily Punch Log PDFs (up to 50MB)
                </p>
              </div>
            </label>
          </div>

          {selectedFile && (
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-teal-50 text-teal-800 text-xs font-semibold border border-teal-200">
              <FileText className="w-4 h-4" />
              <span>Selected: {selectedFile.name} ({Math.round(selectedFile.size / 1024)} KB)</span>
            </div>
          )}

          <div className="pt-4 border-t border-slate-100 flex justify-end">
            <Button
              onClick={handleUploadPreview}
              disabled={!selectedFile || uploading}
              className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-6 h-10 shadow-md shadow-teal-600/20"
            >
              Parse PDF & Preview Import
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
        </div>
      )}

      {/* STEP 2: Parsing Spinner */}
      {step === 2 && (
        <div className="bg-white p-16 rounded-xl border border-slate-200 shadow-xs text-center space-y-4">
          <Loader2 className="w-10 h-10 text-teal-600 animate-spin mx-auto" />
          <h2 className="text-base font-bold text-slate-900">Analyzing eSSL PDF Report Structure...</h2>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Detecting period date range from header, mapping coordinate columns, computing row checksums, and matching staff biometric codes.
          </p>
        </div>
      )}

      {/* STEP 3: Preview & Record Validation */}
      {step === 3 && previewData && (
        <div className="space-y-6">
          {/* Month Detection Banner */}
          {previewData.period_name && (
            <div className="p-4 bg-teal-50/80 rounded-xl border border-teal-200 flex items-start gap-3 text-xs">
              <Calendar className="w-5 h-5 text-teal-700 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-teal-900 text-sm">Detected PDF Period: {previewData.period_name}</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-200/80 text-teal-900">
                    Header Source of Truth
                  </span>
                </div>
                <p className="text-teal-800">
                  Extracted date range: <strong>{previewData.date_range_start}</strong> to <strong>{previewData.date_range_end}</strong>.
                  All attendance records and payroll calculations will be linked to <strong>{previewData.period_name}</strong> regardless of the current system month.
                </p>
              </div>
            </div>
          )}

          {/* Finalized Period Blocker Warning */}
          {previewData.is_payroll_finalized && (
            <div className="p-4 bg-rose-50 rounded-xl border border-rose-200 flex items-start gap-3 text-xs text-rose-900">
              <ShieldAlert className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <span className="font-bold text-sm">Import Blocked — Payroll Finalized</span>
                <p className="text-rose-800">
                  {previewData.payroll_finalized_reason ||
                    `The payroll period for ${previewData.period_name} has already been locked and finalized. Attendance records cannot be overwritten for finalized payroll.`}
                </p>
              </div>
            </div>
          )}

          {/* Existing Attendance Alert */}
          {previewData.attendance_already_exists && !previewData.is_payroll_finalized && (
            <div className="p-4 bg-amber-50 rounded-xl border border-amber-200 flex items-start gap-3 text-xs text-amber-900">
              <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <span className="font-bold text-sm">Existing Attendance Records Detected</span>
                <p className="text-amber-800">
                  {previewData.existing_attendance_message ||
                    `Found ${previewData.existing_attendance_count} existing attendance records for ${previewData.period_name}. Proceeding will cleanly replace them for this period without creating duplicates.`}
                </p>
              </div>
            </div>
          )}

          {/* Metadata Card */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Report Metadata & Detection</h2>
              {previewData.report_type && (
                <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-indigo-50 text-indigo-800 text-xs font-bold border border-indigo-200">
                  <Layers className="w-3.5 h-3.5" />
                  Format: {previewData.report_type}
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-slate-50 p-4 rounded-lg border border-slate-100 text-xs">
              <div>
                <span className="text-slate-400 font-medium">Company Name:</span>
                <p className="font-semibold text-slate-900">{previewData.company_name || 'SPT Hospital'}</p>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Period:</span>
                <p className="font-semibold text-slate-900">
                  {previewData.period_name || `${previewData.date_range_start} to ${previewData.date_range_end}`}
                </p>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Staff Rows Detected:</span>
                <p className="font-semibold text-teal-700 text-sm">
                  {previewData.review_rows?.length || previewData.statistics?.total_records || 0}
                </p>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Punch Times Availability:</span>
                <p className="font-semibold text-slate-700 text-xs mt-0.5">
                  {previewData.report_type?.includes('Monthly Status Report')
                    ? 'Status Codes (No punch times)'
                    : 'Punch In/Out Times Available'}
                </p>
              </div>
            </div>
          </div>

          {/* STEP 3 REVIEW SCREEN: Biometric Code Review Table */}
          {previewData.review_rows && previewData.review_rows.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden space-y-4 p-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 pb-3">
                <div>
                  <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
                    <UserCheck className="w-4 h-4 text-teal-600" />
                    Biometric Code Matching & Review Screen ({previewData.review_rows.length} Staff)
                  </h2>
                  <p className="text-[11px] text-slate-500 mt-0.5">
                    Review how PDF biometric rows map to employee master records. Department source of truth is always the employee master.
                  </p>
                </div>

                {/* Status Filter Badges */}
                <div className="flex flex-wrap gap-1.5 text-xs">
                  <button
                    onClick={() => setReviewFilter('ALL')}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                      reviewFilter === 'ALL'
                        ? 'bg-slate-800 text-white'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    All ({reviewCounts.all})
                  </button>
                  <button
                    onClick={() => setReviewFilter('MATCHED')}
                    className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                      reviewFilter === 'MATCHED'
                        ? 'bg-emerald-600 text-white'
                        : 'bg-emerald-50 text-emerald-800 hover:bg-emerald-100'
                    }`}
                  >
                    Matched ({reviewCounts.matched})
                  </button>
                  {reviewCounts.mismatch > 0 && (
                    <button
                      onClick={() => setReviewFilter('NAME_MISMATCH')}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                        reviewFilter === 'NAME_MISMATCH'
                          ? 'bg-amber-600 text-white'
                          : 'bg-amber-50 text-amber-800 hover:bg-amber-100'
                      }`}
                    >
                      Mismatches ({reviewCounts.mismatch})
                    </button>
                  )}
                  {reviewCounts.newStaff > 0 && (
                    <button
                      onClick={() => setReviewFilter('NEW_EMPLOYEE')}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                        reviewFilter === 'NEW_EMPLOYEE'
                          ? 'bg-sky-600 text-white'
                          : 'bg-sky-50 text-sky-800 hover:bg-sky-100'
                      }`}
                    >
                      New Staff ({reviewCounts.newStaff})
                    </button>
                  )}
                  {reviewCounts.dups > 0 && (
                    <button
                      onClick={() => setReviewFilter('DUPLICATE_SUSPECT')}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                        reviewFilter === 'DUPLICATE_SUSPECT'
                          ? 'bg-rose-600 text-white'
                          : 'bg-rose-50 text-rose-800 hover:bg-rose-100'
                      }`}
                    >
                      Duplicate Suspects ({reviewCounts.dups})
                    </button>
                  )}
                </div>
              </div>

              {/* Review Rows Table */}
              <div className="max-h-[28rem] overflow-y-auto border border-slate-200 rounded-lg">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px] sticky top-0 z-10">
                    <tr>
                      <th className="p-2.5">Device & Code</th>
                      <th className="p-2.5">PDF Employee</th>
                      <th className="p-2.5">Status</th>
                      <th className="p-2.5">Attendance Counts</th>
                      <th className="p-2.5">Action</th>
                      <th className="p-2.5 text-center">Save Alias</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-[11px]">
                    {filteredReviewRows.map((row) => {
                      const key = `${row.company}_${row.employee_code}`
                      const defaultAct = (row.default_action || row.action || row.suggested_action || 'link') as 'link' | 'create' | 'ignore'
                      const currentAction = reviewActions[key] || {
                        action: defaultAct,
                        employee_id: row.matched_employee_id ?? row.mapped_employee_id ?? null,
                        save_as_alias: Boolean(row.save_as_alias),
                      }

                      const summary = row.summary || row.computed_totals || {}
                      const pCount = summary.P ?? 0
                      const aCount = summary.A ?? 0
                      const hpCount = summary.HP ?? 0
                      const lCount = summary.L ?? 0
                      const hCount = summary.H ?? 0
                      const woCount = summary.WO ?? 0
                      const wopCount = summary.WOP ?? 0
                      const noDataCount = summary.NO_DATA ?? 0
                      const matchedEmpName = row.matched_employee_name || row.mapped_employee_name || 'Staff'

                      let statusBadge = (
                        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          Matched
                        </span>
                      )

                      if (row.status === 'NAME_MISMATCH') {
                        statusBadge = (
                          <div className="space-y-0.5">
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
                              Name Mismatch
                            </span>
                            <div className="text-[10px] text-amber-700">Master: {matchedEmpName}</div>
                          </div>
                        )
                      } else if (row.status === 'NEW_EMPLOYEE') {
                        statusBadge = (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-50 text-sky-800 border border-sky-200">
                            New Employee
                          </span>
                        )
                      } else if (row.status === 'DUPLICATE_SUSPECT') {
                        statusBadge = (
                          <div className="space-y-0.5">
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-50 text-rose-800 border border-rose-200">
                              Duplicate Suspect
                            </span>
                            <div className="text-[10px] text-rose-700">Old Bio all-absent duplicate</div>
                          </div>
                        )
                      }

                      const rowBg =
                        row.status === 'DUPLICATE_SUSPECT'
                          ? 'bg-rose-50/30'
                          : row.status === 'NAME_MISMATCH'
                          ? 'bg-amber-50/20'
                          : row.status === 'NEW_EMPLOYEE'
                          ? 'bg-sky-50/20'
                          : 'hover:bg-slate-50/60'

                      return (
                        <tr key={key} className={rowBg}>
                          <td className="p-2.5">
                            <div className="flex items-center gap-1.5 font-mono font-bold text-slate-900">
                              <span
                                className={`px-1.5 py-0.5 rounded text-[10px] font-sans ${
                                  row.company === 'Old Bio'
                                    ? 'bg-purple-100 text-purple-800'
                                    : 'bg-teal-100 text-teal-800'
                                }`}
                              >
                                {row.company}
                              </span>
                              #{row.employee_code}
                            </div>
                          </td>

                          <td className="p-2.5">
                            <div className="font-semibold text-slate-900">{row.employee_name}</div>
                            <div className="text-[10px] text-slate-400">PDF Dept: {row.pdf_department || '—'}</div>
                          </td>

                          <td className="p-2.5">{statusBadge}</td>

                          <td className="p-2.5 font-mono text-[10px]">
                            <div className="flex items-center gap-1.5">
                              <span className="text-emerald-700 font-bold">P:{pCount}</span>
                              <span className="text-rose-600 font-bold">A:{aCount}</span>
                              {hpCount > 0 && <span className="text-amber-700">HP:{hpCount}</span>}
                              {lCount > 0 && <span className="text-blue-700">L:{lCount}</span>}
                              {hCount > 0 && <span className="text-purple-700">H:{hCount}</span>}
                              {woCount > 0 && <span className="text-slate-600">WO:{woCount}</span>}
                              {wopCount > 0 && <span className="text-teal-700">WOP:{wopCount}</span>}
                              {noDataCount > 0 && (
                                <span className="text-slate-400">NoData:{noDataCount}</span>
                              )}
                            </div>
                            {row.checksum_errors && row.checksum_errors.length > 0 && (
                              <div className="text-[9px] text-rose-600 mt-0.5">{row.checksum_errors.join('; ')}</div>
                            )}
                          </td>

                          <td className="p-2.5">
                            <div className="space-y-1">
                              <select
                                value={currentAction.action}
                                onChange={(e) =>
                                  updateReviewAction(key, {
                                    action: e.target.value as 'link' | 'create' | 'ignore',
                                  })
                                }
                                className="h-7 text-xs bg-white border border-slate-200 rounded px-1.5 w-full"
                              >
                                <option value="link">Link to Employee</option>
                                <option value="create">Create New Employee</option>
                                <option value="ignore">Ignore Row</option>
                              </select>

                              {currentAction.action === 'link' && (
                                <select
                                  value={currentAction.employee_id || ''}
                                  onChange={(e) =>
                                    updateReviewAction(key, {
                                      employee_id: e.target.value ? Number(e.target.value) : null,
                                    })
                                  }
                                  className="h-7 text-[11px] bg-slate-50 border border-slate-200 rounded px-1.5 w-full"
                                >
                                  <option value="">-- Choose Employee --</option>
                                  {employees.map((emp) => (
                                    <option key={emp.id} value={emp.id}>
                                      {emp.full_name} ({emp.biometric_code || emp.employee_id})
                                    </option>
                                  ))}
                                </select>
                              )}
                            </div>
                          </td>

                          <td className="p-2.5 text-center">
                            <input
                              type="checkbox"
                              checked={currentAction.save_as_alias}
                              onChange={(e) =>
                                updateReviewAction(key, {
                                  save_as_alias: e.target.checked,
                                })
                              }
                              title="Save as alias in device_code_aliases for automatic resolution in future months"
                              className="rounded text-teal-600"
                            />
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Legacy Unmapped Sections for Punch Detail Reports */}
          {((previewData.unknown_employee_codes && previewData.unknown_employee_codes.length > 0) ||
            (previewData.unknown_department_names && previewData.unknown_department_names.length > 0)) &&
            (!previewData.review_rows || previewData.review_rows.length === 0) && (
              <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-6">
                <h2 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2 uppercase tracking-wider">
                  Review Mappings & Resolve Conflicts
                </h2>

                {previewData.unknown_employee_codes && previewData.unknown_employee_codes.length > 0 && (
                  <div className="space-y-3">
                    <h3 className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-rose-500" />
                      Unmapped Employee Biometric Codes ({previewData.unknown_employee_codes.length})
                    </h3>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {previewData.unknown_employee_codes.map((code: string) => {
                        const matchingRecord = previewData.records?.find((r: PreviewRecord) => r.employee_code === code)
                        const pdfName = matchingRecord ? matchingRecord.employee_name : 'Unknown'
                        return (
                          <div key={code} className="flex flex-col gap-1 bg-slate-50 p-3 rounded-lg border border-slate-100">
                            <div className="flex justify-between items-center text-xs">
                              <span className="font-bold text-slate-800 font-mono">Code: {code}</span>
                              <span className="text-slate-400">({pdfName})</span>
                            </div>
                            <select
                              value={employeeMappings[code] || ''}
                              onChange={(e) =>
                                setEmployeeMappings({
                                  ...employeeMappings,
                                  [code]: e.target.value,
                                })
                              }
                              className="h-8 text-xs bg-white border border-slate-200 rounded px-2 mt-1 w-full"
                            >
                              <option value="">-- Choose Existing Employee --</option>
                              {employees.map((emp: Employee) => (
                                <option key={emp.id} value={emp.id}>
                                  {emp.full_name} ({emp.employee_id})
                                </option>
                              ))}
                            </select>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )}
              </div>
            )}

          {/* Action Footer */}
          <div className="flex justify-between items-center bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
            <Button variant="outline" onClick={() => setStep(1)} className="text-xs h-9">
              Back to Upload
            </Button>
            <Button
              onClick={handleConfirmCommit}
              disabled={committing || previewData.is_payroll_finalized}
              className={`text-white text-xs font-semibold px-6 h-9 shadow-md ${
                previewData.is_payroll_finalized
                  ? 'bg-slate-400 cursor-not-allowed'
                  : 'bg-teal-600 hover:bg-teal-700 shadow-teal-600/20'
              }`}
            >
              {previewData.is_payroll_finalized
                ? 'Period Finalized (Blocked)'
                : 'Confirm & Save Records to Database'}
            </Button>
          </div>
        </div>
      )}

      {/* STEP 4: Committing Spinner */}
      {step === 4 && (
        <div className="bg-white p-16 rounded-xl border border-slate-200 shadow-xs text-center space-y-4">
          <Loader2 className="w-10 h-10 text-teal-600 animate-spin mx-auto" />
          <h2 className="text-base font-bold text-slate-900">Saving Attendance Records to Database...</h2>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            Creating consolidated attendance rows, registering biometric code aliases, generating monthly aggregates, and recording audit logs.
          </p>
        </div>
      )}

      {/* STEP 5: Success Summary */}
      {step === 5 && importSummary && (
        <div className="bg-white p-8 rounded-xl border border-slate-200 shadow-xs text-center space-y-6">
          <div className="w-14 h-14 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-8 h-8" />
          </div>

          <div>
            <h2 className="text-xl font-extrabold text-slate-900">Attendance Import Completed Successfully!</h2>
            <p className="text-xs text-slate-500 mt-1">
              Attendance records for <strong>{previewData?.period_name || 'the selected period'}</strong> have been saved cleanly.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-lg mx-auto bg-slate-50 p-4 rounded-xl border border-slate-100 text-xs">
            <div>
              <span className="text-slate-400 font-medium">New Records</span>
              <p className="text-lg font-bold text-emerald-600">{importSummary.imported ?? 0}</p>
            </div>
            <div>
              <span className="text-slate-400 font-medium">Updated</span>
              <p className="text-lg font-bold text-teal-600">{importSummary.updated ?? 0}</p>
            </div>
            <div>
              <span className="text-slate-400 font-medium">Skipped (Dups)</span>
              <p className="text-lg font-bold text-amber-600">{importSummary.skipped ?? 0}</p>
            </div>
            <div>
              <span className="text-slate-400 font-medium">Errors</span>
              <p className="text-lg font-bold text-rose-600">{importSummary.errors ?? 0}</p>
            </div>
          </div>

          {/* Action CTAs Linking Straight to Payroll */}
          <div className="pt-4 flex flex-col sm:flex-row justify-center items-center gap-3">
            {previewData?.period_year && previewData?.period_month && (
              <Button
                onClick={handleCalculatePayroll}
                disabled={calculatingPayroll}
                className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-5 h-10 shadow-md shadow-teal-600/20"
              >
                {calculatingPayroll ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Calculating Payroll...
                  </>
                ) : (
                  <>
                    <Calculator className="w-4 h-4 mr-2" />
                    Calculate Payroll for {previewData.period_name}
                  </>
                )}
              </Button>
            )}

            <Button
              variant="outline"
              onClick={() => {
                if (previewData?.period_year && previewData?.period_month) {
                  router.push(`/payroll?year=${previewData.period_year}&month=${previewData.period_month}`)
                } else {
                  router.push('/payroll')
                }
              }}
              className="text-xs h-10 px-5"
            >
              Go to Payroll Table
            </Button>

            <Button
              variant="ghost"
              onClick={() => {
                setSelectedFile(null)
                setStep(1)
              }}
              className="text-xs h-10 px-4 text-slate-500 hover:text-slate-700"
            >
              Import Another PDF
            </Button>
          </div>

          {/* Documentation Link */}
          <div className="pt-4 border-t border-slate-100 text-center">
            <Link
              href="/docs/monthly-import"
              className="inline-flex items-center gap-1.5 text-xs text-slate-500 hover:text-teal-700 font-medium"
            >
              <FileText className="w-3.5 h-3.5" />
              Need help? Read docs/MONTHLY_IMPORT.md for eSSL export and verification procedures
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
