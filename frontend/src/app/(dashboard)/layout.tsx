'use client'

import MainLayout from '@/components/layout/MainLayout'
import { useEffect, useSyncExternalStore } from 'react'
import { useRouter } from 'next/navigation'
import { isAuthenticated } from '@/lib/auth'
import { Loader2 } from 'lucide-react'

const emptySubscribe = () => () => {}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false)

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push('/login')
    }
  }, [router])

  if (!mounted) {
    return (
      <div className="h-screen w-screen bg-slate-900 flex items-center justify-center text-teal-400">
        <Loader2 className="w-8 h-8 animate-spin" />
      </div>
    )
  }

  return <MainLayout>{children}</MainLayout>
}
