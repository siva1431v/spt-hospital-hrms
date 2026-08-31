'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Edit, Loader2, Plus, Minus, PiggyBank } from 'lucide-react'
import api from '@/lib/api'
import { Employee } from '@/types'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'sonner'

export default function EmployeeDetailPage() {
  const params = useParams()
  const id = params?.id
  const [employee, setEmployee] = useState<Employee | null>(null)
  const [loading, setLoading] = useState(true)
  const [txDialogOpen, setTxDialogOpen] = useState(false)
  const [txType, setTxType] = useState<'DEPOSIT' | 'WITHDRAWAL' | 'SETTLEMENT'>('DEPOSIT')
  const [amount, setAmount] = useState('')
  const [notes, setNotes] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const fetchEmployee = () => {
    if (id) {
      api.get(`/employees/${id}`)
        .then((res) => setEmployee(res.data))
        .catch((err) => console.error(err))
        .finally(() => setLoading(false))
    }
  }

  useEffect(() => {
    fetchEmployee()
  }, [id])

  const handleOpenTransaction = (type: 'DEPOSIT' | 'WITHDRAWAL' | 'SETTLEMENT') => {
    setTxType(type)
    if (type === 'SETTLEMENT') {
      const bal = (employee as any)?.accumulated_security_fund || 0
      setAmount(bal > 0 ? String(bal) : '')
      setNotes('Full resignation settlement payout')
    } else {
      setAmount('')
      setNotes('')
    }
    setTxDialogOpen(true)
  }

  const handleTransactionSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const val = parseFloat(amount)
    if (!amount || val <= 0) {
      toast.error('Please enter a valid amount')
      return
    }
    const currentBal = (employee as any)?.accumulated_security_fund || 0
    if ((txType === 'WITHDRAWAL' || txType === 'SETTLEMENT') && val > currentBal) {
      toast.error(`Insufficient balance. Current accumulated fund is ₹${currentBal.toLocaleString('en-IN')}`)
      return
    }

    setSubmitting(true)
    try {
      await api.post(`/employees/${id}/savings-fund/transactions`, {
        transaction_type: txType,
        amount: val,
        notes: notes || undefined,
      })
      toast.success(`Savings Fund ${txType.toLowerCase()} of ₹${val.toLocaleString('en-IN')} recorded successfully!`)
      setTxDialogOpen(false)
      setAmount('')
      setNotes('')
      fetchEmployee()
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to record transaction')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="p-12 flex justify-center text-slate-400">
        <Loader2 className="w-6 h-6 animate-spin text-teal-600" />
      </div>
    )
  }

  if (!employee) {
    return (
      <div className="p-12 text-center text-slate-500">
        Employee record not found.
      </div>
    )
  }

  const accumulatedBal = (employee as any)?.accumulated_security_fund || 0

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/employees">
            <Button variant="outline" size="sm" className="h-8 w-8 p-0">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div>
            <h1 className="text-xl font-bold text-slate-900">{employee.full_name}</h1>
            <p className="text-xs text-slate-500">Employee ID: {employee.employee_id} • Biometric Code: {employee.biometric_code || 'None'}</p>
          </div>
        </div>
        <Link href={`/employees/${id}/edit`}>
          <Button className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2">
            <Edit className="w-3.5 h-3.5" />
            Edit Profile
          </Button>
        </Link>
      </div>

      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-6">
        <div className="flex items-center gap-4 border-b border-slate-100 pb-4">
          <div className="w-14 h-14 rounded-full bg-teal-100 border border-teal-200 text-teal-800 flex items-center justify-center font-bold text-lg">
            {employee.first_name?.[0] || ''}{employee.last_name?.[0] || ''}
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-900">{employee.full_name}</h2>
            <div className="flex items-center gap-2 mt-1">
              <Badge variant="outline" className="bg-slate-50 text-slate-700">
                {employee.department_name || 'No Dept'}
              </Badge>
              <Badge variant="outline" className="bg-slate-50 text-slate-700">
                {employee.designation_name || 'Staff'}
              </Badge>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 text-xs">
          <div className="space-y-3">
            <h3 className="font-bold text-slate-900 uppercase tracking-wider text-[11px]">Employment Details</h3>
            <div className="space-y-1.5 text-slate-600">
              <p>Shift: <strong className="text-slate-900">{employee.shift_code || 'GS'}</strong></p>
              <p>Employment Type: <strong className="text-slate-900">{employee.employment_type}</strong></p>
              <p>Joining Date: <strong className="text-slate-900">{employee.joining_date || '—'}</strong></p>
              <p>Status: <strong className={employee.is_active ? 'text-emerald-700' : 'text-slate-500'}>{employee.is_active ? 'Active' : 'Inactive'}</strong></p>
            </div>
          </div>

          <div className="space-y-3 bg-slate-50 p-4 rounded-lg border border-slate-200">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-slate-900 uppercase tracking-wider text-[11px] flex items-center gap-1.5">
                <PiggyBank className="w-4 h-4 text-emerald-600" /> Salary & Savings Fund
              </h3>
              <div className="flex items-center gap-1">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleOpenTransaction('DEPOSIT')}
                  className="h-6 px-2 text-[10px] text-teal-700 border-teal-200 hover:bg-teal-50 gap-1 font-semibold"
                >
                  <Plus className="w-3 h-3" /> Deposit
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleOpenTransaction('WITHDRAWAL')}
                  className="h-6 px-2 text-[10px] text-rose-700 border-rose-200 hover:bg-rose-50 gap-1 font-semibold"
                >
                  <Minus className="w-3 h-3" /> Payout
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleOpenTransaction('SETTLEMENT')}
                  className="h-6 px-2 text-[10px] text-amber-700 border-amber-200 hover:bg-amber-50 gap-1 font-semibold"
                >
                  Settlement
                </Button>
              </div>
            </div>

            <div className="space-y-1.5 text-slate-600 pt-1">
              <p>Basic Salary: <strong className="text-slate-900 font-mono">₹ {employee.basic_salary?.toLocaleString('en-IN') || 0}</strong></p>
              <p>Monthly Savings Fund Deduction: <strong className="text-amber-800 font-mono">₹ {(employee.security_fund_deduction !== undefined && employee.security_fund_deduction !== null ? employee.security_fund_deduction : 0)?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></p>
              <div className="bg-white p-2.5 rounded border border-emerald-200 mt-2">
                <span className="text-[10px] text-slate-500 block uppercase font-semibold">Total Accumulated Savings Balance</span>
                <span className="text-lg font-extrabold text-emerald-700 font-mono">₹ {accumulatedBal.toLocaleString('en-IN')}</span>
                <span className="text-[10px] text-slate-400 block mt-0.5">Payable to employee on request or upon resignation.</span>
              </div>
              <p className="pt-2">Bank Name: <strong className="text-slate-900">{employee.bank_name || '—'}</strong></p>
              <p>Account No: <strong className="text-slate-900 font-mono">{employee.account_number || employee.bank_account_number || '—'}</strong></p>
              <p>IFSC: <strong className="text-slate-900 font-mono">{employee.ifsc_code || employee.bank_ifsc || '—'}</strong></p>
            </div>
          </div>
        </div>
      </div>

      {/* Transaction Modal */}
      <Dialog open={txDialogOpen} onOpenChange={setTxDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-bold flex items-center gap-2">
              <PiggyBank className="w-5 h-5 text-teal-600" />
              {txType === 'DEPOSIT' && 'Add Deposit / Savings Funds'}
              {txType === 'WITHDRAWAL' && 'Record Withdrawal / Payout'}
              {txType === 'SETTLEMENT' && 'Resignation Settlement Payout'}
            </DialogTitle>
          </DialogHeader>

          <form onSubmit={handleTransactionSubmit} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <div className="flex justify-between items-center">
                <Label className="text-xs font-semibold">Amount (₹) *</Label>
                <span className="text-[11px] text-slate-500">
                  Available: <strong className="text-emerald-700 font-mono">₹{accumulatedBal.toLocaleString('en-IN')}</strong>
                </span>
              </div>
              <Input
                type="number"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="e.g. 1000"
                className="text-xs font-mono h-9"
                required
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">Notes / Reason</Label>
              <Input
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={
                  txType === 'DEPOSIT'
                    ? 'e.g. Manual deposit by staff'
                    : txType === 'SETTLEMENT'
                    ? 'e.g. Final settlement on resignation'
                    : 'e.g. Advance withdrawal requested by staff'
                }
                className="text-xs h-9"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setTxDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={submitting} className="bg-teal-600 hover:bg-teal-700 text-white font-semibold">
                {submitting ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : null}
                Save Transaction
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
