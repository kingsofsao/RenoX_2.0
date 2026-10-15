import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, toApiError } from '../services/api'

export interface AsyncState<T> {
  data: T | null
  error: ApiError | null
  loading: boolean
  reload: () => void
}

/** Run an async loader whenever `deps` change; ignores stale responses. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const requestId = useRef(0)

  useEffect(() => {
    const id = ++requestId.current
    setLoading(true)
    loader()
      .then((result) => {
        if (id !== requestId.current) return
        setData(result)
        setError(null)
      })
      .catch((err) => {
        if (id !== requestId.current) return
        setError(toApiError(err))
      })
      .finally(() => {
        if (id === requestId.current) setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick])

  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { data, error, loading, reload }
}
