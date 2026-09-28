'use client'

import { useState } from 'react'
import { getUser, isAuthenticated, clearTokens } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { User } from '@/types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(() => getUser())
  const [loading] = useState(false)
  const router = useRouter()

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
