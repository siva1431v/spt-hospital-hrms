'use client'

import { useEffect, useState } from 'react'
import { AlertTriangle, Check, X, Loader2, CheckSquare, Square, ChevronLeft, ChevronRight, Search } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { toast } from 'sonner'
import { formatDate } from '@/lib/dateUtils'

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

const EXCEPTION_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'NO_OUT_PUNCH', label: 'Missing Out Punch (NO_OUT_PUNCH)' },
  { value: 'LATE_ARRIVAL', label: 'Late Arrival (LATE_ARRIVAL)' },
  { value: 'EARLY_EXIT', label: 'Early Exit (EARLY_EXIT)' },
  { value: 'OVERNIGHT_ANOMALY', label: 'Overnight Shift Anomaly' },
  { value: 'UNMATCHED_EMPLOYEE', label: 'Unmatched Biometric Code' },
]

export default function AttendanceExceptionsPage() {
  const [exceptions, setExceptions] = useState<AttendanceException[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [pendingCount, setPendingCount] = useState(0)
  const [loading, setLoading] = useState(true)
  
  // Filters
  const [statusFilter, setStatusFilter] = useState('PENDING')
  const [severityFilter, setSeverityFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [dateFilter, setDateFilter] = useState('')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')

  // Pagination
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  
  // Selection & Bulk Actions
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [bulkProcessing, setBulkProcessing] = useState(false)
  const [confirmBulkAction, setConfirmBulkAction] = useState<'APPROVED' | 'DISMISSED' | null>(null)
  
  const [refreshTrigger, setRefreshTrigger] = useState(0)
  const refreshExceptions = () => setRefreshTrigger((n) => n + 1)

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 250)
    return () => clearTimeout(timer)
  }, [search])

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const params: Record<string, string | number> = { page, page_size: pageSize }
        if (statusFilter) params.review_status = statusFilter
        if (severityFilter) params.severity = severityFilter
        if (typeFilter) params.exception_type = typeFilter
        if (dateFilter) params.exception_date = dateFilter
        if (debouncedSearch.trim()) params.search = debouncedSearch.trim()

        const res = await api.get('/attendance/exceptions', { params })
        if (active) {
          setExceptions(res.data.items || [])
          setTotalCount(res.data.total || 0)
          setPendingCount(res.data.pending_total || 0)
          setSelectedIds([])
        }
      } catch (err) {
        console.error(err)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => {
      active = false
    }
  }, [statusFilter, severityFilter, typeFilter, dateFilter, debouncedSearch, page, pageSize, refreshTrigger])

  const handleReview = async (id: number, action: 'APPROVED' | 'DISMISSED') => {
    try {
      await api.put(`/attendance/exceptions/${id}/review`, {
        status: action,
        notes: `Reviewed as ${action} by HR`,
      })
      toast.success(`Exception marked as ${action.toLowerCase()}`)
      refreshExceptions()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || 'Failed to review exception')
    }
  }

  const executeBulkReview = async () => {
    if (!confirmBulkAction || selectedIds.length === 0) return
    const action = confirmBulkAction
    setBulkProcessing(true)
    try {
      await api.post('/attendance/exceptions/bulk-review', {
        exception_ids: selectedIds,
        status: action,
        notes: `Bulk reviewed as ${action} by HR`,
      })
      toast.success(`Bulk updated ${selectedIds.length} exceptions as ${action.toLowerCase()}`)
      setSelectedIds([])
      setConfirmBulkAction(null)
      refreshExceptions()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || 'Failed to bulk review exceptions')
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
    <div className="w-full space-y-6">
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
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-3">
          {/* Employee search */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-3" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search staff, code, reason..."
              className="text-xs h-9 pl-8"
            />
          </div>

          {/* Date filter */}
          <div>
            <Input
              type="date"
              value={dateFilter}
              onChange={(e) => { setDateFilter(e.target.value); setPage(1) }}
              className="text-xs h-9"
            />
          </div>

          {/* Status filter */}
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

          {/* Exception Type filter */}
          <select
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1) }}
            className="h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-teal-500"
          >
            {EXCEPTION_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>

          {/* Severity filter */}
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
        {selectedIds.length > 0 && (
          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <span className="text-xs font-semibold text-teal-800">
              {selectedIds.length} on this page selected
            </span>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                onClick={() => setConfirmBulkAction('APPROVED')}
                disabled={bulkProcessing}
                className="h-8 px-3 text-xs bg-emerald-600 hover:bg-emerald-700 text-white font-semibold gap-1.5"
              >
                <Check className="w-3.5 h-3.5" />
                Bulk Approve ({selectedIds.length})
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setConfirmBulkAction('DISMISSED')}
                disabled={bulkProcessing}
                className="h-8 px-3 text-xs text-slate-700 border-slate-300 hover:bg-slate-50 font-semibold gap-1.5"
              >
                <X className="w-3.5 h-3.5" />
                Bulk Dismiss ({selectedIds.length})
              </Button>
            </div>
          </div>
        )}
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
                  <th className="px-2.5 py-2.5 pl-3 w-10">
                    <button
                      type="button"
                      onClick={toggleSelectAll}
                      className="text-slate-500 hover:text-slate-700 flex items-center"
                      title="Select all on this page"
                    >
                      {selectedIds.length > 0 && selectedIds.length === exceptions.length ? (
                        <CheckSquare className="w-4 h-4 text-teal-600" />
                      ) : (
                        <Square className="w-4 h-4" />
                      )}
                    </button>
                  </th>
                  <th className="px-2.5 py-2.5 whitespace-nowrap">Date</th>
                  <th className="px-2.5 py-2.5 whitespace-nowrap">Employee</th>
                  <th className="px-2.5 py-2.5 whitespace-nowrap">Exception Type</th>
                  <th className="px-2.5 py-2.5">Reason / Details</th>
                  <th className="px-2.5 py-2.5 text-center whitespace-nowrap">Severity</th>
                  <th className="px-2.5 py-2.5 text-center whitespace-nowrap">Status</th>
                  <th className="px-3 py-2.5 text-right pr-4 sticky right-0 bg-slate-50 shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.06)] z-10 whitespace-nowrap">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {exceptions.map((item) => (
                  <tr key={item.id} className={`hover:bg-slate-50/80 group ${selectedIds.includes(item.id) ? 'bg-teal-50/40' : ''}`}>
                    <td className="px-2.5 py-2 pl-3">
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
                    <td className="px-2.5 py-2 font-mono text-slate-900 font-bold whitespace-nowrap">{formatDate(item.exception_date)}</td>
                    <td className="px-2.5 py-2 font-semibold text-slate-900 whitespace-nowrap">
                      {item.employee_name || 'Unassigned Staff'}
                      {item.employee_code && (
                        <span className="text-slate-400 font-mono text-[10px] ml-1">({item.employee_code})</span>
                      )}
                    </td>
                    <td className="px-2.5 py-2 font-semibold text-amber-700 whitespace-nowrap">{item.exception_type}</td>
                    <td className="px-2.5 py-2 text-slate-600 max-w-xs truncate">{item.reason || item.original_value || '—'}</td>
                    <td className="px-2.5 py-2 text-center whitespace-nowrap">
                      {(item.severity === 'ERROR' || item.severity === 'HIGH') && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-800">ERROR</span>}
                      {(item.severity === 'WARNING' || item.severity === 'MEDIUM') && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">WARNING</span>}
                      {(item.severity === 'INFO' || item.severity === 'LOW') && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-800">INFO</span>}
                      {!['ERROR', 'HIGH', 'WARNING', 'MEDIUM', 'INFO', 'LOW'].includes(item.severity) && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700">{item.severity || 'WARNING'}</span>}
                    </td>
                    <td className="px-2.5 py-2 text-center whitespace-nowrap">
                      {item.review_status === 'APPROVED' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">APPROVED</span>}
                      {item.review_status === 'PENDING' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800">PENDING</span>}
                      {item.review_status === 'DISMISSED' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600">DISMISSED</span>}
                      {item.review_status === 'CORRECTED' && <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-100 text-blue-800">CORRECTED</span>}
                    </td>
                    <td className="px-3 py-2 text-right pr-4 space-x-1 sticky right-0 bg-white group-hover:bg-slate-50 shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.06)] z-10 whitespace-nowrap">
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
              <div className="flex items-center gap-2">
                <span>
                  Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, totalCount)} of {totalCount} exceptions
                </span>
                <select
                  value={pageSize}
                  onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1) }}
                  className="h-7 px-2 rounded border border-slate-200 bg-white text-xs text-slate-700 ml-2"
                >
                  <option value={25}>25 / page</option>
                  <option value={50}>50 / page</option>
                  <option value={100}>100 / page</option>
                </select>
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
            <p className="text-xs text-slate-400">All attendance records and out-punches match the selected filters.</p>
          </div>
        )}
      </div>

      {/* Confirmation Dialog for Bulk Review */}
      {confirmBulkAction && (
        <Dialog open={!!confirmBulkAction} onOpenChange={(open) => !open && setConfirmBulkAction(null)}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle className="text-base font-bold text-slate-900">
                Confirm Bulk {confirmBulkAction === 'APPROVED' ? 'Approval' : 'Dismissal'}
              </DialogTitle>
            </DialogHeader>

            <div className="space-y-3 py-2 text-xs text-slate-700">
              <p>
                Are you sure you want to mark <strong>{selectedIds.length}</strong> selected exception{selectedIds.length > 1 ? 's' : ''} as{' '}
                <span className={confirmBulkAction === 'APPROVED' ? 'font-bold text-emerald-700' : 'font-bold text-slate-800'}>
                  {confirmBulkAction}
                </span>?
              </p>
              <p className="text-slate-500">
                This action will update the review status and can be reviewed in audit logs.
              </p>
            </div>

            <DialogFooter className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setConfirmBulkAction(null)}
                disabled={bulkProcessing}
                className="text-xs h-8"
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={executeBulkReview}
                disabled={bulkProcessing}
                className={`text-white text-xs font-semibold h-8 ${confirmBulkAction === 'APPROVED' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-slate-700 hover:bg-slate-800'}`}
              >
                {bulkProcessing ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : null}
                Confirm {confirmBulkAction === 'APPROVED' ? 'Approve' : 'Dismiss'} ({selectedIds.length})
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}
    </div>
  )
}
