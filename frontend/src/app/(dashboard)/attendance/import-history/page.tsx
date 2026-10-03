'use client'

import { useEffect, useState } from 'react'
import { History, FileText, CheckCircle2, AlertTriangle, XCircle, Loader2, Download } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { formatDate } from '@/lib/dateUtils'

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
  const [downloadingId, setDownloadingId] = useState<number | null>(null)

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

  const handleDownloadPdf = async (id: number, filename?: string) => {
    try {
      setDownloadingId(id)
      const defaultFilename = filename || `attendance_import_${id}.pdf`
      const response = await api.get(`/attendance/imports/${id}/download?presigned=true`, {
        responseType: 'blob',
      })

      const contentType = response.headers['content-type']
      const isJson =
        response.data?.type === 'application/json' ||
        (typeof contentType === 'string' && contentType.includes('application/json'))

      if (isJson) {
        const text = await response.data.text()
        const json = JSON.parse(text)
        if (json.download_url) {
          const link = document.createElement('a')
          link.href = json.download_url
          link.target = '_blank'
          link.setAttribute('download', json.filename || defaultFilename)
          document.body.appendChild(link)
          link.click()
          link.remove()
          return
        }
      }

      const url = window.URL.createObjectURL(response.data)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', defaultFilename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      alert('Original PDF file is not available or could not be downloaded.')
    } finally {
      setDownloadingId(null)
    }
  }

  return (
    <div className="w-full space-y-6">
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
                <p className="text-xs text-slate-500">
                  Imported on {formatDate(selectedImport.imported_at)} {new Date(selectedImport.imported_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={downloadingId === selectedImport.id}
                  onClick={() => handleDownloadPdf(selectedImport.id, selectedImport.filename)}
                  className="h-8 px-2.5 text-xs text-slate-700 border-slate-200 hover:bg-slate-50 gap-1.5"
                >
                  {downloadingId === selectedImport.id ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Download className="w-3.5 h-3.5 text-slate-500" />
                  )}
                  Download PDF
                </Button>
                <Button size="sm" variant="outline" onClick={() => setSelectedImport(null)} className="h-8 px-2 text-xs">
                  Close
                </Button>
              </div>
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
                        <td className="p-2.5 pl-4 font-mono">{formatDate(r.attendance_date || r.date)}</td>
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
                  <th className="px-3 py-2.5 pl-4 whitespace-nowrap">File Name</th>
                  <th className="px-3 py-2.5 whitespace-nowrap">Import Date</th>
                  <th className="px-3 py-2.5 whitespace-nowrap">Date Range</th>
                  <th className="px-3 py-2.5 text-center whitespace-nowrap">Total Records</th>
                  <th className="px-3 py-2.5 text-center whitespace-nowrap">Imported</th>
                  <th className="px-3 py-2.5 text-center whitespace-nowrap">Duplicates</th>
                  <th className="px-3 py-2.5 whitespace-nowrap">Status</th>
                  <th className="px-3 py-2.5 text-right pr-4 sticky right-0 bg-slate-50 shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.06)] z-10 whitespace-nowrap">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {imports.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/80 group">
                    <td className="px-3 py-2 pl-4 font-semibold text-slate-900 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-teal-600 shrink-0" />
                        <span>{item.filename}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-slate-600 whitespace-nowrap">
                      {formatDate(item.imported_at)} {new Date(item.imported_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="px-3 py-2 font-mono text-slate-600 whitespace-nowrap">
                      {item.date_range_start && item.date_range_end
                        ? `${formatDate(item.date_range_start)} → ${formatDate(item.date_range_end)}`
                        : '—'}
                    </td>
                    <td className="px-3 py-2 font-bold font-mono text-center whitespace-nowrap">{item.total_records}</td>
                    <td className="px-3 py-2 font-bold font-mono text-emerald-700 text-center whitespace-nowrap">{item.records_imported}</td>
                    <td className="px-3 py-2 font-bold font-mono text-amber-700 text-center whitespace-nowrap">{item.records_duplicate}</td>
                    <td className="px-3 py-2 whitespace-nowrap">
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
                    <td className="px-3 py-2 text-right pr-4 sticky right-0 bg-white group-hover:bg-slate-50 shadow-[-4px_0_6px_-2px_rgba(0,0,0,0.06)] z-10 whitespace-nowrap">
                      <div className="flex items-center justify-end gap-1.5">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={downloadingId === item.id}
                          onClick={() => handleDownloadPdf(item.id, item.filename)}
                          className="h-7 px-2 text-xs text-slate-700 border-slate-200 hover:bg-slate-50 gap-1"
                          title="Download original eSSL PDF"
                        >
                          {downloadingId === item.id ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Download className="w-3 h-3 text-slate-500" />
                          )}
                          PDF
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleViewDetail(item.id)}
                          className="h-7 px-2.5 text-xs text-teal-700 border-teal-200 hover:bg-teal-50"
                        >
                          View Log
                        </Button>
                      </div>
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
