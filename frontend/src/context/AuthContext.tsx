import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, setCsrfToken } from '../api/client'
import type { Session, User } from '../api/types'

type AuthState = {
  user: User | null
  ready: boolean
  login: (email: string, password: string) => Promise<void>
  register: (name: string, email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  const bootstrap = useCallback(async () => {
    try {
      const csrf = await api.get<{ csrf_token: string }>('/auth/csrf')
      setCsrfToken(csrf.csrf_token)
    } catch {
      setCsrfToken(null)
    }

    try {
      const state = await api.get<{ user: User | null }>('/auth/session')
      setUser(state.user)
    } catch {
      setUser(null)
    } finally {
      setReady(true)
    }
  }, [])

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  const login = useCallback(async (email: string, password: string) => {
    const session = await api.post<Session>('/auth/login', { email, password })
    setCsrfToken(session.csrf_token)
    setUser(session.user)
  }, [])

  const register = useCallback(async (name: string, email: string, password: string) => {
    const session = await api.post<Session>('/auth/register', { name, email, password })
    setCsrfToken(session.csrf_token)
    setUser(session.user)
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      setUser(null)
      setCsrfToken(null)
    }
  }, [])

  const refresh = useCallback(async () => {
    const me = await api.get<User>('/auth/me')
    setUser(me)
  }, [])

  const value = useMemo(
    () => ({ user, ready, login, register, logout, refresh }),
    [user, ready, login, register, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider')
  }
  return context
}
