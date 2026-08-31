'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Cross, Lock, User, Eye, EyeOff, Loader2, CheckCircle2, AlertTriangle } from 'lucide-react'
import { setTokens, setUser } from '@/lib/auth'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function LoginPage() {
  const router = useRouter()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isExpired, setIsExpired] = useState(false)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search)
      if (params.get('expired') === '1' || sessionStorage.getItem('session_expired') === '1') {
        setIsExpired(true)
        sessionStorage.removeItem('session_expired')
      }
    }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await api.post('/auth/login', { username, password })
      const { access_token, refresh_token, user } = response.data
      setTokens(access_token, refresh_token)
      setUser(user)
      router.push('/dashboard')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Invalid username or password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 md:grid-cols-2 bg-slate-900 font-sans">
      {/* Left Column — Hospital Branding */}
      <div className="relative bg-gradient-to-br from-slate-950 via-slate-900 to-teal-950 p-8 lg:p-16 flex flex-col justify-between overflow-hidden border-r border-slate-800">
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-teal-600/10 rounded-full blur-3xl" />

        {/* Logo */}
        <div className="flex items-center gap-3.5 z-10">
          <div className="w-12 h-12 rounded-xl bg-teal-500 flex items-center justify-center text-slate-950 font-bold shadow-lg shadow-teal-500/30">
            <Cross className="w-7 h-7 fill-slate-950" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white tracking-wider">SPT HOSPITAL</h1>
            <p className="text-xs text-teal-400 font-medium tracking-widest uppercase">HRMS & Payroll Suite</p>
          </div>
        </div>

        {/* Center Intro */}
        <div className="my-auto py-12 z-10 space-y-6 max-w-lg">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-teal-950/80 border border-teal-800/60 text-teal-300 text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-teal-400 animate-pulse" />
            eSSL Biometric Integration Ready
          </div>
          <h2 className="text-3xl lg:text-4xl font-extrabold text-white leading-tight">
            Automated Attendance & Hospital Salary Management
          </h2>
          <p className="text-slate-400 text-sm leading-relaxed">
            Upload attendance PDFs directly from your biometric logs. Parse overnight hospital shifts, calculate allowances, manage leaves, and issue automated salary slips in seconds.
          </p>

          <div className="space-y-3 pt-4">
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
              <span>Full eSSL PDF Report Parsing Engine</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
              <span>Overnight Shift & Custom OT Rate Calculation</span>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <CheckCircle2 className="w-4 h-4 text-teal-400 shrink-0" />
              <span>One-Click Salary Slips & Monthly Excel Exports</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <p className="text-xs text-slate-500 z-10">
          © {new Date().getFullYear()} SPT Hospital HRMS. Production Ready System.
        </p>
      </div>

      {/* Right Column — Login Form */}
      <div className="bg-white p-8 lg:p-16 flex flex-col justify-center items-center">
        <div className="w-full max-w-md space-y-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Sign In to Administrator Portal</h2>
            <p className="text-xs text-slate-500 mt-1.5">
              Enter your hospital user credentials to access HRMS.
            </p>
          </div>

          {isExpired && (
            <div className="p-3.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-xs font-medium flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>Your session has expired. Please sign in again to continue.</span>
            </div>
          )}

          {error && (
            <div className="p-3.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 text-xs font-medium">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-1.5">
              <Label htmlFor="username" className="text-xs font-semibold text-slate-700">Username or Email</Label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <Input
                  id="username"
                  type="text"
                  required
                  placeholder="Enter username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="pl-9 text-xs h-10 border-slate-200 focus-visible:ring-teal-500"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-xs font-semibold text-slate-700">Password</Label>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3 top-3" />
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-9 pr-9 text-xs h-10 border-slate-200 focus-visible:ring-teal-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-3 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-teal-600 hover:bg-teal-700 text-white font-semibold text-xs h-10 shadow-md shadow-teal-600/20 transition-all"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Signing In...
                </>
              ) : (
                'Sign In to Dashboard'
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  )
}
