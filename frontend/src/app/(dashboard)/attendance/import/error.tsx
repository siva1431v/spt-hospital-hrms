'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { AlertTriangle, RefreshCw, ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function ImportErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    console.error('Attendance import error:', error)
  }, [error])

  return (
    <div className="max-w-xl mx-auto my-12 p-8 bg-white rounded-2xl border border-rose-200 shadow-sm text-center space-y-4">
      <div className="w-12 h-12 mx-auto rounded-full bg-rose-50 border border-rose-100 flex items-center justify-center text-rose-600">
        <AlertTriangle className="w-6 h-6" />
      </div>
      <div>
        <h2 className="text-lg font-bold text-slate-900">Something went wrong parsing attendance</h2>
        <p className="text-xs text-slate-500 mt-1">
          {error.message || 'An unexpected error occurred while processing the attendance file.'}
        </p>
      </div>

      <div className="flex items-center justify-center gap-2 pt-2">
        <Button
          onClick={() => reset()}
          size="sm"
          className="bg-teal-600 hover:bg-teal-700 text-white text-xs font-semibold gap-1.5"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Try Again
        </Button>
        <Link href="/dashboard">
          <Button variant="outline" size="sm" className="text-xs gap-1.5">
            <ArrowLeft className="w-3.5 h-3.5" />
            Go to Dashboard
          </Button>
        </Link>
      </div>
    </div>
  )
}
