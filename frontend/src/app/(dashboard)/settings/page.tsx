'use client'

import { useEffect, useState } from 'react'
import { Settings as SettingsIcon, Save, Building, Clock, IndianRupee, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'

export default function SettingsPage() {
  const [hospitalName, setHospitalName] = useState('SPT Hospital')
  const [gracePeriod, setGracePeriod] = useState('5')
  const [lopThreshold, setLopThreshold] = useState('3')
  const [paidLeaveCap, setPaidLeaveCap] = useState('3')
  const [saving, setSaving] = useState(false)

  const fetchSettings = async () => {
    try {
      const res = await api.get('/settings')
      const general = res.data.settings?.GENERAL || []
      const att = res.data.settings?.ATTENDANCE || []
      const payroll = res.data.settings?.PAYROLL || []

      general.forEach((s: any) => {
        if (s.key === 'hospital_name') setHospitalName(s.value)
      })
      att.forEach((s: any) => {
        if (s.key === 'attendance_grace_period') setGracePeriod(s.value)
      })
      payroll.forEach((s: any) => {
        if (s.key === 'lop_late_threshold_days') setLopThreshold(s.value)
        if (s.key === 'paid_leave_monthly_cap') setPaidLeaveCap(s.value)
      })
    } catch (err) {
      console.error(err)
    }
  }

  useEffect(() => {
    fetchSettings()
  }, [])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      await api.put('/settings', {
        updates: {
          hospital_name: hospitalName,
          attendance_grace_period: gracePeriod,
          lop_late_threshold_days: lopThreshold,
          paid_leave_monthly_cap: paidLeaveCap,
        },
      })
      toast.success('System settings updated successfully!')
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save settings.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="border-b border-slate-200/80 pb-5">
        <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">System Settings</h1>
        <p className="text-xs text-slate-500 mt-1">Configure global hospital HRMS parameters, attendance thresholds, and payroll rules</p>
      </div>

      <form onSubmit={handleSave} className="bg-white p-6 rounded-xl border border-slate-200 space-y-6 shadow-xs">
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2 flex items-center gap-2">
            <Building className="w-4 h-4 text-teal-600" />
            Hospital Information
          </h2>

          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">Hospital Name</Label>
            <Input value={hospitalName} onChange={(e) => setHospitalName(e.target.value)} className="text-xs h-9" />
          </div>
        </div>

        <div className="space-y-4 pt-2">
          <h2 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2 flex items-center gap-2">
            <Clock className="w-4 h-4 text-teal-600" />
            Attendance & Lateness Rules
          </h2>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Default Grace Period (Minutes)</Label>
              <Input type="number" value={gracePeriod} onChange={(e) => setGracePeriod(e.target.value)} className="text-xs h-9 font-mono" />
              <span className="text-[10px] text-slate-400">Punches beyond this duration are flagged as qualifying late arrivals.</span>
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">LOP Late Threshold (Days)</Label>
              <Input type="number" value={lopThreshold} onChange={(e) => setLopThreshold(e.target.value)} className="text-xs h-9 font-mono" />
              <span className="text-[10px] text-slate-400">Every 3 qualifying late arrivals in a month trigger 1 day Loss of Pay (LOP).</span>
            </div>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded p-2.5">
            <p className="text-[11px] text-amber-900 font-medium leading-relaxed flex items-start gap-1.5">
              <span className="text-amber-600 mt-0.5">⚠️</span>
              Changing the default grace period applies to newly imported records. To update existing draft or under-review payroll periods, recalculate payroll on the Monthly Payroll page. Finalized periods are locked and will not be altered.
            </p>
          </div>
        </div>

        <div className="space-y-4 pt-2">
          <h2 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2 flex items-center gap-2">
            <IndianRupee className="w-4 h-4 text-teal-600" />
            Payroll & Leave Rules
          </h2>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold flex items-center gap-1.5">
                Max Paid Leave Cap (Days / Month)
              </Label>
              <Input type="number" value={paidLeaveCap} onChange={(e) => setPaidLeaveCap(e.target.value)} className="text-xs h-9 font-mono" />
              <div className="bg-blue-50 border border-blue-100 rounded p-2 mt-2">
                <p className="text-[10px] text-blue-800 font-medium leading-relaxed flex items-start gap-1.5">
                  <span className="text-blue-500 mt-0.5">ℹ</span>
                  This is the single source of truth for paid leave caps. The same value is enforced in payroll calculation and leave approval.
                </p>
              </div>
            </div>

            <div className="space-y-1.5 bg-slate-50 p-3 rounded-lg border border-slate-200">
              <Label className="text-xs font-semibold text-slate-700">Salary Calculation Divisor</Label>
              <p className="text-xs font-bold text-teal-700 mt-1">Exact Calendar Month Days</p>
              <span className="text-[10px] text-slate-500 block mt-0.5">August: 31 days · September: 30 days · February: 28/29 days.</span>
            </div>
          </div>
        </div>

        <div className="flex justify-end pt-4 border-t border-slate-100">
          <Button type="submit" disabled={saving} className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold h-9 px-5">
            {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-1.5" />}
            Save Settings
          </Button>
        </div>
      </form>
    </div>
  )
}
