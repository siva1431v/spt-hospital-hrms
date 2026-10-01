'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, Check, Loader2, AlertTriangle } from 'lucide-react'
import api from '@/lib/api'
import { Department, Shift, Employee } from '@/types'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import Link from 'next/link'

interface FormErrors {
  first_name?: string
  last_name?: string
  employee_id?: string
  biometric_code?: string
  phone?: string
  basic_salary?: string
  security_fund_deduction?: string
  api?: string
}

export default function NewEmployeePage() {
  const router = useRouter()
  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)
  const [departments, setDepartments] = useState<Department[]>([])
  const [shifts, setShifts] = useState<Shift[]>([])
  const [errors, setErrors] = useState<FormErrors>({})
  const [similarStaff, setSimilarStaff] = useState<Employee[]>([])

  // Form State
  const [formData, setFormData] = useState({
    first_name: '',
    last_name: '',
    employee_id: '',
    biometric_code: '',
    gender: 'MALE',
    date_of_birth: '',
    phone: '',
    email: '',
    department_id: '',
    shift_id: '',
    employment_type: 'FULL_TIME',
    joining_date: new Date().toISOString().split('T')[0],
    basic_salary: '',
    security_fund_deduction: '500',
  })

  useEffect(() => {
    Promise.all([api.get('/departments'), api.get('/shifts')])
      .then(([deptRes, shiftRes]) => {
        setDepartments(deptRes.data.items || [])
        setShifts(shiftRes.data.items || [])
      })
      .catch((err) => console.error(err))
  }, [])

  // Check for similar employee names when first_name or last_name changes
  useEffect(() => {
    const timer = setTimeout(async () => {
      const query = formData.first_name.trim()
      if (query.length < 3) {
        setSimilarStaff([])
        return
      }
      try {
        const res = await api.get('/employees', { params: { search: query, page_size: 10 } })
        const items: Employee[] = res.data.items || []
        const matches = items.filter((emp) => {
          const empFirst = (emp.first_name || '').toLowerCase()
          const empFull = (emp.full_name || '').toLowerCase()
          const q = query.toLowerCase()
          return empFirst.includes(q) || empFull.includes(q)
        })
        setSimilarStaff(matches)
      } catch {
        setSimilarStaff([])
      }
    }, 350)

    return () => clearTimeout(timer)
  }, [formData.first_name, formData.last_name])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target
    setFormData({ ...formData, [name]: value })
    // Clear field-level error on change
    if (errors[name as keyof FormErrors]) {
      setErrors({ ...errors, [name]: undefined })
    }
  }

  const validateStep1 = (): boolean => {
    const newErrors: FormErrors = {}
    if (!formData.first_name.trim()) {
      newErrors.first_name = 'First name is required'
    }
    if (!formData.employee_id.trim()) {
      newErrors.employee_id = 'Employee ID is required'
    }
    if (formData.phone && formData.phone.trim() !== '') {
      const cleaned = formData.phone.trim().replace(/[\s\-]/g, '')
      if (!/^(?:\+91|91|0)?[6-9]\d{9}$/.test(cleaned)) {
        newErrors.phone = 'Please enter a valid 10-digit Indian mobile number (e.g. 9876543210 or +919876543210)'
      }
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const validateStep2 = (): boolean => {
    const newErrors: FormErrors = {}
    if (!formData.basic_salary || formData.basic_salary.trim() === '') {
      newErrors.basic_salary = 'Basic monthly salary is required'
    } else {
      const sal = Number(formData.basic_salary)
      if (isNaN(sal) || sal <= 0) {
        newErrors.basic_salary = 'Basic salary must be greater than 0'
      }
    }
    if (formData.security_fund_deduction !== '' && formData.security_fund_deduction !== undefined) {
      const fund = Number(formData.security_fund_deduction)
      if (isNaN(fund) || fund < 0) {
        newErrors.security_fund_deduction = 'Savings fund deduction must be 0 or greater'
      }
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleNextStep = () => {
    if (validateStep1()) {
      setStep(2)
    }
  }

  const handleSubmit = async () => {
    if (!validateStep1()) {
      setStep(1)
      return
    }
    if (!validateStep2()) {
      return
    }
    setLoading(true)
    setErrors({})

    try {
      const payload: Record<string, unknown> = {}
      Object.entries(formData).forEach(([key, val]) => {
        if (val !== '') {
          payload[key] = val
        }
      })
      if (payload.department_id) payload.department_id = Number(payload.department_id)
      if (payload.shift_id) payload.shift_id = Number(payload.shift_id)
      if (payload.basic_salary !== undefined) payload.basic_salary = Number(payload.basic_salary)
      if (payload.security_fund_deduction !== undefined) payload.security_fund_deduction = Number(payload.security_fund_deduction)

      await api.post('/employees', payload)
      router.push('/employees')
    } catch (err: unknown) {
      const errResp = (err as { response?: { data?: { detail?: string; errors?: Array<{ field?: string; message?: string }> } } })?.response
      const detail = errResp?.data?.detail || 'Failed to create employee.'
      // Parse error detail to show inline on the right field while preserving form state
      if (typeof detail === 'string') {
        if (detail.toLowerCase().includes('employee id')) {
          setErrors({ employee_id: detail })
          setStep(1)
        } else if (detail.toLowerCase().includes('biometric')) {
          setErrors({ biometric_code: detail })
          setStep(1)
        } else if (detail.toLowerCase().includes('phone') || detail.toLowerCase().includes('mobile')) {
          setErrors({ phone: detail })
          setStep(1)
        } else if (detail.toLowerCase().includes('basic salary') || detail.toLowerCase().includes('salary')) {
          setErrors({ basic_salary: detail })
          setStep(2)
        } else if (detail.toLowerCase().includes('savings fund') || detail.toLowerCase().includes('security fund') || detail.toLowerCase().includes('deduction')) {
          setErrors({ security_fund_deduction: detail })
          setStep(2)
        } else {
          setErrors({ api: detail })
        }
      } else if (Array.isArray(errResp?.data?.errors)) {
        const fieldErrors: FormErrors = {}
        let targetStep = 2
        for (const e of errResp.data.errors) {
          if (e.field?.includes('phone')) {
            fieldErrors.phone = e.message
            targetStep = 1
          } else if (e.field?.includes('basic_salary')) {
            fieldErrors.basic_salary = e.message
          } else if (e.field?.includes('security_fund_deduction')) {
            fieldErrors.security_fund_deduction = e.message
          } else if (e.field?.includes('employee_id')) {
            fieldErrors.employee_id = e.message
            targetStep = 1
          } else if (e.field?.includes('first_name')) {
            fieldErrors.first_name = e.message
            targetStep = 1
          } else if (e.field?.includes('last_name')) {
            fieldErrors.last_name = e.message
            targetStep = 1
          }
        }
        setErrors(fieldErrors)
        setStep(targetStep)
      } else {
        setErrors({ api: 'Failed to create employee.' })
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link href="/employees">
          <Button variant="outline" size="sm" className="h-8 w-8 p-0">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-xl font-bold text-slate-900">Add New Hospital Staff</h1>
          <p className="text-xs text-slate-500">Register employee details and biometric code mapping</p>
        </div>
      </div>

      {/* Step Indicator */}
      <div className="flex items-center justify-between bg-white p-4 rounded-xl border border-slate-200 shadow-2xs">
        <div className={`flex items-center gap-2 text-xs font-semibold ${step >= 1 ? 'text-teal-600' : 'text-slate-400'}`}>
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${step >= 1 ? 'bg-teal-600 text-white' : 'bg-slate-200'}`}>1</div>
          <span>Basic Information</span>
        </div>
        <div className="h-[1px] w-12 bg-slate-200" />
        <div className={`flex items-center gap-2 text-xs font-semibold ${step >= 2 ? 'text-teal-600' : 'text-slate-400'}`}>
          <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${step >= 2 ? 'bg-teal-600 text-white' : 'bg-slate-200'}`}>2</div>
          <span>Department & Shift</span>
        </div>
      </div>

      {/* Global API Error */}
      {errors.api && (
        <div className="bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium p-3 rounded-lg">
          {errors.api}
        </div>
      )}

      {/* Form Container — using div instead of form to prevent implicit submit on Enter */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 space-y-6 shadow-xs">
        {step === 1 && (
          <div className="space-y-4">
            <h2 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2">Step 1: Personal & Biometric Info</h2>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">First Name *</Label>
                <Input name="first_name" value={formData.first_name} onChange={handleChange} placeholder="e.g. Anitha" className={`text-xs h-9 ${errors.first_name ? 'border-rose-400 focus-visible:ring-rose-400' : ''}`} />
                {errors.first_name && <p className="text-[11px] text-rose-600 font-medium">{errors.first_name}</p>}
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Last Name</Label>
                <Input name="last_name" value={formData.last_name} onChange={handleChange} placeholder="e.g. Kumar (Optional)" className={`text-xs h-9 ${errors.last_name ? 'border-rose-400 focus-visible:ring-rose-400' : ''}`} />
                {errors.last_name && <p className="text-[11px] text-rose-600 font-medium">{errors.last_name}</p>}
              </div>
            </div>

            {similarStaff.length > 0 && (
              <div className="p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs space-y-1.5 animate-in fade-in duration-200">
                <div className="flex items-center gap-1.5 font-bold text-amber-900">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                  <span>Possible Duplicate Employee Detected</span>
                </div>
                <p className="text-amber-800 text-[11px]">
                  Existing staff with similar names already exist in the database:
                </p>
                <div className="divide-y divide-amber-200/60 bg-white/70 rounded-md border border-amber-200/80 p-2 space-y-1">
                  {similarStaff.slice(0, 4).map((s) => (
                    <div key={s.id} className="pt-1 first:pt-0 flex items-center justify-between text-[11px] text-amber-950">
                      <span className="font-semibold">{s.first_name} {s.last_name || ''}</span>
                      <span className="font-mono text-amber-800 text-[10px]">
                        ID: {s.employee_id} {s.biometric_code ? `• Bio: ${s.biometric_code}` : ''} {s.department_name ? `• ${s.department_name}` : ''}
                      </span>
                    </div>
                  ))}
                </div>
                <p className="text-[10px] text-amber-700 italic">
                  Please verify this person is a new staff member and not a re-registration of an existing profile.
                </p>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Employee ID *</Label>
                <Input name="employee_id" value={formData.employee_id} onChange={handleChange} placeholder="e.g. EMP045" className={`text-xs h-9 font-mono ${errors.employee_id ? 'border-rose-400 focus-visible:ring-rose-400' : ''}`} />
                {errors.employee_id && <p className="text-[11px] text-rose-600 font-medium">{errors.employee_id}</p>}
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Biometric Device Code</Label>
                <Input name="biometric_code" value={formData.biometric_code} onChange={handleChange} placeholder="e.g. 45" className={`text-xs h-9 font-mono ${errors.biometric_code ? 'border-rose-400 focus-visible:ring-rose-400' : ''}`} />
                {errors.biometric_code && <p className="text-[11px] text-rose-600 font-medium">{errors.biometric_code}</p>}
                {!errors.biometric_code && <p className="text-[10px] text-slate-400">Maps to eSSL attendance report PDF</p>}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Gender</Label>
                <select name="gender" value={formData.gender} onChange={handleChange} className="h-9 px-3 rounded-md border border-slate-200 text-xs w-full">
                  <option value="FEMALE">Female</option>
                  <option value="MALE">Male</option>
                  <option value="OTHER">Other</option>
                </select>
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Phone Number</Label>
                <Input
                  name="phone"
                  value={formData.phone}
                  onChange={handleChange}
                  placeholder="e.g. 9876543210 or +919876543210"
                  className={`text-xs h-9 ${errors.phone ? 'border-rose-400 focus-visible:ring-rose-400' : ''}`}
                />
                {errors.phone && <p className="text-[11px] text-rose-600 font-medium">{errors.phone}</p>}
                {!errors.phone && <p className="text-[10px] text-slate-400">Optional: 10-digit Indian mobile number</p>}
              </div>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <h2 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-2">Step 2: Department & Shift Assignment</h2>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Department</Label>
                <select name="department_id" value={formData.department_id} onChange={handleChange} className="h-9 px-3 rounded-md border border-slate-200 text-xs w-full">
                  <option value="">Select Department</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>{d.name} ({d.code})</option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Assigned Shift</Label>
                <select name="shift_id" value={formData.shift_id} onChange={handleChange} className="h-9 px-3 rounded-md border border-slate-200 text-xs w-full">
                  <option value="">Select Shift</option>
                  {shifts.map((s) => (
                    <option key={s.id} value={s.id}>{s.name} ({s.code}: {s.start_time} - {s.end_time})</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Employment Type</Label>
                <select name="employment_type" value={formData.employment_type} onChange={handleChange} className="h-9 px-3 rounded-md border border-slate-200 text-xs w-full">
                  <option value="FULL_TIME">Full Time / Permanent</option>
                  <option value="PROBATION">Probation</option>
                  <option value="CONTRACT">Contract</option>
                  <option value="PART_TIME">Part Time</option>
                  <option value="INTERN">Intern</option>
                </select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Joining Date</Label>
                <Input type="date" name="joining_date" value={formData.joining_date} onChange={handleChange} className="text-xs h-9" />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Basic Monthly Salary (₹) *</Label>
                <Input
                  type="number"
                  name="basic_salary"
                  min="1"
                  required
                  value={formData.basic_salary}
                  onChange={handleChange}
                  placeholder="e.g. 25000"
                  className={`text-xs h-9 font-mono ${errors.basic_salary ? 'border-rose-400 focus-visible:ring-rose-400' : ''}`}
                />
                {errors.basic_salary && <p className="text-[11px] text-rose-600 font-medium">{errors.basic_salary}</p>}
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">Monthly Savings Fund Deduction (₹)</Label>
                <Input
                  type="number"
                  name="security_fund_deduction"
                  min="0"
                  value={formData.security_fund_deduction}
                  onChange={handleChange}
                  placeholder="e.g. 500"
                  className={`text-xs h-9 font-mono ${errors.security_fund_deduction ? 'border-rose-400 focus-visible:ring-rose-400' : ''}`}
                />
                {errors.security_fund_deduction && <p className="text-[11px] text-rose-600 font-medium">{errors.security_fund_deduction}</p>}
              </div>
            </div>
          </div>
        )}

        {/* Buttons */}
        <div className="flex items-center justify-between pt-4 border-t border-slate-100">
          {step > 1 ? (
            <Button type="button" variant="outline" onClick={() => setStep(step - 1)} className="text-xs h-9">
              Previous
            </Button>
          ) : <div />}

          {step < 2 ? (
            <Button type="button" onClick={handleNextStep} className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9">
              Next Step
            </Button>
          ) : (
            <Button type="button" onClick={handleSubmit} disabled={loading} className="bg-teal-600 hover:bg-teal-700 text-white text-xs h-9">
              {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Check className="w-4 h-4 mr-1" />}
              Save Employee Profile
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
