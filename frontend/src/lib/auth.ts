import { User } from '@/types'

export const getToken = (): string | null => {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('spt_access_token')
}

export const getRefreshToken = (): string | null => {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('spt_refresh_token')
}

export const setTokens = (access: string, refresh: string) => {
  if (typeof window === 'undefined') return
  localStorage.setItem('spt_access_token', access)
  localStorage.setItem('spt_refresh_token', refresh)
}

export const clearTokens = () => {
  if (typeof window === 'undefined') return
  localStorage.removeItem('spt_access_token')
  localStorage.removeItem('spt_refresh_token')
  localStorage.removeItem('spt_user')
  // Remove legacy non-httpOnly token cookie if present
  document.cookie = 'token=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; SameSite=Lax'
  // Clear httpOnly cookies on the backend
  const apiBase = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').replace(/\/+$/, '')
  fetch(`${apiBase}/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => {})
}

export const getUser = (): User | null => {
  if (typeof window === 'undefined') return null
  try {
    const userStr = localStorage.getItem('spt_user')
    return userStr ? (JSON.parse(userStr) as User) : null
  } catch {
    return null
  }
}

export const setUser = (user: User) => {
  if (typeof window === 'undefined') return
  localStorage.setItem('spt_user', JSON.stringify(user))
}

export const isAuthenticated = (): boolean => {
  return !!getToken()
}
