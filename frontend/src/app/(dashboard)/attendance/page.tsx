'use client'

import { useEffect, useState } from 'react'
import { Calendar as CalendarIcon, Filter, Search, Edit3, Loader2, CheckCircle2, AlertTriangle, CalendarOff, ArrowLeftRight, CheckSquare, Square } from 'lucide-react'
import api from '@/lib/api'
import { AttendanceRecord, Department } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'

function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}

const LEAVE_TYPES = [
  { code: 'CL', name: 'Casual Leave (Paid up to 3/mo)' },
  { code: 'SL', name: 'Sick Leave (Paid up to 3/mo)' },
  { code: 'EL', name: 'Earned Leave (Paid up to 3/mo)' },
  { code: 'LOP', name: 'Loss of Pay (Unpaid Leave)' },
  { code: 'ML', name: 'Maternity Leave' },
  { code: 'CO', name: 'Compensatory Off' },
  { code: 'EM', name: 'Emergency Leave' },
]

export default function DailyAttendancePage() {
  const [attendance, setAttendance] = useState<AttendanceRecord[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)

  const [selectedDate, setSelectedDate] = useState<string>('')
  const [selectedDept, setSelectedDept] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [search, setSearch] = useState<string>('')
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [total, setTotal] = useState(0)
  const debouncedSearch = useDebounce(search, 300)

  // Selection for bulk reclassification
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  // Correction Modal state
  const [selectedRecord, setSelectedRecord] = useState<AttendanceRecord | null>(null)
  const [correctedIn, setCorrectedIn] = useState('')
  const [correctedOut, setCorrectedOut] = useState('')
  const [reason, setReason] = useState('')
  const [submittingCorrection, setSubmittingCorrection] = useState(false)

  // Leave Reclassification Modal state
  const [leaveModalOpen, setLeaveModalOpen] = useState(false)
  const [targetRecords, setTargetRecords] = useState<AttendanceRecord[]>([])
  const [leaveAction, setLeaveAction] = useState<'MARK_LEAVE' | 'REVERT_ABSENT'>('MARK_LEAVE')
  const [selectedLeaveType, setSelectedLeaveType] = useState<string>('CL')
  const [leaveReason, setLeaveReason] = useState<string>('')
  const [submittingLeave, setSubmittingLeave] = useState(false)

  const fetchAttendance = async () => {
    setLoading(true)
    try {
      const params: any = { page, page_size: pageSize }
      if (selectedDate) params.attendance_date = selectedDate
      if (selectedDept) params.department_id = selectedDept
      if (statusFilter) params.status_filter = statusFilter
      if (debouncedSearch) params.search = debouncedSearch

      const [attRes, deptRes] = await Promise.all([
        api.get('/attendance', { params }),
        departments.length === 0 ? api.get('/departments') : Promise.resolve({ data: { items: departments } }),
      ])
      setAttendance(attRes.data.items || [])
      setTotal(attRes.data.total || 0)
      if (deptRes.data.items) setDepartments(deptRes.data.items)
      setSelectedIds([])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchAttendance()
  }, [selectedDate, selectedDept, statusFilter, debouncedSearch, page])

  useEffect(() => {
    setPage(1)
  }, [selectedDate, selectedDept, statusFilter, debouncedSearch])

  const toggleSelectAll = () => {
    if (selectedIds.length === attendance.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(attendance.map((a) => a.id))
    }
  }

  const toggleSelectRow = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    )
  }

  const handleOpenCorrection = (record: AttendanceRecord) => {
    setSelectedRecord(record)
    const inTimeVal = record.source_in_time || record.in_time || '09:30'
    let inHour = 9
    if (inTimeVal && inTimeVal.includes(':')) {
      const parsedH = parseInt(inTimeVal.split(':')[0], 10)
      if (!isNaN(parsedH)) inHour = parsedH
    }

    const shiftCode = (record.shift_code || 'GS').toUpperCase().trim()
    let defaultOut = '20:00'

    if (shiftCode === 'NIGHT' || shiftCode === 'NTS') {
      defaultOut = '09:30'
    } else if (shiftCode === 'GS' || shiftCode === 'MS') {
      defaultOut = '20:00'
    } else if (shiftCode === 'S2' || shiftCode === 'IS' || shiftCode === 'B') {
      defaultOut = '20:30'
    } else if (shiftCode === 'S3' || shiftCode === 'DIET') {
      defaultOut = '19:00'
    } else if (shiftCode === 'S4') {
      defaultOut = '18:00'
    } else if (shiftCode === 'HK_SPLIT' || shiftCode === 'HK' || shiftCode === 'HKN') {
      defaultOut = inHour >= 16 || inHour < 6 ? '08:30' : '18:30'
    } else if (shiftCode === 'SEC_SPLIT' || shiftCode === 'SS' || shiftCode === 'SNS') {
      defaultOut = inHour >= 15 || inHour < 6 ? '08:00' : '17:00'
    } else if (shiftCode === 'LAB_SPLIT') {
      defaultOut = inHour >= 16 || inHour < 6 ? '09:30' : '17:30'
    }

    setCorrectedIn(inTimeVal)
    const existingOut = (record.source_out_time && record.source_out_time !== '00:00') 
      ? record.source_out_time 
      : (record.out_time && record.out_time !== '00:00' && record.out_time !== '—' ? record.out_time : null)
    setCorrectedOut(existingOut || defaultOut)
    setReason('')
  }

  const handleSaveCorrection = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedRecord) return
    setSubmittingCorrection(true)

    try {
      await api.put(`/attendance/${selectedRecord.id}/correct`, {
        corrected_in: correctedIn,
        corrected_out: correctedOut,
        reason,
      })
      setSelectedRecord(null)
      fetchAttendance()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to apply manual correction.')
    } finally {
      setSubmittingCorrection(false)
    }
  }

  const openSingleLeaveReclassify = (record: AttendanceRecord, action: 'MARK_LEAVE' | 'REVERT_ABSENT') => {
    setTargetRecords([record])
    setLeaveAction(action)
    setLeaveReason('')
    setSelectedLeaveType('CL')
    setLeaveModalOpen(true)
  }

  const openBulkLeaveReclassify = (action: 'MARK_LEAVE' | 'REVERT_ABSENT') => {
    const targets = attendance.filter((a) => selectedIds.includes(a.id))
    setTargetRecords(targets)
    setLeaveAction(action)
    setLeaveReason('')
    setSelectedLeaveType('CL')
    setLeaveModalOpen(true)
  }

  const handleSaveLeaveReclassify = async () => {
    if (targetRecords.length === 0) return
    setSubmittingLeave(true)

    try {
      if (targetRecords.length === 1) {
        await api.post('/attendance/reclassify-leave', {
          attendance_id: targetRecords[0].id,
          action: leaveAction,
          leave_type_code: selectedLeaveType,
          reason: leaveReason || (leaveAction === 'MARK_LEAVE' ? `Approved ${selectedLeaveType}` : 'Reverted to Absent'),
        })
      } else {
        await api.post('/attendance/bulk-reclassify-leave', {
          attendance_ids: targetRecords.map((r) => r.id),
          action: leaveAction,
          leave_type_code: selectedLeaveType,
          reason: leaveReason || `Bulk ${leaveAction === 'MARK_LEAVE' ? 'Leave Reclassification' : 'Revert to Absent'}`,
        })
      }
      setLeaveModalOpen(false)
      fetchAttendance()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to reclassify leave.')
    } finally {
      setSubmittingLeave(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Daily Attendance Records</h1>
          <p className="text-xs text-slate-500 mt-1">Review raw eSSL punch logs, mark absent days as approved leave, and apply HR corrections</p>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <Input
            placeholder="Search employee..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 text-xs h-10 border-slate-200"
          />
        </div>

        <div>
          <Input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="text-xs h-10 border-slate-200"
          />
        </div>

        <div>
          <select
            value={selectedDept}
            onChange={(e) => setSelectedDept(e.target.value)}
            className="h-10 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 w-full"
          >
            <option value="">All Departments</option>
            {departments.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
        </div>

        <div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-10 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 w-full"
          >
            <option value="">All Statuses</option>
            <option value="PRESENT">Present</option>
            <option value="ABSENT">Absent</option>
            <option value="PRESENT_INCOMPLETE">Incomplete (No Out Punch)</option>
            <option value="PRESENT_OVERNIGHT">Overnight Shift</option>
            <option value="LEAVE">On Leave</option>
          </select>
        </div>
      </div>

      {/* Bulk Action Banner */}
      {selectedIds.length > 0 && (
        <div className="bg-teal-50 border border-teal-200 p-3 rounded-xl flex items-center justify-between">
          <div className="text-xs font-semibold text-teal-900 flex items-center gap-2">
            <CheckSquare className="w-4 h-4 text-teal-700" />
            <span>{selectedIds.length} attendance record{selectedIds.length > 1 ? 's' : ''} selected</span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={() => openBulkLeaveReclassify('MARK_LEAVE')}
              className="bg-blue-600 hover:bg-blue-700 text-white text-xs h-8 gap-1.5"
            >
              <CalendarOff className="w-3.5 h-3.5" />
              Mark Selected as Leave
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => openBulkLeaveReclassify('REVERT_ABSENT')}
              className="text-xs h-8 text-rose-700 border-rose-200 hover:bg-rose-50"
            >
              Revert to Absent
            </Button>
          </div>
        </div>
      )}

      {/* Attendance Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-12 flex justify-center text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
          </div>
        ) : attendance.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="p-3.5 pl-4 w-10">
                    <input
                      type="checkbox"
                      checked={selectedIds.length === attendance.length && attendance.length > 0}
                      onChange={toggleSelectAll}
                      className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 cursor-pointer"
                    />
                  </th>
                  <th className="p-3.5">Date</th>
                  <th className="p-3.5">Emp ID</th>
                  <th className="p-3.5">Employee Name</th>
                  <th className="p-3.5">Department</th>
                  <th className="p-3.5">In Time</th>
                  <th className="p-3.5">Out Time</th>
                  <th className="p-3.5">Work (hrs)</th>
                  <th className="p-3.5">OT (hrs)</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5 text-right pr-5">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {attendance.map((rec) => {
                  const isSelected = selectedIds.includes(rec.id)
                  const isAbsent = rec.status === 'ABSENT'
                  const isLeave = rec.status === 'LEAVE'

                  return (
                    <tr key={rec.id} className={`hover:bg-slate-50/80 transition-colors ${isSelected ? 'bg-teal-50/30' : ''}`}>
                      <td className="p-3.5 pl-4">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => toggleSelectRow(rec.id)}
                          className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 cursor-pointer"
                        />
                      </td>
                      <td className="p-3.5 font-mono text-slate-600">{rec.attendance_date}</td>
                      <td className="p-3.5 font-mono text-slate-900 font-bold">{rec.employee_code || (rec as any).biometric_code}</td>
                      <td className="p-3.5 font-semibold text-slate-900">{rec.employee_name || 'Staff'}</td>
                      <td className="p-3.5 text-slate-600">{rec.department_name || (rec as any).department || '—'}</td>
                      <td className="p-3.5 font-mono text-emerald-700">{rec.source_in_time || (rec as any).in_time || '—'}</td>
                      <td className="p-3.5 font-mono text-teal-700">{rec.source_out_time || (rec as any).out_time || '—'}</td>
                      <td className="p-3.5 font-mono">{rec.work_minutes ? (rec.work_minutes / 60).toFixed(1) : '0.0'}</td>
                      <td className="p-3.5 font-mono text-purple-700 font-bold">{rec.ot_minutes ? (rec.ot_minutes / 60).toFixed(1) : '0.0'}</td>
                      <td className="p-3.5">
                        {rec.status === 'PRESENT' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">PRESENT</span>}
                        {rec.status === 'ABSENT' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-800">ABSENT</span>}
                        {rec.status === 'PRESENT_INCOMPLETE' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">NO OUT PUNCH</span>}
                        {rec.status === 'PRESENT_OVERNIGHT' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-purple-100 text-purple-800">OVERNIGHT</span>}
                        {rec.status === 'LEAVE' && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200">
                            LEAVE
                          </span>
                        )}
                        {rec.is_corrected && (
                          <span className="ml-1 text-[9px] text-amber-600 font-bold" title="HR Corrected">✓</span>
                        )}
                      </td>
                      <td className="p-3.5 text-right pr-5">
                        <div className="flex items-center justify-end gap-1.5">
                          {isAbsent && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openSingleLeaveReclassify(rec, 'MARK_LEAVE')}
                              className="h-7 px-2 text-xs text-blue-700 border-blue-200 hover:bg-blue-50"
                            >
                              <CalendarOff className="w-3.5 h-3.5 mr-1" />
                              Mark Leave
                            </Button>
                          )}
                          {isLeave && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openSingleLeaveReclassify(rec, 'REVERT_ABSENT')}
                              className="h-7 px-2 text-xs text-rose-700 border-rose-200 hover:bg-rose-50"
                            >
                              <ArrowLeftRight className="w-3.5 h-3.5 mr-1" />
                              To Absent
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenCorrection(rec)}
                            className="h-7 px-2 text-xs text-slate-600 hover:text-teal-600"
                          >
                            <Edit3 className="w-3.5 h-3.5 mr-1" />
                            Correct
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
          <div className="p-12 text-center text-slate-400">
            No attendance records found for selected filters.
          </div>
        )}
      </div>

      {/* Pagination Footer */}
      {!loading && total > 0 && (
        <div className="flex items-center justify-between px-4 py-3 bg-white border border-slate-200 rounded-xl shadow-2xs">
          <span className="text-xs text-slate-600">
            Showing {Math.min((page - 1) * pageSize + 1, total)} to {Math.min(page * pageSize, total)} of {total} records
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="text-xs h-8"
            >
              Previous
            </Button>
            <span className="text-xs text-slate-700 font-semibold">Page {page} of {Math.ceil(total / pageSize)}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={page >= Math.ceil(total / pageSize)}
              className="text-xs h-8"
            >
              Next
            </Button>
          </div>
        </div>
      )}

      {/* Leave Reclassification Dialog Modal */}
      <Dialog open={leaveModalOpen} onOpenChange={setLeaveModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-bold text-slate-900">
              {leaveAction === 'MARK_LEAVE' ? 'Reclassify Absent Days as Leave' : 'Revert Leave Days to Absent'}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1 text-slate-700">
              <p>Target: <strong className="text-slate-900">{targetRecords.length} record{targetRecords.length > 1 ? 's' : ''}</strong></p>
              {targetRecords.length === 1 && (
                <>
                  <p>Staff: <strong className="text-slate-900">{targetRecords[0].employee_name || 'Staff'}</strong> ({targetRecords[0].employee_code})</p>
                  <p>Date: <strong className="text-slate-900">{targetRecords[0].attendance_date}</strong></p>
                </>
              )}
            </div>

            {leaveAction === 'MARK_LEAVE' && (
              <>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-slate-700">Leave Type</Label>
                  <select
                    value={selectedLeaveType}
                    onChange={(e) => setSelectedLeaveType(e.target.value)}
                    className="h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 w-full"
                  >
                    {LEAVE_TYPES.map((lt) => (
                      <option key={lt.code} value={lt.code}>{lt.name}</option>
                    ))}
                  </select>
                </div>

                <div className="p-2.5 bg-blue-50/80 rounded-lg border border-blue-200 text-[11px] text-blue-900 space-y-1">
                  <p className="font-bold">📋 Hospital Paid Leave Policy:</p>
                  <p>Up to <strong>3 leave days per month</strong> are counted as paid in payroll. Any leave days beyond 3 remain unpaid (LOP).</p>
                </div>
              </>
            )}

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700">Notes / Reason (Optional)</Label>
              <Input
                value={leaveReason}
                onChange={(e) => setLeaveReason(e.target.value)}
                placeholder="e.g. Medical certificate submitted; approved by HR"
                className="text-xs h-9"
              />
            </div>
          </div>

          <DialogFooter className="flex items-center justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setLeaveModalOpen(false)} className="text-xs">
              Cancel
            </Button>
            <Button
              size="sm"
              onClick={handleSaveLeaveReclassify}
              disabled={submittingLeave}
              className={`text-white text-xs font-semibold gap-1.5 ${leaveAction === 'MARK_LEAVE' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-rose-600 hover:bg-rose-700'}`}
            >
              {submittingLeave ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
              {leaveAction === 'MARK_LEAVE' ? 'Confirm Mark Leave' : 'Confirm Revert to Absent'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Manual Time Correction Dialog Modal */}
      {selectedRecord && (
        <Dialog open={!!selectedRecord} onOpenChange={(open) => !open && setSelectedRecord(null)}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-base font-bold text-slate-900">
                HR Attendance Correction
              </DialogTitle>
            </DialogHeader>

            <div className="bg-slate-50 p-3 rounded-lg text-xs space-y-1 text-slate-700 border border-slate-100">
              <p>Employee: <strong className="text-slate-900">{selectedRecord.employee_name || 'Staff'}</strong> ({selectedRecord.employee_code})</p>
              <p>Date: <strong className="text-slate-900">{selectedRecord.attendance_date}</strong></p>
              <p>Original In/Out: <span className="font-mono">{selectedRecord.source_in_time || '—'}</span> / <span className="font-mono">{selectedRecord.source_out_time || '—'}</span></p>
            </div>

            <form onSubmit={handleSaveCorrection} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-700">Corrected In Time</label>
                  <Input type="time" required value={correctedIn} onChange={(e) => setCorrectedIn(e.target.value)} className="text-xs h-9" />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-700">Corrected Out Time</label>
                  <Input type="time" required value={correctedOut} onChange={(e) => setCorrectedOut(e.target.value)} className="text-xs h-9" />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-700">Correction Reason *</label>
                <textarea
                  required
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g. Employee forgot out-punch; verified with duty roster"
                  className="w-full text-xs p-2.5 rounded-md border border-slate-200 focus:ring-2 focus:ring-teal-500 focus:outline-hidden"
                />
              </div>

              <DialogFooter className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setSelectedRecord(null)} className="text-xs h-9">
                  Cancel
                </Button>
                <Button type="submit" disabled={submittingCorrection} className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9">
                  {submittingCorrection ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Correction'}
                </Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
