'use client'

import { useEffect, useState } from 'react'
import { Plus, Check, X, CalendarOff, Loader2, Search } from 'lucide-react'
import api from '@/lib/api'
import { LeaveRequest, LeaveType, Employee } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function LeaveManagementPage() {
  const [requests, setRequests] = useState<LeaveRequest[]>([])
  const [leaveTypes, setLeaveTypes] = useState<LeaveType[]>([])
  const [loading, setLoading] = useState(true)
  const [showApplyModal, setShowApplyModal] = useState(false)

  const [leaveTypeId, setLeaveTypeId] = useState('')
  const [startDate, setStartDate] = useState(new Date().toISOString().split('T')[0])
  const [endDate, setEndDate] = useState(new Date().toISOString().split('T')[0])
  const [reason, setReason] = useState('')
  const [employeeId, setEmployeeId] = useState<number | null>(null)

  // Employee search for the picker
  const [employees, setEmployees] = useState<Employee[]>([])
  const [empSearch, setEmpSearch] = useState('')
  const [showEmpDropdown, setShowEmpDropdown] = useState(false)
  const [selectedEmpLabel, setSelectedEmpLabel] = useState('')

  const fetchLeaveData = async () => {
    setLoading(true)
    try {
      const [reqRes, typesRes] = await Promise.all([
        api.get('/leaves'),
        api.get('/leave-types'),
      ])
      setRequests(reqRes.data.items || [])
      setLeaveTypes(typesRes.data.items || [])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchLeaveData()
  }, [])

  // Fetch employees for the searchable picker
  useEffect(() => {
    if (showApplyModal) {
      api.get('/employees', { params: { page_size: 100 } })
        .then((res) => setEmployees(res.data.items || []))
        .catch(() => {})
    }
  }, [showApplyModal])

  const filteredEmployees = employees.filter((emp) => {
    if (!empSearch) return true
    const term = empSearch.toLowerCase()
    return (
      emp.full_name?.toLowerCase().includes(term) ||
      emp.employee_id?.toLowerCase().includes(term) ||
      emp.biometric_code?.toLowerCase().includes(term)
    )
  })

  const handleSelectEmployee = (emp: Employee) => {
    setEmployeeId(emp.id)
    setSelectedEmpLabel(`${emp.full_name} (${emp.employee_id})`)
    setEmpSearch('')
    setShowEmpDropdown(false)
  }

  const handleApply = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/leaves', {
        leave_type_id: Number(leaveTypeId),
        start_date: startDate,
        end_date: endDate,
        reason,
        employee_id: employeeId || undefined,
      })
      setShowApplyModal(false)
      setEmployeeId(null)
      setSelectedEmpLabel('')
      fetchLeaveData()
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to submit leave request.')
    }
  }

  const handleApprove = async (id: number) => {
    try {
      await api.put(`/leaves/${id}/approve`, { comment: 'Approved by HR' })
      fetchLeaveData()
    } catch (err) {
      alert('Failed to approve leave.')
    }
  }

  const handleReject = async (id: number) => {
    try {
      await api.put(`/leaves/${id}/reject`, { comment: 'Rejected by HR' })
      fetchLeaveData()
    } catch (err) {
      alert('Failed to reject leave.')
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Leave Management</h1>
          <p className="text-xs text-slate-500 mt-1">Review leave applications, manage allocations, and approve time-off</p>
        </div>

        <Button
          onClick={() => setShowApplyModal(true)}
          className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2"
        >
          <Plus className="w-4 h-4" />
          Apply for Leave
        </Button>
      </div>

      {showApplyModal && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900">Submit Leave Application</h2>

            <form onSubmit={handleApply} className="space-y-4">
              {/* Employee Picker */}
              <div className="space-y-1.5 relative">
                <Label className="text-xs font-semibold">Employee (If applying for staff)</Label>
                {selectedEmpLabel ? (
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-9 px-3 rounded-md border border-teal-200 bg-teal-50 text-xs flex items-center text-teal-800 font-semibold">
                      {selectedEmpLabel}
                    </div>
                    <Button type="button" variant="outline" size="sm" className="h-9 px-2" onClick={() => { setEmployeeId(null); setSelectedEmpLabel(''); }}>
                      <X className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                ) : (
                  <div className="relative">
                    <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
                    <Input
                      value={empSearch}
                      onChange={(e) => { setEmpSearch(e.target.value); setShowEmpDropdown(true); }}
                      onFocus={() => setShowEmpDropdown(true)}
                      placeholder="Search by name or employee code..."
                      className="text-xs h-9 pl-8"
                    />
                    {showEmpDropdown && filteredEmployees.length > 0 && (
                      <div className="absolute top-10 left-0 right-0 bg-white border border-slate-200 rounded-md shadow-lg z-50 max-h-40 overflow-y-auto">
                        {filteredEmployees.slice(0, 10).map((emp) => (
                          <button
                            key={emp.id}
                            type="button"
                            onClick={() => handleSelectEmployee(emp)}
                            className="w-full text-left px-3 py-2 text-xs hover:bg-teal-50 flex items-center justify-between border-b border-slate-50 last:border-0"
                          >
                            <span className="font-semibold text-slate-800">{emp.full_name}</span>
                            <span className="font-mono text-slate-500">{emp.employee_id}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Leave Type *</Label>
                <select
                  required
                  value={leaveTypeId}
                  onChange={(e) => setLeaveTypeId(e.target.value)}
                  className="h-9 px-3 rounded-md border border-slate-200 text-xs w-full"
                >
                  <option value="">Select Leave Type</option>
                  {leaveTypes.map((t) => (
                    <option key={t.id} value={t.id}>{t.name} ({t.code})</option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Start Date *</Label>
                  <Input type="date" required value={startDate} onChange={(e) => setStartDate(e.target.value)} className="text-xs h-9" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">End Date *</Label>
                  <Input type="date" required value={endDate} onChange={(e) => setEndDate(e.target.value)} className="text-xs h-9" />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Reason *</Label>
                <textarea
                  required
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="State the reason for leave..."
                  className="w-full text-xs p-2.5 rounded-md border border-slate-200 focus:ring-2 focus:ring-teal-500 focus:outline-hidden"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => { setShowApplyModal(false); setEmployeeId(null); setSelectedEmpLabel(''); }} className="text-xs h-9">
                  Cancel
                </Button>
                <Button type="submit" className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9">
                  Submit Request
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Requests Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-12 flex justify-center text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
          </div>
        ) : requests.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[11px]">
                <tr>
                  <th className="p-3.5 pl-5">Emp Code</th>
                  <th className="p-3.5">Employee Name</th>
                  <th className="p-3.5">Leave Type</th>
                  <th className="p-3.5">Dates</th>
                  <th className="p-3.5">Days</th>
                  <th className="p-3.5">Reason</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5 text-right pr-5">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {requests.map((req) => (
                  <tr key={req.id} className="hover:bg-slate-50/80">
                    <td className="p-3.5 pl-5 font-mono text-slate-900 font-bold">{req.employee_code || '—'}</td>
                    <td className="p-3.5 font-semibold text-slate-900">{req.employee_name || 'Staff'}</td>
                    <td className="p-3.5 font-semibold text-teal-700">{req.leave_type}</td>
                    <td className="p-3.5 font-mono text-slate-600">{req.start_date} → {req.end_date}</td>
                    <td className="p-3.5 font-bold">{req.days_count} day(s)</td>
                    <td className="p-3.5 text-slate-500 max-w-xs truncate">{req.reason || '—'}</td>
                    <td className="p-3.5">
                      {req.status === 'APPROVED' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">APPROVED</span>}
                      {req.status === 'PENDING' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">PENDING</span>}
                      {req.status === 'REJECTED' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-800">REJECTED</span>}
                    </td>
                    <td className="p-3.5 text-right pr-5 space-x-1">
                      {req.status === 'PENDING' && (
                        <>
                          <Button
                            size="sm"
                            onClick={() => handleApprove(req.id)}
                            className="h-7 px-2 text-[11px] bg-emerald-600 hover:bg-emerald-700 text-white"
                          >
                            <Check className="w-3.5 h-3.5 mr-1" />
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleReject(req.id)}
                            className="h-7 px-2 text-[11px] text-rose-600 border-rose-200 hover:bg-rose-50"
                          >
                            <X className="w-3.5 h-3.5 mr-1" />
                            Reject
                          </Button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center text-slate-400">
            No leave applications registered.
          </div>
        )}
      </div>
    </div>
  )
}
