'use client'

import { useEffect, useState } from 'react'
import {
  Users,
  UserPlus,
  Shield,
  Key,
  Mail,
  User as UserIcon,
  CheckCircle2,
  XCircle,
  Edit2,
  Loader2,
  RefreshCw,
  Search,
} from 'lucide-react'
import api from '@/lib/api'
import { getUser } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { toast } from 'sonner'
import type { User, UserRole, Employee } from '@/types'

const ROLE_COLORS: Record<UserRole, string> = {
  SUPER_ADMIN: 'bg-purple-100 text-purple-800 border-purple-200',
  HR_ADMIN: 'bg-teal-100 text-teal-800 border-teal-200',
  DEPT_MANAGER: 'bg-blue-100 text-blue-800 border-blue-200',
  EMPLOYEE: 'bg-slate-100 text-slate-700 border-slate-200',
}

const ROLE_LABELS: Record<UserRole, string> = {
  SUPER_ADMIN: 'Super Admin',
  HR_ADMIN: 'HR Admin',
  DEPT_MANAGER: 'Dept Manager',
  EMPLOYEE: 'Employee',
}

export default function UsersManagementPage() {
  const [currentUser] = useState(() => getUser())
  const [users, setUsers] = useState<User[]>([])
  const [employees, setEmployees] = useState<Employee[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  // Add User Modal State
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [createForm, setCreateForm] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    role: 'HR_ADMIN' as UserRole,
    employee_id: '' as string | number,
    is_active: true,
  })

  // Edit User Modal State
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [editLoading, setEditLoading] = useState(false)
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [editForm, setEditForm] = useState({
    full_name: '',
    email: '',
    role: 'EMPLOYEE' as UserRole,
    password: '',
    is_active: true,
    employee_id: '' as string | number,
  })

  const handleRefresh = async () => {
    setLoading(true)
    try {
      const [usersRes, empRes] = await Promise.all([
        api.get('/users?page_size=100'),
        api.get('/employees?page_size=100').catch(() => ({ data: { items: [] } })),
      ])
      setUsers(usersRes.data.items || [])
      setEmployees(empRes.data.items || [])
    } catch {
      toast.error('Failed to load users. Super Admin access required.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    let ignore = false
    const load = async () => {
      try {
        const [usersRes, empRes] = await Promise.all([
          api.get('/users?page_size=100'),
          api.get('/employees?page_size=100').catch(() => ({ data: { items: [] } })),
        ])
        if (!ignore) {
          setUsers(usersRes.data.items || [])
          setEmployees(empRes.data.items || [])
        }
      } catch {
        if (!ignore) {
          toast.error('Failed to load users. Super Admin access required.')
        }
      } finally {
        if (!ignore) {
          setLoading(false)
        }
      }
    }
    load()
    return () => {
      ignore = true
    }
  }, [])

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!createForm.username || !createForm.email || !createForm.password || !createForm.full_name) {
      toast.error('Please fill in all required fields.')
      return
    }

    if (createForm.password.length < 6) {
      toast.error('Password must be at least 6 characters.')
      return
    }

    setCreateLoading(true)
    try {
      await api.post('/users', {
        username: createForm.username.trim(),
        email: createForm.email.trim(),
        full_name: createForm.full_name.trim(),
        password: createForm.password,
        role: createForm.role,
        is_active: createForm.is_active,
        employee_id: createForm.employee_id ? Number(createForm.employee_id) : null,
      })
      toast.success(`User '${createForm.username}' created successfully!`)
      setCreateModalOpen(false)
      setCreateForm({
        username: '',
        email: '',
        full_name: '',
        password: '',
        role: 'HR_ADMIN',
        employee_id: '',
        is_active: true,
      })
      handleRefresh()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || 'Failed to create user.')
    } finally {
      setCreateLoading(false)
    }
  }

  const handleOpenEdit = (user: User) => {
    setEditingUser(user)
    setEditForm({
      full_name: user.full_name || '',
      email: user.email || '',
      role: user.role,
      password: '',
      is_active: user.is_active,
      employee_id: user.employee_id || '',
    })
    setEditModalOpen(true)
  }

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUser) return

    setEditLoading(true)
    try {
      const payload: Record<string, unknown> = {
        full_name: editForm.full_name.trim(),
        email: editForm.email.trim(),
        role: editForm.role,
        is_active: editForm.is_active,
        employee_id: editForm.employee_id ? Number(editForm.employee_id) : null,
      }
      if (editForm.password && editForm.password.trim().length >= 6) {
        payload.password = editForm.password.trim()
      }

      await api.put(`/users/${editingUser.id}`, payload)
      toast.success(`User '${editingUser.username}' updated successfully!`)
      setEditModalOpen(false)
      setEditingUser(null)
      handleRefresh()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(msg || 'Failed to update user.')
    } finally {
      setEditLoading(false)
    }
  }

  const filteredUsers = users.filter((u) => {
    const q = search.toLowerCase()
    return (
      u.username.toLowerCase().includes(q) ||
      u.full_name.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      u.role.toLowerCase().includes(q)
    )
  })

  const isSuperAdmin = currentUser?.role === 'SUPER_ADMIN'

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">User Management</h1>
            <Badge variant="outline" className="text-[11px] font-semibold bg-purple-50 text-purple-700 border-purple-200">
              Super Admin Only
            </Badge>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Provision hospital staff accounts, manage administrative roles, and assign employee profiles.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={loading}
            className="text-xs h-9"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button
            onClick={() => setCreateModalOpen(true)}
            disabled={!isSuperAdmin}
            className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9 shadow-xs"
          >
            <UserPlus className="w-4 h-4 mr-1.5" />
            Add New User
          </Button>
        </div>
      </div>

      {!isSuperAdmin && (
        <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-3">
          <Shield className="w-5 h-5 text-amber-600 shrink-0" />
          <div>
            <p className="font-semibold">Restricted Access Notice</p>
            <p className="mt-0.5 text-amber-700">
              User creation and credential management is strictly restricted to Super Administrators to protect hospital HR records.
            </p>
          </div>
        </div>
      )}

      {/* Search Bar */}
      <div className="flex items-center gap-3 bg-white p-3.5 rounded-xl border border-slate-200 shadow-2xs">
        <Search className="w-4 h-4 text-slate-400 ml-1" />
        <Input
          placeholder="Search users by name, username, email, or role..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border-0 shadow-none focus-visible:ring-0 text-xs h-8 p-0 placeholder:text-slate-400"
        />
        {search && (
          <Button variant="ghost" size="sm" onClick={() => setSearch('')} className="text-xs h-7 px-2">
            Clear
          </Button>
        )}
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-700">
            <thead className="bg-slate-50/80 text-[11px] font-bold text-slate-500 uppercase tracking-wider border-b border-slate-200">
              <tr>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Email</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Linked Employee</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Last Login</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-teal-600" />
                    Loading users...
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-400">
                    <Users className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                    No users found matching your search.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => {
                  const linkedEmp = employees.find((e) => e.id === u.employee_id)
                  return (
                    <tr key={u.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-teal-50 border border-teal-200 text-teal-700 font-bold flex items-center justify-center text-xs">
                            {u.full_name ? u.full_name.charAt(0).toUpperCase() : u.username.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="font-semibold text-slate-900">{u.full_name || u.username}</p>
                            <p className="text-[11px] text-slate-400 font-mono">@{u.username}</p>
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-slate-600">{u.email}</td>
                      <td className="py-3 px-4">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold border ${ROLE_COLORS[u.role] || 'bg-slate-100 text-slate-700 border-slate-200'}`}>
                          {ROLE_LABELS[u.role] || u.role}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-slate-600">
                        {linkedEmp ? (
                          <span className="font-medium text-slate-800">
                            {linkedEmp.first_name} {linkedEmp.last_name || ''} ({linkedEmp.employee_id})
                          </span>
                        ) : (
                          <span className="text-slate-400 italic">None</span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        {u.is_active ? (
                          <span className="inline-flex items-center gap-1.5 text-emerald-700 text-xs font-medium">
                            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                            Active
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 text-slate-400 text-xs font-medium">
                            <XCircle className="w-3.5 h-3.5 text-slate-400" />
                            Deactivated
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                        {u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={!isSuperAdmin}
                          onClick={() => handleOpenEdit(u)}
                          className="h-8 px-2 text-xs text-slate-600 hover:text-teal-700 hover:bg-teal-50"
                        >
                          <Edit2 className="w-3.5 h-3.5 mr-1" />
                          Edit
                        </Button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modal: Create User */}
      <Dialog open={createModalOpen} onOpenChange={setCreateModalOpen}>
        <DialogContent className="max-w-md bg-white">
          <DialogHeader>
            <DialogTitle className="text-base font-bold flex items-center gap-2 text-slate-900">
              <UserPlus className="w-5 h-5 text-teal-600" />
              Add New Hospital User
            </DialogTitle>
          </DialogHeader>

          <form onSubmit={handleCreateUser} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Full Name *</Label>
              <div className="relative">
                <UserIcon className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <Input
                  required
                  placeholder="e.g. Dr. Ramesh Kumar"
                  value={createForm.full_name}
                  onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                  className="pl-9 text-xs h-9"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Username *</Label>
                <Input
                  required
                  placeholder="e.g. ramesh"
                  value={createForm.username}
                  onChange={(e) => setCreateForm({ ...createForm, username: e.target.value.toLowerCase().trim() })}
                  className="text-xs h-9 font-mono"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Initial Password *</Label>
                <div className="relative">
                  <Key className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                  <Input
                    required
                    type="password"
                    placeholder="Min. 6 chars"
                    value={createForm.password}
                    onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                    className="pl-9 text-xs h-9 font-mono"
                  />
                </div>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Email Address *</Label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                <Input
                  required
                  type="email"
                  placeholder="ramesh@spthospital.com"
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value.trim() })}
                  className="pl-9 text-xs h-9"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">System Role *</Label>
                <select
                  value={createForm.role}
                  onChange={(e) => setCreateForm({ ...createForm, role: e.target.value as UserRole })}
                  className="w-full text-xs h-9 px-3 rounded-md border border-slate-200 bg-white text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                >
                  <option value="HR_ADMIN">HR Administrator</option>
                  <option value="DEPT_MANAGER">Department Manager</option>
                  <option value="EMPLOYEE">Employee (Portal Access)</option>
                  <option value="SUPER_ADMIN">Super Administrator</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Link to Employee (Optional)</Label>
                <select
                  value={createForm.employee_id}
                  onChange={(e) => setCreateForm({ ...createForm, employee_id: e.target.value })}
                  className="w-full text-xs h-9 px-3 rounded-md border border-slate-200 bg-white text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                >
                  <option value="">None (Standalone)</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.first_name} {emp.last_name || ''} ({emp.employee_id})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="create-is-active"
                checked={createForm.is_active}
                onChange={(e) => setCreateForm({ ...createForm, is_active: e.target.checked })}
                className="w-4 h-4 text-teal-600 rounded border-slate-300 focus:ring-teal-500"
              />
              <Label htmlFor="create-is-active" className="text-xs font-medium text-slate-700 cursor-pointer">
                Account Active (Can log in immediately)
              </Label>
            </div>

            <DialogFooter className="pt-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => setCreateModalOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={createLoading}
                className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9"
              >
                {createLoading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : null}
                Create Account
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Modal: Edit User */}
      <Dialog open={editModalOpen} onOpenChange={setEditModalOpen}>
        <DialogContent className="max-w-md bg-white">
          <DialogHeader>
            <DialogTitle className="text-base font-bold flex items-center gap-2 text-slate-900">
              <Edit2 className="w-5 h-5 text-teal-600" />
              Edit User: @{editingUser?.username}
            </DialogTitle>
          </DialogHeader>

          <form onSubmit={handleUpdateUser} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Full Name *</Label>
              <Input
                required
                value={editForm.full_name}
                onChange={(e) => setEditForm({ ...editForm, full_name: e.target.value })}
                className="text-xs h-9"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Email Address *</Label>
              <Input
                required
                type="email"
                value={editForm.email}
                onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                className="text-xs h-9"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Role *</Label>
                <select
                  value={editForm.role}
                  onChange={(e) => setEditForm({ ...editForm, role: e.target.value as UserRole })}
                  className="w-full text-xs h-9 px-3 rounded-md border border-slate-200 bg-white text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                >
                  <option value="HR_ADMIN">HR Administrator</option>
                  <option value="DEPT_MANAGER">Department Manager</option>
                  <option value="EMPLOYEE">Employee (Portal Access)</option>
                  <option value="SUPER_ADMIN">Super Administrator</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Linked Employee</Label>
                <select
                  value={editForm.employee_id}
                  onChange={(e) => setEditForm({ ...editForm, employee_id: e.target.value })}
                  className="w-full text-xs h-9 px-3 rounded-md border border-slate-200 bg-white text-slate-800 focus:outline-hidden focus:ring-2 focus:ring-teal-500"
                >
                  <option value="">None (Standalone)</option>
                  {employees.map((emp) => (
                    <option key={emp.id} value={emp.id}>
                      {emp.first_name} {emp.last_name || ''} ({emp.employee_id})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Reset Password (leave blank to keep current)</Label>
              <Input
                type="password"
                placeholder="Enter new password (min. 6 chars)"
                value={editForm.password}
                onChange={(e) => setEditForm({ ...editForm, password: e.target.value })}
                className="text-xs h-9 font-mono"
              />
            </div>

            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="edit-is-active"
                checked={editForm.is_active}
                onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                className="w-4 h-4 text-teal-600 rounded border-slate-300 focus:ring-teal-500"
              />
              <Label htmlFor="edit-is-active" className="text-xs font-medium text-slate-700 cursor-pointer">
                Account Active (Can log in)
              </Label>
            </div>

            <DialogFooter className="pt-3">
              <Button
                type="button"
                variant="outline"
                onClick={() => setEditModalOpen(false)}
                className="text-xs h-9"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={editLoading}
                className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9"
              >
                {editLoading ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : null}
                Save Changes
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
