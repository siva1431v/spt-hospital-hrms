'use client'

import { useEffect, useState } from 'react'
import { Shield, Search, Loader2, ChevronLeft, ChevronRight } from 'lucide-react'
import api from '@/lib/api'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'

function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)
    return () => clearTimeout(handler)
  }, [value, delay])
  return debouncedValue
}

export default function AuditLogsPage() {
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [actionFilter, setActionFilter] = useState('')
  const debouncedAction = useDebounce(actionFilter, 300)
  
  const [entityType, setEntityType] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  
  const [page, setPage] = useState(1)
  const pageSize = 50
  const [total, setTotal] = useState(0)

  const fetchLogs = async (currentPage: number) => {
    setLoading(true)
    try {
      const params: any = {
        page: currentPage,
        page_size: pageSize,
      }
      if (debouncedAction) params.action = debouncedAction
      if (entityType) params.entity_type = entityType
      if (dateFrom) params.date_from = dateFrom
      if (dateTo) params.date_to = dateTo

      const res = await api.get('/audit-logs', { params })
      setLogs(res.data.items || [])
      setTotal(res.data.total || 0)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setPage(1)
    fetchLogs(1)
  }, [debouncedAction, entityType, dateFrom, dateTo])
  
  useEffect(() => {
    fetchLogs(page)
  }, [page])

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">System Audit Trail</h1>
          <p className="text-xs text-slate-500 mt-1">Immutable security log of all administrative actions, imports, and manual overrides</p>
        </div>
      </div>

      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-wrap gap-4 items-end">
        <div className="relative flex-1 min-w-[200px]">
          <Label className="text-xs font-semibold mb-1.5 block">Search Action</Label>
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-8" />
          <Input
            placeholder="Filter by action (e.g. IMPORT)..."
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="pl-9 text-xs h-10 border-slate-200"
          />
        </div>
        
        <div className="w-48">
          <Label className="text-xs font-semibold mb-1.5 block">Entity Type</Label>
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="w-full text-xs h-10 rounded-md border border-slate-200 bg-white px-3 focus:outline-none focus:ring-2 focus:ring-teal-500"
          >
            <option value="">All Entities</option>
            <option value="user">User</option>
            <option value="employee">Employee</option>
            <option value="attendance">Attendance</option>
            <option value="payroll">Payroll</option>
            <option value="leave_request">Leave Request</option>
          </select>
        </div>
        
        <div className="w-40">
          <Label className="text-xs font-semibold mb-1.5 block">From Date</Label>
          <Input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="text-xs h-10"
          />
        </div>
        
        <div className="w-40">
          <Label className="text-xs font-semibold mb-1.5 block">To Date</Label>
          <Input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="text-xs h-10"
          />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs flex flex-col">
        {loading ? (
          <div className="p-12 flex justify-center text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
          </div>
        ) : logs.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[11px]">
                <tr>
                  <th className="p-3.5 pl-5">Timestamp</th>
                  <th className="p-3.5">User</th>
                  <th className="p-3.5">Action</th>
                  <th className="p-3.5">Entity</th>
                  <th className="p-3.5">Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/80">
                    <td className="p-3.5 pl-5 font-mono text-slate-500">{new Date(log.created_at).toLocaleString()}</td>
                    <td className="p-3.5 font-semibold text-slate-900">{log.user_name || 'System'}</td>
                    <td className="p-3.5 font-mono font-bold text-teal-700">{log.action}</td>
                    <td className="p-3.5 font-mono text-slate-600">{log.entity_type} #{log.entity_id}</td>
                    <td className="p-3.5 text-slate-700 max-w-md truncate" title={log.description}>{log.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center text-slate-400">
            No audit log entries found.
          </div>
        )}
        
        {/* Pagination */}
        {!loading && total > 0 && (
          <div className="p-4 border-t border-slate-200 flex items-center justify-between bg-slate-50">
            <p className="text-xs text-slate-500">
              Showing <span className="font-semibold text-slate-900">{(page - 1) * pageSize + 1}</span> to{' '}
              <span className="font-semibold text-slate-900">{Math.min(page * pageSize, total)}</span> of{' '}
              <span className="font-semibold text-slate-900">{total}</span> entries
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 1}
                onClick={() => setPage(p => p - 1)}
                className="h-8 px-3 text-xs"
              >
                <ChevronLeft className="w-3.5 h-3.5 mr-1" /> Prev
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page * pageSize >= total}
                onClick={() => setPage(p => p + 1)}
                className="h-8 px-3 text-xs"
              >
                Next <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
