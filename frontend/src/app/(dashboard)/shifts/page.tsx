'use client'

import { useEffect, useState } from 'react'
import { Plus, Moon, Sun, Loader2, Trash2, Edit, ArrowLeftRight } from 'lucide-react'
import api from '@/lib/api'
import { Shift } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface ShiftAlias {
  id?: number
  device_code: string
  shift_id: number
  shift_name?: string
  shift_code?: string
  shift?: Shift
  created_at?: string
}

export default function ShiftsPage() {
  const [shifts, setShifts] = useState<Shift[]>([])
  const [aliases, setAliases] = useState<ShiftAlias[]>([])
  const [loading, setLoading] = useState(true)
  const [showDialog, setShowDialog] = useState(false)
  const [showAliasDialog, setShowAliasDialog] = useState(false)
  const [newDeviceCode, setNewDeviceCode] = useState('')
  const [newAliasShiftId, setNewAliasShiftId] = useState<number | ''>('')
  
  const [editingShift, setEditingShift] = useState<Shift | null>(null)
  const [deletingShift, setDeletingShift] = useState<Shift | null>(null)

  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [startTime, setStartTime] = useState('09:00')
  const [endTime, setEndTime] = useState('17:00')
  const [isOvernight, setIsOvernight] = useState(false)
  const [gracePeriod, setGracePeriod] = useState(5)
  
  const [isSplit, setIsSplit] = useState(false)
  const [startTime2, setStartTime2] = useState('13:00')
  const [endTime2, setEndTime2] = useState('17:00')
  const [refreshTrigger, setRefreshTrigger] = useState(0)

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const [shiftRes, aliasRes] = await Promise.allSettled([
          api.get('/shifts'),
          api.get('/shifts/aliases'),
        ])
        if (active) {
          if (shiftRes.status === 'fulfilled') setShifts(shiftRes.value.data.items || [])
          if (aliasRes.status === 'fulfilled') setAliases(aliasRes.value.data.items || [])
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
  }, [refreshTrigger])

  const refreshShiftsAndAliases = () => {
    setRefreshTrigger((n) => n + 1)
  }

  const handleCreateAlias = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newDeviceCode || !newAliasShiftId) return
    try {
      await api.post('/shifts/aliases', {
        device_code: newDeviceCode.toUpperCase().trim(),
        shift_id: Number(newAliasShiftId),
      })
      setShowAliasDialog(false)
      setNewDeviceCode('')
      setNewAliasShiftId('')
      refreshShiftsAndAliases()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || 'Failed to create shift alias.')
    }
  }

  const handleDeleteAlias = async (aliasId: number) => {
    try {
      await api.delete(`/shifts/aliases/${aliasId}`)
      refreshShiftsAndAliases()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || 'Failed to delete shift alias.')
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const payload = {
        name,
        code: code.toUpperCase(),
        start_time: startTime,
        end_time: endTime,
        is_overnight: isOvernight,
        grace_period_minutes: Number(gracePeriod),
        is_split: isSplit,
        start_time_2: isSplit ? startTime2 : null,
        end_time_2: isSplit ? endTime2 : null,
      }
      
      if (editingShift) {
        await api.put(`/shifts/${editingShift.id}`, payload)
      } else {
        await api.post('/shifts', payload)
      }
      closeDialog()
      refreshShiftsAndAliases()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg || `Failed to ${editingShift ? 'update' : 'create'} shift.`)
    }
  }

  const handleDelete = async () => {
    if (!deletingShift) return
    try {
      await api.delete(`/shifts/${deletingShift.id}`)
      setDeletingShift(null)
      refreshShiftsAndAliases()
    } catch (err: unknown) {
      const axErr = err as { response?: { status?: number; data?: { detail?: string } } }
      if (axErr.response?.status === 409) {
        alert('Cannot delete this shift because it is currently assigned to employees.')
      } else {
        alert(axErr.response?.data?.detail || 'Failed to delete shift.')
      }
      setDeletingShift(null)
    }
  }

  const openEdit = (shift: Shift) => {
    setEditingShift(shift)
    setName(shift.name)
    setCode(shift.code)
    setStartTime(shift.start_time)
    setEndTime(shift.end_time)
    setIsOvernight(shift.is_overnight)
    setGracePeriod(shift.grace_period_minutes)
    setIsSplit(shift.is_split || false)
    if (shift.start_time_2) setStartTime2(shift.start_time_2)
    if (shift.end_time_2) setEndTime2(shift.end_time_2)
    setShowDialog(true)
  }

  const closeDialog = () => {
    setShowDialog(false)
    setEditingShift(null)
    setName('')
    setCode('')
    setStartTime('09:00')
    setEndTime('17:00')
    setIsOvernight(false)
    setGracePeriod(5)
    setIsSplit(false)
    setStartTime2('13:00')
    setEndTime2('17:00')
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between border-b border-slate-200/80 pb-5">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Shift Timings & Rules</h1>
          <p className="text-xs text-slate-500 mt-1">Configure morning, evening, and overnight hospital shift rules ({shifts.length})</p>
        </div>

        <Button
          onClick={() => setShowDialog(true)}
          className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Shift Rule
        </Button>
      </div>

      {showDialog && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900">{editingShift ? 'Edit Shift Rule' : 'Configure New Shift Rule'}</h2>

            <form onSubmit={handleSave} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Shift Name *</Label>
                  <Input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Night Time Shift" className="text-xs h-9" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Shift Code *</Label>
                  <Input required value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. NTS" className="text-xs h-9 uppercase font-mono" />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">Start Time (HH:MM) *</Label>
                  <Input type="time" required value={startTime} onChange={(e) => setStartTime(e.target.value)} className="text-xs h-9" />
                </div>
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold">End Time (HH:MM) *</Label>
                  <Input type="time" required value={endTime} onChange={(e) => setEndTime(e.target.value)} className="text-xs h-9" />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="overnight"
                  checked={isOvernight}
                  onChange={(e) => setIsOvernight(e.target.checked)}
                  className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 h-4 w-4"
                />
                <Label htmlFor="overnight" className="text-xs font-medium cursor-pointer">
                  Is Overnight Shift? (e.g. 22:00 to 06:00 next morning)
                </Label>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <input
                  type="checkbox"
                  id="split"
                  checked={isSplit}
                  onChange={(e) => setIsSplit(e.target.checked)}
                  className="rounded border-slate-300 text-teal-600 focus:ring-teal-500 h-4 w-4"
                />
                <Label htmlFor="split" className="text-xs font-medium cursor-pointer">
                  Is Split Shift? (Requires Window 2)
                </Label>
              </div>

              {isSplit && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-semibold">Start Time 2 (HH:MM) *</Label>
                    <Input type="time" required value={startTime2} onChange={(e) => setStartTime2(e.target.value)} className="text-xs h-9" />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-semibold">End Time 2 (HH:MM) *</Label>
                    <Input type="time" required value={endTime2} onChange={(e) => setEndTime2(e.target.value)} className="text-xs h-9" />
                  </div>
                </div>
              )}

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Grace Period (Minutes)</Label>
                <Input type="number" value={gracePeriod} onChange={(e) => setGracePeriod(Number(e.target.value))} className="text-xs h-9" />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={closeDialog} className="text-xs h-9">
                  Cancel
                </Button>
                <Button type="submit" className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9">
                  {editingShift ? 'Save Changes' : 'Save Shift Rule'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deletingShift && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-md w-full p-6 space-y-4 shadow-xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900">Delete Shift Rule</h2>
            <p className="text-sm text-slate-600">
              Are you sure you want to delete <strong>{deletingShift.name}</strong>? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" onClick={() => setDeletingShift(null)} className="text-xs h-9">
                Cancel
              </Button>
              <Button type="button" onClick={handleDelete} className="bg-rose-600 hover:bg-rose-700 text-white text-xs h-9">
                Delete
              </Button>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <div className="p-12 flex justify-center text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {shifts.map((shift) => (
            <div key={shift.id} className="bg-white p-5 rounded-xl border border-slate-200 space-y-3 shadow-2xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`p-2.5 rounded-lg border ${shift.is_split ? 'bg-blue-50 text-blue-700 border-blue-200' : shift.is_overnight ? 'bg-purple-50 text-purple-700 border-purple-200' : 'bg-amber-50 text-amber-700 border-amber-200'}`}>
                    {shift.is_split ? <ArrowLeftRight className="w-5 h-5" /> : shift.is_overnight ? <Moon className="w-5 h-5" /> : <Sun className="w-5 h-5" />}
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">{shift.name}</h3>
                    <span className="text-[10px] font-mono font-bold bg-slate-100 px-1.5 py-0.5 rounded text-slate-600">
                      CODE: {shift.code}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {shift.is_overnight && (
                    <span className="text-[10px] font-semibold bg-purple-100 text-purple-800 px-2 py-0.5 rounded-full">
                      Overnight
                    </span>
                  )}
                  <div className="flex items-center gap-1">
                    <button onClick={() => openEdit(shift)} className="p-1.5 text-slate-400 hover:text-teal-600 hover:bg-teal-50 rounded-md transition-colors" title="Edit">
                      <Edit className="w-4 h-4" />
                    </button>
                    <button onClick={() => setDeletingShift(shift)} className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors" title="Delete">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-100 flex flex-col gap-1.5 text-xs text-slate-600">
                <div className="flex items-center justify-between">
                  <span>{shift.is_split ? 'Window 1 (Day):' : 'Shift Hours:'} <strong className="text-slate-900 font-mono">{shift.start_time} — {shift.end_time}</strong></span>
                  <span className="text-[11px] text-slate-400">Grace: {shift.grace_period_minutes}m</span>
                </div>
                {shift.is_split && shift.start_time_2 && (
                  <div className="flex items-center justify-between text-teal-900 font-medium bg-teal-50 px-2 py-1 rounded border border-teal-100">
                    <span>Window 2 (Night): <strong className="font-mono">{shift.start_time_2} — {shift.end_time_2}</strong></span>
                    <span className="text-[10px] bg-teal-200 text-teal-900 px-1.5 py-0.5 rounded font-bold">Split</span>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* SECTION: Device Shift Code Aliases */}
      <div className="pt-6 border-t border-slate-200 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-slate-900">eSSL Device Shift Code Mappings ({aliases.length})</h2>
            <p className="text-xs text-slate-500">Map punch clock device shift codes (e.g. NS, MS, HKN, NTS) to canonical shifts above</p>
          </div>
          <Button
            size="sm"
            onClick={() => setShowAliasDialog(true)}
            className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-1.5 h-8"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Device Code Alias
          </Button>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-2xs">
          {aliases.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold uppercase text-[10px]">
                  <tr>
                    <th className="p-3 pl-4">Device Code</th>
                    <th className="p-3">Mapped System Shift</th>
                    <th className="p-3">Shift Code</th>
                    <th className="p-3 text-right pr-4">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 font-medium">
                  {aliases.map((alias) => (
                    <tr key={alias.id} className="hover:bg-slate-50/50">
                      <td className="p-3 pl-4 font-mono font-bold text-teal-800 bg-teal-50/40">{alias.device_code}</td>
                      <td className="p-3 font-semibold text-slate-900">{alias.shift_name || '—'}</td>
                      <td className="p-3 font-mono text-slate-600">{alias.shift_code || '—'}</td>
                      <td className="p-3 text-right pr-4">
                        <button
                          onClick={() => alias.id && handleDeleteAlias(alias.id)}
                          className="p-1 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-md transition-colors"
                          title="Delete Alias"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8 text-center text-xs text-slate-400">
              No device shift code aliases created yet. Standard shift codes match directly.
            </div>
          )}
        </div>
      </div>

      {/* Alias Modal Dialog */}
      {showAliasDialog && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl max-w-sm w-full p-5 space-y-4 shadow-xl border border-slate-200">
            <h2 className="text-base font-bold text-slate-900">Add Device Code Alias</h2>
            <form onSubmit={handleCreateAlias} className="space-y-3 text-xs">
              <div className="space-y-1">
                <Label className="text-xs font-semibold">eSSL Device Shift Code *</Label>
                <Input
                  required
                  placeholder="e.g. HKN"
                  value={newDeviceCode}
                  onChange={(e) => setNewDeviceCode(e.target.value)}
                  className="text-xs h-9 uppercase font-mono"
                />
              </div>

              <div className="space-y-1">
                <Label className="text-xs font-semibold">Map to System Shift *</Label>
                <select
                  required
                  value={newAliasShiftId}
                  onChange={(e) => setNewAliasShiftId(Number(e.target.value))}
                  className="h-9 px-2.5 rounded-md border border-slate-200 bg-white text-xs text-slate-700 w-full"
                >
                  <option value="">-- Select Shift --</option>
                  {shifts.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name} ({s.code}: {s.start_time}–{s.end_time})
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setShowAliasDialog(false)} className="text-xs h-8">
                  Cancel
                </Button>
                <Button type="submit" className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-8">
                  Create Alias
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
