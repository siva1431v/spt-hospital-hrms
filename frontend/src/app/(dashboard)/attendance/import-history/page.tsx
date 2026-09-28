'use client'

import { useEffect, useState } from 'react'
import { History, FileText, CheckCircle2, AlertTriangle, XCircle, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'

interface AttendanceImportSession {
  id: number
  filename: string
  date_range_start: string | null
  date_range_end: string | null
  total_records: number
  total_records_in_pdf?: number
  records_imported: number
  records_duplicate: number
  records_error: number
  status: string
  imported_at: string
}

interface ImportRecordItem {
  attendance_date?: string
  date?: string
  employee_code?: string
  employee_name?: string
  in_time?: string
  out_time?: string
  status?: string
}

interface ImportDetail extends AttendanceImportSession {
  records?: ImportRecordItem[]
}

export default function ImportHistoryPage() {
  const [imports, setImports] = useState<AttendanceImportSession[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedImport, setSelectedImport] = useState<ImportDetail | null>(null)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const res = await api.get('/attendance/imports')
        if (active) setImports(res.data.items || [])
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
  }, [])

  const handleViewDetail = async (id: number) => {
    try {
      const res = await api.get(`/attendance/imports/${id}`)
      setSelectedImport(res.data)
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200/80 pb-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-600 flex items-center justify-center font-bold">
            <History className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">PDF Import History</h1>
            <p className="text-xs text-slate-500 mt-0.5">Audit log of all eSSL attendance PDF imports and processing runs</p>
          </div>
        </div>

        <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-teal-100 text-teal-800">
          {imports.length} import session(s) recorded
        </span>
      </div>

      {/* Detail Modal */}
      {selectedImport && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-2xl w-full p-6 space-y-4 shadow-xl border border-slate-200 max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <h2 className="text-base font-bold text-slate-900">{selectedImport.filename}</h2>
                <p className="text-xs text-slate-500">Imported on {new Date(selectedImport.imported_at).toLocaleString()}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => setSelectedImport(null)} className="h-8 px-2 text-xs">
                Close
              </Button>
            </div>

            <div className="grid grid-cols-4 gap-3 bg-slate-50 p-3 rounded-lg text-center text-xs">
              <div>
                <span className="text-slate-500 block text-[10px]">Total PDF Records</span>
                <span className="font-bold text-slate-900 text-sm">{selectedImport.total_records || selectedImport.total_records_in_pdf || 0}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">Imported</span>
                <span className="font-bold text-emerald-700 text-sm">{selectedImport.records_imported || 0}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">Duplicates Skipped</span>
                <span className="font-bold text-amber-700 text-sm">{selectedImport.records_duplicate || 0}</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[10px]">Errors</span>
                <span className="font-bold text-rose-700 text-sm">{selectedImport.records_error || 0}</span>
              </div>
            </div>

            {selectedImport.records && selectedImport.records.length > 0 ? (
              <div className="overflow-y-auto flex-1 border border-slate-200 rounded-md">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-100 border-b border-slate-200 font-semibold text-slate-600 uppercase text-[10px] sticky top-0">
                    <tr>
                      <th className="p-2.5 pl-4">Date</th>
                      <th className="p-2.5">Code</th>
                      <th className="p-2.5">Name</th>
                      <th className="p-2.5">In Time</th>
                      <th className="p-2.5">Out Time</th>
                      <th className="p-2.5">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {selectedImport.records?.map((r: ImportRecordItem, idx: number) => (
                      <tr key={idx} className="hover:bg-slate-50">
                        <td className="p-2.5 pl-4 font-mono">{r.attendance_date || r.date || '—'}</td>
                        <td className="p-2.5 font-mono font-bold">{r.employee_code}</td>
                        <td className="p-2.5">{r.employee_name}</td>
                        <td className="p-2.5 font-mono">{r.in_time || '—'}</td>
                        <td className="p-2.5 font-mono">{r.out_time || '—'}</td>
                        <td className="p-2.5">
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-800">{r.status}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-slate-500 text-center py-4">No individual record logs found for this session.</p>
            )}
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-12 flex justify-center text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
          </div>
        ) : imports.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[11px]">
                <tr>
                  <th className="p-3.5 pl-5">File Name</th>
                  <th className="p-3.5">Import Date</th>
                  <th className="p-3.5">Date Range</th>
                  <th className="p-3.5">Total Records</th>
                  <th className="p-3.5">Imported</th>
                  <th className="p-3.5">Duplicates</th>
                  <th className="p-3.5">Status</th>
                  <th className="p-3.5 text-right pr-5">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {imports.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/80">
                    <td className="p-3.5 pl-5 font-semibold text-slate-900 flex items-center gap-2">
                      <FileText className="w-4 h-4 text-teal-600 shrink-0" />
                      <span>{item.filename}</span>
                    </td>
                    <td className="p-3.5 text-slate-600">{new Date(item.imported_at).toLocaleString()}</td>
                    <td className="p-3.5 font-mono text-slate-600">
                      {item.date_range_start && item.date_range_end
                        ? `${item.date_range_start} → ${item.date_range_end}`
                        : '—'}
                    </td>
                    <td className="p-3.5 font-bold font-mono">{item.total_records}</td>
                    <td className="p-3.5 font-bold font-mono text-emerald-700">{item.records_imported}</td>
                    <td className="p-3.5 font-bold font-mono text-amber-700">{item.records_duplicate}</td>
                    <td className="p-3.5">
                      {item.status?.toUpperCase() === 'COMPLETED' ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800 flex items-center gap-1 w-fit">
                          <CheckCircle2 className="w-3 h-3" /> Completed
                        </span>
                      ) : item.status?.toUpperCase().includes('WARNING') ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-100 text-amber-800 flex items-center gap-1 w-fit">
                          <AlertTriangle className="w-3 h-3" /> Warnings
                        </span>
                      ) : item.status?.toUpperCase() === 'FAILED' ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-rose-100 text-rose-800 flex items-center gap-1 w-fit">
                          <XCircle className="w-3 h-3" /> Failed
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800 flex items-center gap-1 w-fit">
                          <CheckCircle2 className="w-3 h-3" /> {item.status ? item.status.replace(/_/g, ' ') : 'Completed'}
                        </span>
                      )}
                    </td>
                    <td className="p-3.5 text-right pr-5">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleViewDetail(item.id)}
                        className="h-7 px-2.5 text-xs text-teal-700 border-teal-200 hover:bg-teal-50"
                      >
                        View Log
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center text-slate-400 space-y-1">
            <p className="text-sm font-semibold text-slate-600">No import sessions recorded yet.</p>
            <p className="text-xs text-slate-400">Upload an eSSL PDF attendance report from the Import PDF tab to create your first session log.</p>
          </div>
        )}
      </div>
    </div>
  )
}
