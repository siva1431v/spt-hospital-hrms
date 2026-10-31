'use client'

import Link from 'next/link'
import { ArrowLeft, BookOpen, CheckCircle2, FileText, Fingerprint, Calculator, AlertTriangle, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function MonthlyImportDocsPage() {
  return (
    <div className="space-y-8 max-w-4xl mx-auto pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <Link
              href="/attendance/import"
              className="text-slate-500 hover:text-slate-800 transition-colors p-1 rounded-md hover:bg-slate-100"
              title="Back to Attendance Import"
            >
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight flex items-center gap-2">
              <BookOpen className="w-6 h-6 text-teal-600" />
              Monthly Attendance Import & Payroll Guide
            </h1>
          </div>
          <p className="text-xs text-slate-500 mt-1 pl-7">
            Standard Operating Procedure for exporting eSSL reports, reviewing employee mappings, and calculating monthly payroll.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/attendance/import">
            <Button className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-1.5 shadow-xs">
              <FileText className="w-3.5 h-3.5" />
              Go to Import Wizard
            </Button>
          </Link>
        </div>
      </div>

      {/* Step 1: Exporting */}
      <section className="bg-white p-6 rounded-xl border border-slate-200 space-y-4 shadow-2xs">
        <div className="flex items-center gap-3 text-teal-900 border-b border-slate-100 pb-3">
          <div className="w-7 h-7 rounded-full bg-teal-100 text-teal-800 flex items-center justify-center font-bold text-xs">
            1
          </div>
          <h2 className="text-base font-bold text-slate-900">Exporting from eSSL Biometric Software</h2>
        </div>
        <ol className="list-decimal list-inside space-y-2 text-xs text-slate-600 leading-relaxed pl-1">
          <li>Open your <strong>eSSL Biometric Attendance Software</strong> (eTimeTrack / SmartOffice Desktop).</li>
          <li>Navigate to: <strong>Reports</strong> &rarr; <strong>Monthly Reports</strong> &rarr; <strong>Monthly Status Report (Basic Report)</strong>.</li>
          <li>
            Select the date range:
            <ul className="list-disc list-inside pl-4 mt-1 space-y-1 text-slate-500">
              <li><strong>From Date:</strong> 1st of the month (e.g. <code className="text-teal-700 bg-teal-50 px-1 py-0.5 rounded">01/09/2026</code>)</li>
              <li><strong>To Date:</strong> Last day of the month (e.g. <code className="text-teal-700 bg-teal-50 px-1 py-0.5 rounded">30/09/2026</code> or <code className="text-teal-700 bg-teal-50 px-1 py-0.5 rounded">31/09/2026</code>)</li>
            </ul>
          </li>
          <li>Ensure all active departments and both biometric companies (<strong>SPT</strong> and <strong>Old Bio</strong>) are included.</li>
          <li>Click <strong>Export &rarr; PDF</strong> and save the file to your computer.</li>
        </ol>
      </section>

      {/* Step 2: Upload & Review */}
      <section className="bg-white p-6 rounded-xl border border-slate-200 space-y-4 shadow-2xs">
        <div className="flex items-center gap-3 text-teal-900 border-b border-slate-100 pb-3">
          <div className="w-7 h-7 rounded-full bg-teal-100 text-teal-800 flex items-center justify-center font-bold text-xs">
            2
          </div>
          <h2 className="text-base font-bold text-slate-900">Upload & Review Wizard</h2>
        </div>
        <p className="text-xs text-slate-600 leading-relaxed">
          Upload your PDF into the Attendance Import Wizard. The system automatically inspects header dates, verifies row checksums, and groups employees by resolution status:
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs pt-1">
          <div className="p-3 bg-emerald-50/50 rounded-lg border border-emerald-200 space-y-1">
            <span className="font-bold text-emerald-800 uppercase text-[10px] tracking-wide">MATCHED</span>
            <p className="text-slate-600">The biometric code and employee name match the Master database. Action is set to <strong>Link</strong> automatically.</p>
          </div>

          <div className="p-3 bg-amber-50/50 rounded-lg border border-amber-200 space-y-1">
            <span className="font-bold text-amber-800 uppercase text-[10px] tracking-wide">NAME MISMATCH</span>
            <p className="text-slate-600">The biometric code exists in the master but the name in the PDF differs (e.g. Code 64: Kiruthika vs Dr. Saranya). You can link to an existing employee and check <strong>Save as Alias</strong>.</p>
          </div>

          <div className="p-3 bg-blue-50/50 rounded-lg border border-blue-200 space-y-1">
            <span className="font-bold text-blue-800 uppercase text-[10px] tracking-wide">NEW EMPLOYEE</span>
            <p className="text-slate-600">The biometric code is new (e.g. newly onboarded staff like Latha or Ashwin). Choose <strong>Create New Employee</strong> to register them into the master database.</p>
          </div>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 space-y-1">
            <span className="font-bold text-slate-700 uppercase text-[10px] tracking-wide">DUPLICATE SUSPECT</span>
            <p className="text-slate-600">Secondary machine entry (e.g. Old Bio reader 208-210) with all-absent records. Action is set to <strong>Ignore</strong> to prevent overwriting valid attendance.</p>
          </div>
        </div>
      </section>

      {/* Step 3: Calculation Rules */}
      <section className="bg-white p-6 rounded-xl border border-slate-200 space-y-4 shadow-2xs">
        <div className="flex items-center gap-3 text-teal-900 border-b border-slate-100 pb-3">
          <div className="w-7 h-7 rounded-full bg-teal-100 text-teal-800 flex items-center justify-center font-bold text-xs">
            3
          </div>
          <h2 className="text-base font-bold text-slate-900">Hospital Attendance & Payroll Calculation Rules</h2>
        </div>

        <div className="space-y-3 text-xs text-slate-600 leading-relaxed">
          <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
            <div className="font-bold text-slate-900">1. Payable Days Formula:</div>
            <p className="font-mono text-xs text-teal-800 bg-white p-2 rounded border border-slate-200">
              Payable Days = Present + (Half × 0.5) + MIN(Leave, 3) + Holiday + Weekly Off + Weekly Off Present + Off Duty
            </p>
          </div>

          <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
            <div className="font-bold text-slate-900">2. 3-Day Paid Leave Benefit:</div>
            <p>
              Every active employee receives up to <strong>3 days of paid leave</strong> per month. The first 3 leave/absence days do not deduct salary. Any unworked absence beyond 3 days generates Loss of Pay (LOP) deductions.
            </p>
          </div>

          <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
            <div className="font-bold text-slate-900">3. Mid-Month Joiners & NO_DATA:</div>
            <p>
              Empty calendar cells before an employee's joining date are recorded as <code className="text-slate-700 bg-slate-200 px-1 py-0.5 rounded font-mono">NO_DATA</code>. They are <strong>never</strong> counted as Absent or Loss of Pay.
              Mid-month joiners (e.g. joined on the 30th) receive pay strictly for the days they worked.
            </p>
          </div>

          <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200 space-y-2">
            <div className="font-bold text-slate-900">4. Monthly Status Report Lateness Notice:</div>
            <p>
              The eSSL Basic Report contains status codes but does not record punch timestamps. Therefore, lateness LOP and overtime are not fabricated from this report. A notice is displayed in the Attendance Coverage bar.
            </p>
          </div>
        </div>
      </section>

      {/* Quick Links Footer */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-4 border-t border-slate-200">
        <Link href="/settings/aliases" className="text-xs font-semibold text-teal-700 hover:text-teal-800 flex items-center gap-1.5">
          <Fingerprint className="w-4 h-4" />
          Manage Device Code Aliases
        </Link>
        <Link href="/payroll" className="text-xs font-semibold text-teal-700 hover:text-teal-800 flex items-center gap-1.5">
          <Calculator className="w-4 h-4" />
          Go to Monthly Payroll & Salary Calculator
          <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>
    </div>
  )
}
