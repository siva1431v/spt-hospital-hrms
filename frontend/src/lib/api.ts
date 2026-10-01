import axios from 'axios'
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios'
import { clearTokens, getRefreshToken, setTokens } from './auth'
import { toast } from 'sonner'

const rawBase = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1').trim()
const cleanBase = rawBase.replace(/\/+$/, '')
const API_BASE_URL = cleanBase.endsWith('/api/v1') ? cleanBase : `${cleanBase}/api/v1`

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Add token to request headers
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
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

interface QueueItem {
  resolve: (token: string) => void
  reject: (error: unknown) => void
}

let isRefreshing = false
let failedQueue: QueueItem[] = []

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else if (token) {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

function handleAuthFailure() {
  if (typeof window === 'undefined') return
  clearTokens()
  if (!window.location.pathname.includes('/login')) {
    sessionStorage.setItem('session_expired', '1')
    toast.error('Your session has expired. Please sign in again.', { duration: 4000 })
    setTimeout(() => {
      window.location.href = '/login?expired=1'
    }, 300)
  }
}

// Handle API errors and token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (
      axios.isCancel(error) ||
      error.code === 'ERR_CANCELED' ||
      error.name === 'AbortError' ||
      error.name === 'CanceledError'
    ) {
      return Promise.reject(error)
    }

    const originalRequest = error.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      const isAuthUrl =
        originalRequest.url?.includes('/auth/login') ||
        originalRequest.url?.includes('/auth/refresh')

      if (isAuthUrl) {
        if (typeof window !== 'undefined' && !originalRequest.url?.includes('/auth/login')) {
          handleAuthFailure()
        }
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise<string>((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((newToken) => {
            if (originalRequest.headers) {
              originalRequest.headers['Authorization'] = `Bearer ${newToken}`
            }
            return api(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      const refreshToken = getRefreshToken()
      if (!refreshToken) {
        isRefreshing = false
        handleAuthFailure()
        return Promise.reject(error)
      }

      try {
        const refreshResponse = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        })
        const { access_token, refresh_token: newRefreshToken } = refreshResponse.data
        setTokens(access_token, newRefreshToken)
        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
        processQueue(null, access_token)

        if (originalRequest.headers) {
          originalRequest.headers['Authorization'] = `Bearer ${access_token}`
        }
        return api(originalRequest)
      } catch (refreshError) {
        processQueue(refreshError, null)
        handleAuthFailure()
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    // Non-401 errors or already retried 401 errors
    if (typeof window !== 'undefined' && error.response?.status !== 401) {
      const detail = error.response?.data?.detail
      const message =
        typeof detail === 'string' ? detail : (error.message || 'An unexpected error occurred.')
      toast.error(message, { duration: 5000 })
    }

    return Promise.reject(error)
  }
)

export default api
