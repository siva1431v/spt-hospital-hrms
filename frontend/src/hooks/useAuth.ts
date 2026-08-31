'use client'

import { useState, useEffect } from 'react'
import { getUser, isAuthenticated, clearTokens } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { User } from '@/types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    const u = getUser()
    setUser(u)
    setLoading(false)
  }, [])

  const logout = () => {
    clearTokens()
    setUser(null)
    router.push('/login')
  }

  return {
    user,
    loading,
    isAuthenticated: isAuthenticated(),
    logout,
  }
}
