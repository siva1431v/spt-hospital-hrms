'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Upload,
  FileText,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  ArrowRight,
  RefreshCw,
  Info,
} from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'

export default function ImportPdfWizardPage() {
  const router = useRouter()
  const [step, setStep] = useState<1 | 2 | 3 | 4 | 5>(1)

  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [previewData, setPreviewData] = useState<any | null>(null)
  const [sessionToken, setSessionToken] = useState<string | null>(null)

  const [uploading, setUploading] = useState(false)
  const [committing, setCommitting] = useState(false)
  const [duplicateHandling, setDuplicateHandling] = useState<'SKIP' | 'OVERWRITE'>('SKIP')
  const [importSummary, setImportSummary] = useState<any | null>(null)

  const [employees, setEmployees] = useState<any[]>([])
  const [departments, setDepartments] = useState<any[]>([])
  const [employeeMappings, setEmployeeMappings] = useState<{ [code: string]: string }>({})
  const [departmentMappings, setDepartmentMappings] = useState<{ [name: string]: string }>({})

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
        api.get('/departments?is_active=true')
      ])

      setEmployees(empRes.data.items || [])
      setDepartments(deptRes.data.items || [])

      setPreviewData(response.data)
      setSessionToken(response.data.session_token || response.data._temp_path || 'valid')

      if (response.data.statistics?.total_records === 0) {
        alert("Warning: The eSSL PDF parser extracted 0 attendance records from this file. Please verify that the PDF is a valid eSSL attendance report (Daily Attendance Report or Monthly Status Report).")
      }

      setStep(3)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to parse attendance PDF report.')
      setStep(1)
    } finally {
      setUploading(false)
    }
  }

  // Step 4: Commit Import
  const handleConfirmCommit = async () => {
    if (!previewData) return
    setCommitting(true)
    setStep(4)

    try {
      const payload = {
        ...previewData,
        session_token: sessionToken || previewData.session_token,
        duplicate_action: duplicateHandling.toLowerCase(),
        employee_mappings: employeeMappings,
        department_mappings: departmentMappings,
      }
      const response = await api.post('/attendance/import/commit', payload)

      setImportSummary(response.data)
      setStep(5)
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to commit attendance records.')
      setStep(3)
    } finally {
      setCommitting(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Page Title */}
      <div className="border-b border-slate-200/80 pb-5">
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">eSSL PDF Attendance Import Wizard</h1>
        <p className="text-xs text-slate-500 mt-1">
          Upload real hospital eSSL PDF attendance reports to parse punch times, overnight shifts, and OT
        </p>
      </div>

      {/* Stepper Progress */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex items-center justify-between">
        {[
          { num: 1, label: 'Upload PDF' },
          { num: 2, label: 'Parsing' },
          { num: 3, label: 'Review & Mapping' },
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
                  Supports eSSL standard PDF attendance log files (up to 50MB)
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
            Extracting company header, date range blocks, employee biometric codes, punch times, and calculating OT.
          </p>
        </div>
      )}

      {/* STEP 3: Preview & Record Validation */}
      {step === 3 && previewData && (
        <div className="space-y-6">
          {/* Metadata Card */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">Report Metadata & Summary</h2>
            {previewData.report_type && (
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-800 text-xs font-bold border border-indigo-200">
                <FileText className="w-3.5 h-3.5" />
                Detected Format: {previewData.report_type}
              </div>
            )}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 bg-slate-50 p-4 rounded-lg border border-slate-100 text-xs">
              <div>
                <span className="text-slate-400 font-medium">Company Name:</span>
                <p className="font-semibold text-slate-900">{previewData.company_name || 'SPT Hospital'}</p>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Date Range:</span>
                <p className="font-semibold text-slate-900">
                  {previewData.date_range_start} to {previewData.date_range_end}
                </p>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Total Attendance Records:</span>
                <p className="font-semibold text-teal-700 text-sm">{previewData.statistics?.total_records}</p>
              </div>
              <div>
                <span className="text-slate-400 font-medium">Duplicates Detected:</span>
                <p className="font-semibold text-amber-600 text-sm">{previewData.statistics?.duplicate}</p>
              </div>
            </div>

            {/* Duplicate Settings */}
            <div className="flex items-center gap-4 pt-2">
              <span className="text-xs font-semibold text-slate-700">Duplicate Handling Strategy:</span>
              <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
                <input
                  type="radio"
                  name="dups"
                  value="SKIP"
                  checked={duplicateHandling === 'SKIP'}
                  onChange={() => setDuplicateHandling('SKIP')}
                  className="text-teal-600"
                />
                Skip existing records (Recommended)
              </label>
              <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer">
                <input
                  type="radio"
                  name="dups"
                  value="OVERWRITE"
                  checked={duplicateHandling === 'OVERWRITE'}
                  onChange={() => setDuplicateHandling('OVERWRITE')}
                  className="text-teal-600"
                />
                Overwrite existing DB records
              </label>
            </div>
          </div>

          {/* MAPPING SECTIONS */}
          {((previewData.unknown_employee_codes && previewData.unknown_employee_codes.length > 0) ||
            (previewData.unknown_department_names && previewData.unknown_department_names.length > 0) ||
            (previewData.unmapped_shift_codes && previewData.unmapped_shift_codes.length > 0)) && (
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-6">
              <h2 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2 uppercase tracking-wider">
                Review Mappings & Resolve Conflicts
              </h2>

              {previewData.unmapped_shift_codes && previewData.unmapped_shift_codes.length > 0 && (
                <div className="p-3 bg-amber-50 rounded-lg border border-amber-200 text-xs space-y-1">
                  <div className="flex items-center gap-1.5 font-bold text-amber-900">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    <span>Unmapped Shift Codes Found in PDF ({previewData.unmapped_shift_codes.length})</span>
                  </div>
                  <p className="text-amber-800 text-[11px]">
                    The following shift codes from the device have no mapping: <strong className="font-mono">{previewData.unmapped_shift_codes.join(', ')}</strong>. You can configure alias rules under <strong>Shifts</strong> page.
                  </p>
                </div>
              )}

              {previewData.unknown_department_names && previewData.unknown_department_names.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600" />
                    Unmapped Departments ({previewData.unknown_department_names.length})
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    The following department names from the PDF do not exist in the database. Map them to an existing department:
                  </p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {previewData.unknown_department_names.map((deptName: string) => (
                      <div key={deptName} className="flex flex-col gap-1 bg-slate-50 p-3 rounded-lg border border-slate-100">
                        <span className="text-xs font-semibold text-slate-700 font-mono">{deptName}</span>
                        <select
                          value={departmentMappings[deptName] || ''}
                          onChange={(e) =>
                            setDepartmentMappings({
                              ...departmentMappings,
                              [deptName]: e.target.value,
                            })
                          }
                          className="h-8 text-xs bg-white border border-slate-200 rounded px-2 mt-1 w-full"
                        >
                          <option value="">-- Choose Existing Department --</option>
                          {departments.map((d: any) => (
                            <option key={d.id} value={d.id}>
                              {d.name} ({d.code})
                            </option>
                          ))}
                        </select>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {previewData.unknown_employee_codes && previewData.unknown_employee_codes.length > 0 && (
                <div className="space-y-3 pt-4 border-t border-slate-100">
                  <h3 className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-rose-500" />
                    Unmapped Employee Biometric Codes ({previewData.unknown_employee_codes.length})
                  </h3>
                  <p className="text-[11px] text-slate-500">
                    These biometric codes from the PDF are not registered in any employee profile. Map them to register their attendance:
                  </p>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {previewData.unknown_employee_codes.map((code: string) => {
                      const matchingRecord = previewData.records?.find((r: any) => r.employee_code === code)
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
                            {employees.map((emp: any) => (
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

          {/* Records Table Preview */}
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs space-y-3 p-4">
            <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">Record Preview (First 50 Entries)</h2>
            <div className="max-h-80 overflow-y-auto border border-slate-100 rounded-lg">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="p-2.5">Date</th>
                    <th className="p-2.5">Emp Code</th>
                    <th className="p-2.5">Name</th>
                    <th className="p-2.5">Dept</th>
                    <th className="p-2.5">In</th>
                    <th className="p-2.5">Out</th>
                    <th className="p-2.5">Status</th>
                    <th className="p-2.5">Validation</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                  {previewData.records?.map((rec: any, idx: number) => {
                    const hasError = rec.is_unknown_employee || (rec.errors && rec.errors.length > 0)
                    const isDup = rec.is_duplicate
                    const isUnknownDept = rec.is_unknown_department
                    
                    let rowBg = ''
                    if (hasError) rowBg = 'bg-rose-50/60'
                    else if (isDup) rowBg = 'bg-amber-50/60'
                    else if (isUnknownDept) rowBg = 'bg-orange-50/50'

                    return (
                      <tr key={idx} className={rowBg}>
                        <td className="p-2.5">{rec.attendance_date}</td>
                        <td className="p-2.5 font-bold text-slate-900">{rec.employee_code}</td>
                        <td className="p-2.5 font-sans font-medium text-slate-800">{rec.employee_name}</td>
                        <td className="p-2.5 font-sans text-slate-600">{rec.department_name || 'Default'}</td>
                        <td className="p-2.5 text-emerald-700">{rec.in_time || '—'}</td>
                        <td className="p-2.5 text-teal-700">{rec.out_time || '—'}</td>
                        <td className="p-2.5 font-sans font-semibold">
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-700">
                            {rec.status}
                          </span>
                        </td>
                        <td className="p-2.5 font-sans text-[10px]">
                          {isDup && <span className="text-amber-700 font-semibold">Duplicate</span>}
                          {rec.is_unknown_employee && <span className="text-rose-600 font-semibold">New Employee</span>}
                          {isUnknownDept && <span className="text-orange-600 font-semibold">Unmapped Dept</span>}
                          {!rec.is_unknown_employee && !isDup && <span className="text-emerald-600 font-semibold">Valid</span>}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {previewData.monthly_aggregates && previewData.monthly_aggregates.length > 0 && (
              <div className="space-y-3 pt-4 border-t border-slate-200">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
                    Extracted Monthly Aggregates ({previewData.monthly_aggregates.length} Employees)
                  </h2>
                  <span className="text-[11px] text-indigo-700 font-semibold bg-indigo-50 px-2 py-0.5 rounded border border-indigo-100">
                    Pre-computed Source Totals
                  </span>
                </div>
                <div className="max-h-60 overflow-y-auto border border-slate-100 rounded-lg">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px]">
                      <tr>
                        <th className="p-2.5">Code</th>
                        <th className="p-2.5">Employee Name</th>
                        <th className="p-2.5">Department</th>
                        <th className="p-2.5 text-center">Present</th>
                        <th className="p-2.5 text-center">Absent</th>
                        <th className="p-2.5 text-center text-amber-700">Late Days</th>
                        <th className="p-2.5">Total Work</th>
                        <th className="p-2.5">Total OT</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 font-mono text-[11px]">
                      {previewData.monthly_aggregates.slice(0, 50).map((agg: any, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="p-2.5 font-bold text-slate-900">{agg.employee_code}</td>
                          <td className="p-2.5 font-sans font-medium text-slate-800">{agg.employee_name}</td>
                          <td className="p-2.5 font-sans text-slate-600">{agg.department_name}</td>
                          <td className="p-2.5 text-center text-emerald-600 font-bold">{agg.present_count}</td>
                          <td className="p-2.5 text-center text-rose-600 font-bold">{agg.absent_count}</td>
                          <td className="p-2.5 text-center text-amber-700 font-bold">{agg.late_by_days}</td>
                          <td className="p-2.5">{agg.total_work_duration || '—'}</td>
                          <td className="p-2.5">{agg.total_ot || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          <div className="flex justify-between items-center bg-white p-4 rounded-xl border border-slate-200">
            <Button variant="outline" onClick={() => setStep(1)} className="text-xs h-9">
              Back to Upload
            </Button>
            <Button
              onClick={handleConfirmCommit}
              disabled={committing}
              className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-6 h-9 shadow-md shadow-teal-600/20"
            >
              Confirm & Save Records to Database
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
            Creating attendance records, auto-generating missing department & employee profiles if needed, and logging audit entries.
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
            <p className="text-xs text-slate-500 mt-1">All valid attendance records have been persisted to the database.</p>
          </div>

          <div className="grid grid-cols-3 gap-4 max-w-lg mx-auto bg-slate-50 p-4 rounded-xl border border-slate-100 text-xs">
            <div>
              <span className="text-slate-400 font-medium">Imported</span>
              <p className="text-lg font-bold text-emerald-600">{importSummary.imported}</p>
            </div>
            <div>
              <span className="text-slate-400 font-medium">Skipped</span>
              <p className="text-lg font-bold text-amber-600">{importSummary.skipped}</p>
            </div>
            <div>
              <span className="text-slate-400 font-medium">Errors</span>
              <p className="text-lg font-bold text-rose-600">{importSummary.errors}</p>
            </div>
          </div>

          <div className="flex justify-center gap-3 pt-4">
            <Button onClick={() => router.push('/attendance')} className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold px-5 h-9">
              View Daily Attendance Table
            </Button>
            <Button variant="outline" onClick={() => { setSelectedFile(null); setStep(1); }} className="text-xs h-9">
              Import Another PDF Report
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
