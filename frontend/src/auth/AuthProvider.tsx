import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useI18n } from '../i18n/I18nProvider'
import { isLang, type LangCode } from '../i18n/languages'
import { UNAUTHORIZED_EVENT, api, toApiError } from '../services/api'
import { useTheme } from '../theme/ThemeProvider'
import type { ThemeSetting, User } from '../types/api'

type Status = 'loading' | 'signed-in' | 'signed-out'

interface AuthState {
  user: User | null
  status: Status
  /** Set when the account could not be loaded for a reason other than "not signed in". */
  bootError: string | null
  signIn: (email: string, password: string, remember: boolean) => Promise<User>
  signUp: (body: { email: string; password: string; name: string; challenge: string; website: string }) => Promise<User>
  signOut: () => Promise<void>
  updateProfile: (patch: { name?: string }) => Promise<User>
  /** Change language/theme: applied at once, and saved to the account when signed in. */
  setLanguage: (lang: LangCode) => void
  setTheme: (theme: ThemeSetting) => void
  replaceUser: (u: User | null) => void
  retry: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { lang, setLang } = useI18n()
  const { setting, setSetting } = useTheme()
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<Status>('loading')
  const [bootError, setBootError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  /** The account's saved preferences win over the device's once signed in. */
  const adopt = useCallback((u: User) => {
    setUser(u)
    setStatus('signed-in')
    if (isLang(u.language)) setLang(u.language)
    setSetting(u.theme)
  }, [setLang, setSetting])

  useEffect(() => {
    let cancelled = false
    setStatus('loading')
    setBootError(null)
    api.csrf().catch(() => undefined)
      .then(() => api.session())
      .then(({ user: u }) => {
        if (cancelled) return
        if (u) adopt(u)
        else { setUser(null); setStatus('signed-out') }
      })
      .catch((err) => {
        if (cancelled) return
        const e = toApiError(err)
        setUser(null)
        setStatus('signed-out')
        if (e.status !== 401) setBootError(e.message)
      })
    return () => { cancelled = true }
  }, [adopt, attempt])

  useEffect(() => {
    const onUnauthorized = () => { setUser(null); setStatus('signed-out') }
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized)
  }, [])

  const value = useMemo<AuthState>(() => ({
    user,
    status,
    bootError,
    signIn: async (email, password, remember) => {
      const u = await api.signIn(email, password, remember)
      adopt(u)
      return u
    },
    signUp: async (body) => {
      // A new account starts with the language and theme the visitor already chose on this device.
      const u = await api.signUp({ ...body, language: lang, theme: setting })
      adopt(u)
      return u
    },
    signOut: async () => {
      try { await api.signOut() } finally { setUser(null); setStatus('signed-out') }
    },
    updateProfile: async (patch) => {
      const u = await api.updateProfile(patch)
      setUser(u)
      return u
    },
    setLanguage: (next) => {
      setLang(next)
      if (user) api.updateProfile({ language: next }).then(setUser).catch(() => { /* kept locally */ })
    },
    setTheme: (next) => {
      setSetting(next)
      if (user) api.updateProfile({ theme: next }).then(setUser).catch(() => { /* kept locally */ })
    },
    replaceUser: (u) => { setUser(u); setStatus(u ? 'signed-in' : 'signed-out') },
    retry: () => setAttempt((n) => n + 1),
  }), [user, status, bootError, adopt, lang, setting, setLang, setSetting])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
