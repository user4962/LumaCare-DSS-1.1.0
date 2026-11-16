import { useCallback, useEffect, useState } from 'react'
import { api, DEMO_FALLBACK } from '../lib/api'

export type DataSource = 'api' | 'demo'

interface ResourceState<T> {
  data: T
  loading: boolean
  error: string | null
  source: DataSource
  retry: () => void
}

export function useApiResource<T>(path: string, fallback: T, mapper?: (value: unknown) => T): ResourceState<T> {
  const [data, setData] = useState<T>(fallback)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [source, setSource] = useState<DataSource>('demo')
  const [attempt, setAttempt] = useState(0)

  const retry = useCallback(() => setAttempt((value) => value + 1), [])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    api.get<unknown>(path)
      .then((result) => {
        if (!active) return
        setData(mapper ? mapper(result) : result as T)
        setSource('api')
      })
      .catch((reason: Error) => {
        if (!active) return
        setError(reason.message)
        if (DEMO_FALLBACK) {
          setData(fallback)
          setSource('demo')
        }
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => { active = false }
  }, [path, attempt, fallback, mapper])

  return { data, loading, error, source, retry }
}
