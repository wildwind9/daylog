import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { fetchCurrentUser } from '../api'

type AuthState = 'checking' | 'authorized' | 'unauthorized'

export function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('daylog_token')
  const [authState, setAuthState] = useState<AuthState>(token ? 'checking' : 'unauthorized')

  useEffect(() => {
    if (!token) {
      return
    }

    let cancelled = false
    fetchCurrentUser()
      .then(() => {
        if (!cancelled) {
          setAuthState('authorized')
        }
      })
      .catch(() => {
        if (!cancelled) {
          localStorage.removeItem('daylog_token')
          setAuthState('unauthorized')
        }
      })

    return () => {
      cancelled = true
    }
  }, [token])

  if (authState === 'checking') return null
  return authState === 'authorized' ? <>{children}</> : <Navigate to="/login" replace />
}
