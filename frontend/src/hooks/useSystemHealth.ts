import { useEffect, useState } from 'react'
import { api } from '../lib/api'

type HealthState = 'checking' | 'ready' | 'offline'

export function useSystemHealth() {
  const [state, setState] = useState<HealthState>('checking')
  const [checkedAt, setCheckedAt] = useState<Date | null>(null)

  useEffect(() => {
    let active = true
    const probe = async () => {
      try {
        const response = await api.get<{ status: string; database: string }>('/health')
        if (!active) return
        setState(response.status === 'ok' && response.database === 'ok' ? 'ready' : 'offline')
      } catch {
        if (active) setState('offline')
      } finally {
        if (active) setCheckedAt(new Date())
      }
    }

    void probe()
    const interval = window.setInterval(() => void probe(), 30_000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [])

  return { state, checkedAt }
}
