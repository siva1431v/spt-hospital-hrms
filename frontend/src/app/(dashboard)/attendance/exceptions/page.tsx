'use client'

import { useEffect, useState } from 'react'
import { AlertTriangle, Check, X, Filter, Loader2, CheckSquare, Square, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { toast } from 'sonner'

interface AttendanceException {
  id: number
  employee_name: string | null
  employee_code: string | null
  exception_date: string
  exception_type: string
  reason: string | null
  original_value: string | null
  severity: string
  review_status: string
  review_notes?: string | null
  created_at: string
}

export default function AttendanceExceptionsPage() {
  const [exceptions, setExceptions] = useState<AttendanceException[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [pendingCount, setPendingCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('PENDING')
  const [severityFilter, setSeverityFilter] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [bulkProcessing, setBulkProcessing] = useState(false)

  const fetchExceptions = async () => {
    setLoading(true)
    try {
      const params: any = { page, page_size: pageSize }
      if (statusFilter) params.review_status = statusFilter
      if (severityFilter) params.severity = severityFilter

      const res = await api.get('/attendance/exceptions', { params })
      setExceptions(res.data.items || [])
      setTotalCount(res.data.total || 0)
      setPendingCount(res.data.pending_total || 0)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchExceptions()
    setSelectedIds([])
  }, [statusFilter, severityFilter, page, pageSize])

  const handleReview = async (id: number, action: 'APPROVED' | 'DISMISSED') => {
    try {
      await api.put(`/attendance/exceptions/${id}/review`, {
        status: action,
        notes: `Reviewed as ${action} by HR`,
      })
      toast.success(`Exception marked as ${action.toLowerCase()}`)
      fetchExceptions()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to review exception')
    }
  }

  const handleBulkReview = async (action: 'APPROVED' | 'DISMISSED') => {
    if (selectedIds.length === 0) {
      toast.error('No exceptions selected')
      return
    }
    setBulkProcessing(true)
    try {
      await api.post('/attendance/exceptions/bulk-review', {
        exception_ids: selectedIds,
        status: action,
        notes: `Bulk reviewed as ${action} by HR`,
      })
      toast.success(`Bulk updated ${selectedIds.length} exceptions as ${action.toLowerCase()}`)
      setSelectedIds([])
      fetchExceptions()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to bulk review exceptions')
    } finally {
      setBulkProcessing(false)
    }
  }

  const toggleSelectAll = () => {
    if (selectedIds.length === exceptions.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(exceptions.map((e) => e.id))
    }
  }

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id]
    )
  }

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize))

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-600 flex items-center justify-center font-bold">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Attendance Exceptions</h1>
            <p className="text-xs text-slate-500 mt-0.5">Review missing out-punches, late arrivals, and overnight shift anomalies</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200">
            {pendingCount} pending exceptions
          </span>
          <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
            {statusFilter ? `${statusFilter}: ${totalCount}` : `Total: ${totalCount}`}
          </span>
        </div>
      </div>

      {/* Filters & Bulk Action Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-700">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span>Status:</span>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            className="h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 font-semibold focus:outline-hidden focus:ring-2 focus:ring-teal-500"
          >
            <option value="">All Statuses ({totalCount})</option>
            <option value="PENDING">Pending Review ({pendingCount})</option>
            <option value="APPROVED">Approved / Resolved</option>
            <option value="DISMISSED">Dismissed</option>
          </select>

          <select
            value={severityFilter}
            onChange={(e) => { setSeverityFilter(e.target.value); setPage(1) }}
            className="h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-teal-500"
          >
            <option value="">All Severities</option>
            <option value="ERROR">Error / High</option>
            <option value="WARNING">Warning / Medium</option>
            <option value="INFO">Info / Low</option>
          </select>
        </div>

        {/* Bulk Action Controls */}
        <div className="flex items-center gap-2">
          {selectedIds.length > 0 && (
            <>
              <span className="text-xs font-semibold text-slate-600 mr-1">
                {selectedIds.length} selected
              </span>
              <Button
                size="sm"
                onClick={() => handleBulkReview('APPROVED')}
                disabled={bulkProcessing}
                className="h-8 px-3 text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-semibold gap-1.5"
              >
                {bulkProcessing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                Bulk Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleBulkReview('DISMISSED')}
                disabled={bulkProcessing}
                className="h-8 px-3 text-xs text-slate-700 border-slate-300 hover:bg-slate-50 font-semibold gap-1.5"
              >
                <X className="w-3.5 h-3.5" />
                Bulk Dismiss
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-12 flex justify-center text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
          </div>
        ) : exceptions.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[11px]">
                <tr>
                  <th className="p-3.5 pl-5 w-10">
                    <button
                      type="button"
                      onClick={toggleSelectAll}
                      className="text-slate-500 hover:text-slate-700 flex items-center"
                    >
                      {selectedIds.length > 0 && selectedIds.length === exceptions.length ? (
                        <CheckSquare className="w-4 h-4 text-teal-600" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>
                  </th>
                  <th className="p-3.5">Date</th>
                  <th className="p-3.5">Employee</th>
                  <th className="p-3.5">Exception Type</th>
                  <th className="p-3.5">Reason / Details</th>
                  <th className="p-3.5">Severity</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5 text-right pr-5">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {exceptions.map((item) => (
                  <tr key={item.id} className={`hover:bg-slate-50/80 ${selectedIds.includes(item.id) ? 'bg-teal-50/40' : ''}`}>
                    <td className="p-3.5 pl-5">
                      <button
                        type="button"
                        onClick={() => toggleSelect(item.id)}
                        className="text-slate-500 hover:text-slate-700 flex items-center"
                      >
                        {selectedIds.includes(item.id) ? (
                          <CheckSquare className="w-4 h-4 text-teal-600" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                    </td>
                    <td className="p-3.5 font-mono text-slate-900 font-bold">{item.exception_date}</td>
                    <td className="p-3.5 font-semibold text-slate-900">{item.employee_name || 'Unassigned Staff'}</td>
                    <td className="p-3.5 font-semibold text-amber-700">{item.exception_type}</td>
                    <td className="p-3.5 text-slate-600 max-w-xs truncate">{item.reason || item.original_value || '—'}</td>
                    <td className="p-3.5">
                      {(item.severity === 'ERROR' || item.severity === 'HIGH') && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-800">ERROR</span>}
                      {(item.severity === 'WARNING' || item.severity === 'MEDIUM') && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">WARNING</span>}
                      {(item.severity === 'INFO' || item.severity === 'LOW') && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-800">INFO</span>}
                      {!['ERROR', 'HIGH', 'WARNING', 'MEDIUM', 'INFO', 'LOW'].includes(item.severity) && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700">{item.severity || 'WARNING'}</span>}
                    </td>
                    <td className="p-3.5">
                      {item.review_status === 'APPROVED' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">APPROVED</span>}
                      {item.review_status === 'PENDING' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">PENDING</span>}
                      {item.review_status === 'DISMISSED' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600">DISMISSED</span>}
                      {item.review_status === 'CORRECTED' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-800">CORRECTED</span>}
                    </td>
                    <td className="p-3.5 text-right pr-5 space-x-1">
                      {item.review_status === 'PENDING' ? (
                        <>
                          <Button
                            size="sm"
                            onClick={() => handleReview(item.id, 'APPROVED')}
                            className="h-7 px-2 text-[11px] bg-emerald-600 hover:bg-emerald-700 text-white font-semibold"
                          >
                            <Check className="w-3.5 h-3.5 mr-1" />
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleReview(item.id, 'DISMISSED')}
                            className="h-7 px-2 text-[11px] text-slate-600 border-slate-200 hover:bg-slate-50"
                          >
                            <X className="w-3.5 h-3.5 mr-1" />
                            Dismiss
                          </Button>
                        </>
                      ) : (
                        <span className="text-[11px] text-slate-400 italic">Resolved</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Pagination Controls */}
            <div className="p-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
              <div>
                Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, totalCount)} of {totalCount} exceptions
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="h-8 px-2.5"
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <span className="font-semibold text-slate-800">
                  Page {page} of {totalPages}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="h-8 px-2.5"
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-12 text-center text-slate-400 space-y-1">
            <p className="text-sm font-semibold text-slate-600">No attendance exceptions found.</p>
            <p className="text-xs text-slate-400">All attendance records and out-punches are verified.</p>
          </div>
        )}
      </div>
    </div>
  )
}

