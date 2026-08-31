import axios from 'axios'
import { clearTokens } from './auth'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add token to request headers
api.interceptors.request.use(
  (config) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('spt_access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

import { toast } from 'sonner'

// Handle API errors globally with sonner toast notifications
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isCancel(error) || error.code === 'ERR_CANCELED' || error.name === 'AbortError' || error.name === 'CanceledError') {
      return Promise.reject(error)
    }

    if (typeof window !== 'undefined') {
      if (error.response?.status === 401) {
        clearTokens()
        if (!window.location.pathname.includes('/login')) {
          sessionStorage.setItem('session_expired', '1')
          toast.error('Your session has expired. Please sign in again.', { duration: 4000 })
          setTimeout(() => {
            window.location.href = '/login?expired=1'
          }, 300)
        }
      } else {
        const detail = error.response?.data?.detail
        const message = typeof detail === 'string' ? detail : (error.message || 'An unexpected error occurred.')
        toast.error(message, { duration: 5000 })
      }
    }
    return Promise.reject(error)
  }
)

export default api
