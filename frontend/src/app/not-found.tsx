import Link from 'next/link'
import { FileQuestion, Home, Calendar, Users, Banknote } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="max-w-md w-full text-center space-y-6 bg-white p-8 rounded-2xl border border-slate-200 shadow-sm">
        <div className="w-16 h-16 rounded-2xl bg-teal-50 border border-teal-200 text-teal-600 flex items-center justify-center mx-auto shadow-inner">
          <FileQuestion className="w-8 h-8 text-teal-600" />
        </div>

        <div className="space-y-2">
          <span className="text-xs font-bold uppercase tracking-wider text-teal-700 bg-teal-50 px-2.5 py-1 rounded-full border border-teal-200">
            404 — Page Not Found
          </span>
          <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
            SPT Hospital HRMS
          </h1>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            The page you are looking for doesn't exist or has been moved. Use the quick links below to return to the system.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-2">
          <Link href="/dashboard" className="w-full">
            <Button className="w-full bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-2 h-10">
              <Home className="w-4 h-4" />
              Dashboard
            </Button>
          </Link>
          <Link href="/attendance" className="w-full">
            <Button variant="outline" className="w-full text-xs font-semibold gap-2 h-10 border-slate-200">
              <Calendar className="w-4 h-4 text-slate-500" />
              Attendance
            </Button>
          </Link>
          <Link href="/employees" className="w-full">
            <Button variant="outline" className="w-full text-xs font-semibold gap-2 h-10 border-slate-200">
              <Users className="w-4 h-4 text-slate-500" />
              Employees
            </Button>
          </Link>
          <Link href="/payroll" className="w-full">
            <Button variant="outline" className="w-full text-xs font-semibold gap-2 h-10 border-slate-200">
              <Banknote className="w-4 h-4 text-slate-500" />
              Payroll
            </Button>
          </Link>
        </div>

        <div className="border-t border-slate-100 pt-4 text-[11px] text-slate-400">
          SPT Hospital Attendance & Payroll Management System
        </div>
      </div>
    </div>
  )
}
