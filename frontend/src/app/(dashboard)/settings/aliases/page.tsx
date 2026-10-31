'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, Fingerprint, Plus, Trash2, Loader2, Search, Building2, Save } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { toast } from 'sonner'

interface DeviceCodeAliasItem {
  id: number
  company: string
  device_code: string
  employee_id: number
  employee_name?: string
  employee_code?: string
  notes?: string
  created_at?: string
}

interface EmployeeOption {
  id: number
  full_name?: string
  first_name?: string
  last_name?: string
  employee_id: string
  biometric_code?: string
  department?: { name: string }
}

export default function DeviceCodeAliasesPage() {
  const [aliases, setAliases] = useState<DeviceCodeAliasItem[]>([])
  const [employees, setEmployees] = useState<EmployeeOption[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  // Create modal state
  const [showAddModal, setShowAddModal] = useState(false)
  const [company, setCompany] = useState('SPT')
  const [deviceCode, setDeviceCode] = useState('')
  const [selectedEmpId, setSelectedEmpId] = useState<number | ''>('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const fetchData = async () => {
    setLoading(true)
    try {
      const [aliasRes, empRes] = await Promise.all([
        api.get('/attendance/aliases'),
        api.get('/employees', { params: { is_active: true, limit: 300 } }),
      ])
      setAliases(aliasRes.data.items || [])
      setEmployees(empRes.data.items || empRes.data || [])
    } catch (err) {
      console.error(err)
      toast.error('Failed to load device aliases.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleCreateAlias = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!company.trim()) {
      toast.error('Please enter a company or device section name')
      return
    }
    if (!deviceCode.trim()) {
      toast.error('Please enter a device biometric code')
      return
    }
    if (!selectedEmpId) {
      toast.error('Please select an employee to map')
      return
    }

    setSubmitting(true)
    try {
      await api.post('/attendance/aliases', {
        company: company.trim(),
        device_code: deviceCode.trim(),
        employee_id: Number(selectedEmpId),
        notes: notes.trim() || undefined,
      })
      toast.success('Biometric device alias saved successfully!')
      setShowAddModal(false)
      setDeviceCode('')
      setSelectedEmpId('')
      setNotes('')
      fetchData()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to save alias.'
      toast.error(msg)
    } finally {
      setSubmitting(false)
    }
  }

  const handleDelete = async (aliasId: number) => {
    if (!confirm('Are you sure you want to delete this device alias?')) return
    setDeletingId(aliasId)
    try {
      await api.delete(`/attendance/aliases/${aliasId}`)
      toast.success('Alias removed successfully.')
      setAliases(aliases.filter((a) => a.id !== aliasId))
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to delete alias.'
      toast.error(msg)
    } finally {
      setDeletingId(null)
    }
  }

  const filteredAliases = aliases.filter((a) => {
    const q = search.toLowerCase()
    return (
      a.company.toLowerCase().includes(q) ||
      a.device_code.toLowerCase().includes(q) ||
      (a.employee_name && a.employee_name.toLowerCase().includes(q)) ||
      (a.employee_code && a.employee_code.toLowerCase().includes(q)) ||
      (a.notes && a.notes.toLowerCase().includes(q))
    )
  })

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Link
              href="/settings"
              className="text-slate-500 hover:text-slate-800 transition-colors p-1 rounded-md hover:bg-slate-100"
              title="Back to Settings"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
              <Fingerprint className="w-6 h-6 text-teal-600" />
              Biometric Device Code Aliases
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1 pl-7">
            Map device biometric codes across multiple machines (e.g. SPT Main vs Old Bio) to staff members in the Master Database.
          </p>
        </div>

        <Button
          onClick={() => setShowAddModal(true)}
          className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-1.5 shadow-xs"
        >
          <Plus className="w-4 h-4" />
          Add Device Alias
        </Button>
      </div>

      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <Input
            placeholder="Search by code, employee, company..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9 text-xs"
          />
        </div>
        <div className="text-xs text-slate-500">
          Total Aliases: <strong className="text-slate-900 font-bold">{aliases.length}</strong>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-16 flex justify-center text-teal-600">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : filteredAliases.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[11px]">
                <tr>
                  <th className="p-3 pl-4 whitespace-nowrap">Company / Device</th>
                  <th className="p-3 text-center whitespace-nowrap">Device Biometric Code</th>
                  <th className="p-3 whitespace-nowrap">Mapped Staff Member</th>
                  <th className="p-3 whitespace-nowrap">Notes</th>
                  <th className="p-3 text-center pr-4 whitespace-nowrap">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {filteredAliases.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/80">
                    <td className="p-3 pl-4 whitespace-nowrap">
                      <div className="flex items-center gap-1.5 font-bold text-slate-900">
                        <Building2 className="w-3.5 h-3.5 text-slate-400" />
                        {item.company}
                      </div>
                    </td>
                    <td className="p-3 text-center whitespace-nowrap">
                      <span className="font-mono font-bold bg-slate-100 text-slate-800 px-2 py-0.5 rounded border border-slate-200">
                        {item.device_code}
                      </span>
                    </td>
                    <td className="p-3 whitespace-nowrap">
                      <div className="font-bold text-slate-900">{item.employee_name || '—'}</div>
                      <div className="text-[10px] text-slate-500 font-mono">
                        Master Code: {item.employee_code || item.employee_id}
                      </div>
                    </td>
                    <td className="p-3 text-slate-500 text-xs">
                      {item.notes || <span className="text-slate-300 italic">None</span>}
                    </td>
                    <td className="p-3 text-center pr-4 whitespace-nowrap">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDelete(item.id)}
                        disabled={deletingId === item.id}
                        className="h-7 w-7 p-0 text-slate-400 hover:text-rose-600 hover:bg-rose-50"
                        title="Delete alias"
                      >
                        {deletingId === item.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="w-3.5 h-3.5" />
                        )}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-16 text-center text-slate-500 space-y-3">
            <div className="w-12 h-12 mx-auto rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
              <Fingerprint className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-800">No device aliases found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Device aliases allow multiple biometric codes or secondary machines to automatically map to the right staff member during monthly imports.
            </p>
            <Button
              onClick={() => setShowAddModal(true)}
              variant="outline"
              size="sm"
              className="text-xs font-semibold"
            >
              Add First Device Alias
            </Button>
          </div>
        )}
      </div>

      {/* Add Alias Modal */}
      <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-bold text-slate-900 flex items-center gap-2">
              <Fingerprint className="w-5 h-5 text-teal-600" />
              Add Biometric Device Alias
            </DialogTitle>
          </DialogHeader>

          <form onSubmit={handleCreateAlias} className="space-y-4 py-2 text-xs">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700">Company / Machine Section</Label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={company === 'SPT' ? 'default' : 'outline'}
                  onClick={() => setCompany('SPT')}
                  className={`text-xs h-8 ${company === 'SPT' ? 'bg-teal-600 text-white' : ''}`}
                >
                  SPT
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={company === 'Old Bio' ? 'default' : 'outline'}
                  onClick={() => setCompany('Old Bio')}
                  className={`text-xs h-8 ${company === 'Old Bio' ? 'bg-teal-600 text-white' : ''}`}
                >
                  Old Bio
                </Button>
                <Input
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  placeholder="Or enter custom company..."
                  className="text-xs h-8"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700">Device Biometric Code (Emp. Code in PDF)</Label>
              <Input
                value={deviceCode}
                onChange={(e) => setDeviceCode(e.target.value)}
                placeholder="e.g. 64, 203, 208"
                className="text-xs h-8 font-mono"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700">Map to Master Staff Member</Label>
              <select
                value={selectedEmpId}
                onChange={(e) => setSelectedEmpId(Number(e.target.value))}
                className="w-full h-9 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-800"
                required
              >
                <option value="">-- Select Employee --</option>
                {employees.map((emp) => {
                  const name = emp.full_name || `${emp.first_name || ''} ${emp.last_name || ''}`.trim()
                  const dept = emp.department?.name ? ` • ${emp.department.name}` : ''
                  const bio = emp.biometric_code ? ` [Bio: ${emp.biometric_code}]` : ''
                  return (
                    <option key={emp.id} value={emp.id}>
                      {name} ({emp.employee_id}{bio}){dept}
                    </option>
                  )
                })}
              </select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold text-slate-700">Notes / Reason (Optional)</Label>
              <Input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Registered as code 203 on secondary floor reader"
                className="text-xs h-8"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowAddModal(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={submitting}
                className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-1.5"
              >
                {submitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                Save Alias
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
