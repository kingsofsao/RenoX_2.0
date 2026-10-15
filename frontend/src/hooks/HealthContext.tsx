import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, type ApiError, toApiError } from '../services/api'
import type { HealthResponse } from '../types/api'

interface HealthState {
  health: HealthResponse | null
  /** Set when the backend itself cannot be reached (as opposed to a degraded database). */
  error: ApiError | null
  loading: boolean
  lastChecked: Date | null
  refresh: () => void
}

const HealthContext = createContext<HealthState | null>(null)
const POLL_MS = 15_000

export function HealthProvider({ children }: { children: ReactNode }) {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastChecked, setLastChecked] = useState<Date | null>(null)

  const refresh = useCallback(() => {
    api
      .health()
      .then((h) => {
        setHealth(h)
        setError(null)
      })
      .catch((err) => {
        setHealth(null)
        setError(toApiError(err))
      })
      .finally(() => {
        setLoading(false)
        setLastChecked(new Date())
      })
  }, [])

  useEffect(() => {
    refresh()
    const timer = window.setInterval(refresh, POLL_MS)
    return () => window.clearInterval(timer)
  }, [refresh])

  return (
    <HealthContext.Provider value={{ health, error, loading, lastChecked, refresh }}>{children}</HealthContext.Provider>
  )
}

export function useHealth(): HealthState {
  const ctx = useContext(HealthContext)
  if (!ctx) throw new Error('useHealth must be used inside <HealthProvider>')
  return ctx
}
