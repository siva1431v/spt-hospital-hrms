'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Plus, Search, Eye, Edit, UserX, UserCheck, Loader2, ChevronLeft, ChevronRight, PiggyBank, Check } from 'lucide-react'
import api from '@/lib/api'
import { Employee, Department } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { toast } from 'sonner'

export default function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([])
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [selectedDept, setSelectedDept] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('active')
  const [refreshIndex, setRefreshIndex] = useState(0)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const pageSize = 50

  // Row selection for bulk actions
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [bulkSavingsOpen, setBulkSavingsOpen] = useState(false)
  const [bulkSavingsAmount, setBulkSavingsAmount] = useState<string>('500')
  const [submittingBulk, setSubmittingBulk] = useState(false)

  // Fetch department list once on mount
  useEffect(() => {
    api.get('/departments')
      .then((res) => setDepartments(res.data.items || []))
      .catch((err) => console.error('Failed to fetch departments', err))
  }, [])

  // Debounce search input by 250ms
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1) // Reset to page 1 on new search
    }, 250)
    return () => clearTimeout(timer)
  }, [search])

  // Single effect owning (debouncedSearch, selectedDept, statusFilter, refreshIndex, page) as a unified query key
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)

    const params: any = { page, page_size: pageSize }
    if (debouncedSearch.trim()) params.search = debouncedSearch.trim()
    if (selectedDept) params.department_id = selectedDept
    if (statusFilter === 'active') params.is_active = true
    else if (statusFilter === 'inactive') params.is_active = false

    api.get('/employees', { params, signal: controller.signal })
      .then((empRes) => {
        setEmployees(empRes.data.items || [])
        setTotal(empRes.data.total || 0)
      })
      .catch((err) => {
        // Discard aborted / superseded requests
        if (err?.name === 'CanceledError' || err?.name === 'AbortError' || err?.code === 'ERR_CANCELED') {
          return
        }
        console.error('Failed to fetch employees', err)
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      })

    return () => {
      controller.abort()
    }
  }, [debouncedSearch, selectedDept, statusFilter, refreshIndex, page])

  const handleDeactivate = async (id: number) => {
    if (!confirm('Are you sure you want to deactivate this employee?')) return
    try {
      await api.delete(`/employees/${id}`)
      setRefreshIndex((prev) => prev + 1)
      setSelectedIds((prev) => prev.filter(i => i !== id))
    } catch (err) {
      alert('Failed to deactivate employee.')
    }
  }

  const handleReactivate = async (id: number) => {
    if (!confirm('Are you sure you want to reactivate this employee?')) return
    try {
      await api.put(`/employees/${id}`, { is_active: true })
      setRefreshIndex((prev) => prev + 1)
    } catch (err) {
      alert('Failed to reactivate employee.')
    }
  }

  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.checked) {
      setSelectedIds(employees.map(e => e.id))
    } else {
      setSelectedIds([])
    }
  }

  const handleSelectRow = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter(i => i !== id) : [...prev, id]
    )
  }

  const handleBulkSetSavings = async (e: React.FormEvent) => {
    e.preventDefault()
    if (selectedIds.length === 0) return
    const amt = Number(bulkSavingsAmount)
    if (isNaN(amt) || amt < 0) {
      toast.error('Please enter a valid amount (0 or greater).')
      return
    }

    setSubmittingBulk(true)
    try {
      const res = await api.post('/employees/bulk-set-savings', {
        employee_ids: selectedIds,
        amount: amt,
      })
      toast.success(`Updated savings deduction to ₹${amt} for ${res.data.updated_count} employees.`)
      setBulkSavingsOpen(false)
      setSelectedIds([])
      setRefreshIndex(prev => prev + 1)
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to bulk-update savings deduction.')
    } finally {
      setSubmittingBulk(false)
    }
  }

  const isAllSelected = employees.length > 0 && selectedIds.length === employees.length

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Employee Directory</h1>
          <p className="text-xs text-slate-500 mt-1">Manage hospital staff profiles, biometric codes, and designations ({total} {statusFilter === 'all' ? 'total' : statusFilter})</p>
        </div>

        <div className="flex items-center gap-3">
          {selectedIds.length > 0 && (
            <Button
              onClick={() => setBulkSavingsOpen(true)}
              variant="outline"
              className="border-amber-300 bg-amber-50 hover:bg-amber-100 text-amber-900 text-xs font-semibold gap-1.5 shadow-2xs"
            >
              <PiggyBank className="w-4 h-4 text-amber-700" />
              Set Savings ({selectedIds.length})
            </Button>
          )}

          <Link href="/employees/new">
            <Button className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2 shadow-sm shadow-teal-600/20">
              <Plus className="w-4 h-4" />
              Add Employee
            </Button>
          </Link>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="flex flex-col sm:flex-row items-center gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
        <div className="relative flex-1 w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
          <Input
            placeholder="Search by name, employee ID, or biometric code..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 text-xs h-10 border-slate-200 focus-visible:ring-teal-500"
          />
        </div>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-10 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-teal-500 w-full sm:w-36"
        >
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="all">All Status</option>
        </select>

        <select
          value={selectedDept}
          onChange={(e) => setSelectedDept(e.target.value)}
          className="h-10 px-3 rounded-md border border-slate-200 bg-white text-xs text-slate-700 focus:outline-hidden focus:ring-2 focus:ring-teal-500 w-full sm:w-48"
        >
          <option value="">All Departments</option>
          {departments.map((d) => (
            <option key={d.id} value={d.id}>{d.name}</option>
          ))}
        </select>
      </div>

      {/* Data Table */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
        {loading ? (
          <div className="p-12 flex flex-col items-center justify-center text-slate-400 space-y-2">
            <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
            <p className="text-xs">Loading employee records...</p>
          </div>
        ) : employees.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[11px]">
                <tr>
                  <th className="p-3.5 pl-4 w-10 text-center">
                    <input
                      type="checkbox"
                      checked={isAllSelected}
                      onChange={handleSelectAll}
                      className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                    />
                  </th>
                  <th className="p-3.5 pl-2">Emp ID</th>
                  <th className="p-3.5">Biometric</th>
                  <th className="p-3.5">Full Name</th>
                  <th className="p-3.5">Department</th>
                  <th className="p-3.5">Designation</th>
                  <th className="p-3.5">Shift</th>
                  <th className="p-3.5 text-right font-mono">Basic (₹)</th>
                  <th className="p-3.5 text-right font-mono">Savings (₹)</th>
                  <th className="p-3.5 text-center">Status</th>
                  <th className="p-3.5 text-right pr-5">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium text-slate-800">
                {employees.map((emp) => {
                  const isSelected = selectedIds.includes(emp.id)
                  const savingsAmt = emp.security_fund_deduction !== undefined && emp.security_fund_deduction !== null
                    ? emp.security_fund_deduction
                    : 0

                  return (
                    <tr
                      key={emp.id}
                      className={`hover:bg-slate-50/80 transition-colors ${isSelected ? 'bg-teal-50/40' : ''}`}
                    >
                      <td className="p-3.5 pl-4 w-10 text-center">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleSelectRow(emp.id)}
                          className="rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                        />
                      </td>
                      <td className="p-3.5 pl-2 font-mono text-slate-600 font-bold">{emp.employee_id}</td>
                      <td className="p-3.5 font-mono text-teal-700 font-semibold">{emp.biometric_code || '—'}</td>
                      <td className="p-3.5">
                        <div className="font-semibold text-slate-900">{emp.full_name}</div>
                        {emp.email && <div className="text-[10px] text-slate-400 font-normal">{emp.email}</div>}
                      </td>
                      <td className="p-3.5">
                        <Badge variant="outline" className="bg-slate-50 text-slate-700 border-slate-200 font-normal">
                          {emp.department_name || 'Unassigned'}
                        </Badge>
                      </td>
                      <td className="p-3.5 text-slate-600">{emp.designation_name || '—'}</td>
                      <td className="p-3.5 font-mono text-slate-500">{emp.shift_code || 'GS'}</td>
                      <td className="p-3.5 text-right font-mono text-slate-900 font-semibold">
                        ₹ {emp.basic_salary ? emp.basic_salary.toLocaleString('en-IN') : '0'}
                      </td>
                      <td className="p-3.5 text-right font-mono text-amber-800 font-bold">
                        ₹ {savingsAmt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="p-3.5 text-center">
                        {emp.is_active ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-100 text-emerald-800">
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600">
                            Inactive
                          </span>
                        )}
                      </td>
                      <td className="p-3.5 text-right pr-5 space-x-1">
                        <Link href={`/employees/${emp.id}`}>
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-teal-600" title="View">
                            <Eye className="w-3.5 h-3.5" />
                          </Button>
                        </Link>
                        <Link href={`/employees/${emp.id}/edit`}>
                          <Button variant="ghost" size="sm" className="h-7 w-7 p-0 text-slate-500 hover:text-teal-600" title="Edit">
                            <Edit className="w-3.5 h-3.5" />
                          </Button>
                        </Link>
                        {emp.is_active ? (
                          <button
                            onClick={() => handleDeactivate(emp.id)}
                            className="h-7 w-7 inline-flex items-center justify-center rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                            title="Deactivate"
                          >
                            <UserX className="w-3.5 h-3.5" />
                          </button>
                        ) : (
                          <button
                            onClick={() => handleReactivate(emp.id)}
                            className="h-7 w-7 inline-flex items-center justify-center rounded-md text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 transition-colors"
                            title="Reactivate"
                          >
                            <UserCheck className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-12 text-center text-slate-400 space-y-2">
            <p className="text-sm font-semibold text-slate-600">No employee records found</p>
            <p className="text-xs">Try adjusting search query or department filter.</p>
          </div>
        )}
        
        {/* Pagination */}
        {!loading && total > 0 && (
          <div className="p-4 border-t border-slate-200 flex items-center justify-between bg-slate-50">
            <p className="text-xs text-slate-500">
              Showing <span className="font-semibold text-slate-900">{(page - 1) * pageSize + 1}</span> to{' '}
              <span className="font-semibold text-slate-900">{Math.min(page * pageSize, total)}</span> of{' '}
              <span className="font-semibold text-slate-900">{total}</span> employees
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

      {/* Bulk Set Savings Fund Modal */}
      <Dialog open={bulkSavingsOpen} onOpenChange={setBulkSavingsOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-bold flex items-center gap-2">
              <PiggyBank className="w-5 h-5 text-teal-600" />
              Bulk Set Savings Fund Deduction
            </DialogTitle>
          </DialogHeader>

          <form onSubmit={handleBulkSetSavings} className="space-y-4 pt-2">
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900">
              You are setting the monthly savings fund deduction for <strong>{selectedIds.length}</strong> selected staff member{selectedIds.length > 1 ? 's' : ''}.
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Monthly Savings Fund Deduction (₹) *</Label>
              <Input
                type="number"
                min="0"
                step="0.01"
                required
                value={bulkSavingsAmount}
                onChange={(e) => setBulkSavingsAmount(e.target.value)}
                placeholder="0 (e.g. 500)"
                className="text-xs h-9 font-mono"
              />
              <p className="text-[11px] text-slate-500">
                Set to <strong>0</strong> if selected staff do not contribute.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setBulkSavingsOpen(false)}
                className="h-8 text-xs"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={submittingBulk}
                className="h-8 text-xs bg-teal-600 hover:bg-teal-700 text-white font-semibold"
              >
                {submittingBulk ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1" /> : <Check className="w-3.5 h-3.5 mr-1" />}
                Apply to {selectedIds.length} Staff
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
