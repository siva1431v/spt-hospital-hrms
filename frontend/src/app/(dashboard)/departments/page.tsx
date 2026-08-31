'use client'

import { useEffect, useState } from 'react'
import { Plus, Building2, Trash2, Edit, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { Department } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([])
  const [loading, setLoading] = useState(true)
  const [showDialog, setShowDialog] = useState(false)
  const [editingDept, setEditingDept] = useState<Department | null>(null)
  const [deletingDept, setDeletingDept] = useState<Department | null>(null)
  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [description, setDescription] = useState('')

  const fetchDepartments = async () => {
    setLoading(true)
    try {
      const res = await api.get('/departments')
      setDepartments(res.data.items || [])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDepartments()
  }, [])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editingDept) {
        await api.put(`/departments/${editingDept.id}`, { name, code: code.toUpperCase(), description })
      } else {
        await api.post('/departments', { name, code: code.toUpperCase(), description })
      }
      closeDialog()
      fetchDepartments()
    } catch (err: any) {
      alert(err.response?.data?.detail || `Failed to ${editingDept ? 'update' : 'create'} department.`)
    }
  }

  const handleDelete = async () => {
    if (!deletingDept) return
    try {
      await api.delete(`/departments/${deletingDept.id}`)
      setDeletingDept(null)
      fetchDepartments()
    } catch (err: any) {
      if (err.response?.status === 409) {
        alert('Cannot delete this department because it is currently in use by employees or shifts.')
      } else {
        alert(err.response?.data?.detail || 'Failed to delete department.')
      }
      setDeletingDept(null)
    }
  }

  const openEdit = (dept: Department) => {
    setEditingDept(dept)
    setName(dept.name)
    setCode(dept.code)
    setDescription(dept.description || '')
    setShowDialog(true)
  }

  const closeDialog = () => {
    setShowDialog(false)
    setEditingDept(null)
    setName('')
    setCode('')
    setDescription('')
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Hospital Departments</h1>
          <p className="text-xs text-slate-500 mt-1">Manage medical & administrative units ({departments.length})</p>
        </div>

        <Button
          onClick={() => setShowDialog(true)}
          className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Department
        </Button>
      </div>

      {/* Modal Dialog */}
      {showDialog && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900">{editingDept ? 'Edit Department' : 'Create New Department'}</h2>

            <form onSubmit={handleSave} className="space-y-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Department Name *</Label>
                <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. ICU & Critical Care" className="text-xs h-9" />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Department Code *</Label>
                <Input required value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. ICU" className="text-xs h-9 uppercase font-mono" />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Description</Label>
                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" className="text-xs h-9" />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={closeDialog} className="text-xs h-9">
                  Cancel
                </Button>
                <Button type="submit" className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9">
                  {editingDept ? 'Save Changes' : 'Create Department'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Dialog */}
      {deletingDept && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900">Delete Department</h2>
            <p className="text-sm text-slate-600">
              Are you sure you want to delete <strong>{deletingDept.name}</strong>? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setDeletingDept(null)} className="text-xs h-9">
                Cancel
              </Button>
              <Button type="button" onClick={handleDelete} className="bg-rose-600 hover:bg-rose-700 text-white text-xs h-9">
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Grid of Departments */}
      {loading ? (
        <div className="p-12 flex justify-center text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {departments.map((dept) => (
            <div key={dept.id} className="bg-white p-5 rounded-xl border border-slate-200 space-y-3 shadow-2xs hover:shadow-md transition-all">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-teal-50 text-teal-700 border border-teal-100">
                    <Building2 className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">{dept.name}</h3>
                    <span className="text-[10px] font-mono font-bold bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                      CODE: {dept.code}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => openEdit(dept)} className="p-1.5 text-slate-400 hover:text-teal-600 hover:bg-teal-50 rounded-md transition-colors" title="Edit">
                    <Edit className="w-4 h-4" />
                  </button>
                  <button onClick={() => setDeletingDept(dept)} className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors" title="Delete">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <p className="text-xs text-slate-500 line-clamp-2">
                {dept.description || 'Standard SPT Hospital department unit.'}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
