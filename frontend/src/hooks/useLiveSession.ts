import { useCallback, useEffect, useRef, useState } from 'react'
import { createTelemetryPoint, decisionForTelemetry, demoSession } from '../data/demo'
import { api, ApiError, DEMO_FALLBACK, WS_BASE_URL } from '../lib/api'
import { mapDecision, mapSessionRead, mapTelemetry } from '../lib/mappers'
import type { Decision, Device, Patient, Protocol, SessionSnapshot, Telemetry } from '../types'

type Scenario = 'normal' | 'heat' | 'contact' | 'spo2' | 'irradiance'
type ConnectionMode = 'connecting' | 'live' | 'demo' | 'disconnected'
type SessionSelection = { patient: Patient; device: Device; protocol: Protocol }

const backendScenario: Record<Scenario, string> = {
  normal: 'nominal',
  heat: 'temperature_rise',
  contact: 'contact_loss',
  spo2: 'spo2_drop',
  irradiance: 'irradiance_spike',
}

const statusAfterDecision = (decision: Decision, current: SessionSnapshot['status']): SessionSnapshot['status'] => {
  if (decision.action === 'HOLD') return 'paused'
  if (decision.action === 'COMPLETE') return 'completed'
  return current
}

const buildDemoHistory = (snapshot: SessionSnapshot) =>
  Array.from({ length: 32 }, (_, index) => {
    const seconds = Math.max(0, snapshot.telemetry.elapsed_seconds - (31 - index) * 2)
    const progress = seconds / Math.max(1, snapshot.telemetry.elapsed_seconds)
    return {
      ...snapshot.telemetry,
      elapsed_seconds: seconds,
      timestamp: new Date(Date.now() - (31 - index) * 2000).toISOString(),
      cumulative_dose_j_cm2: Number((snapshot.telemetry.cumulative_dose_j_cm2 * progress).toFixed(3)),
      skin_temperature_c: 36.3 + progress * 0.5 + Math.sin(index / 4) * 0.04,
      irradiance_mw_cm2: 8.3 + Math.sin(index / 3) * 0.14,
    }
  })

const HISTORY_WINDOW = 60

const appendPoint = (points: Telemetry[], point: Telemetry) =>
  points.length && points[points.length - 1].timestamp === point.timestamp
    ? points
    : [...points.slice(-(HISTORY_WINDOW - 1)), point]

export function useLiveSession() {
  const [session, setSession] = useState<SessionSnapshot>({ ...demoSession, status: 'idle' })
  const [history, setHistory] = useState<Telemetry[]>(() => buildDemoHistory(demoSession))
  const [sampleCount, setSampleCount] = useState(0)
  const sessionRef = useRef(session)
  const [connection, setConnection] = useState<ConnectionMode>('disconnected')
  const [scenario, setScenario] = useState<Scenario>('normal')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const websocketRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    sessionRef.current = session
  }, [session])

  const applySample = useCallback((telemetry: Telemetry, decision?: Decision) => {
    setHistory((points) => appendPoint(points, telemetry))
    setSampleCount((count) => count + 1)
    setSession((current) => {
      const nextDecision = decision ?? current.decision
      return { ...current, telemetry, decision: nextDecision, status: statusAfterDecision(nextDecision, current.status) }
    })
  }, [])

  useEffect(() => {
    if (session.status !== 'active' || connection !== 'demo') return
    const interval = window.setInterval(() => {
      const current = sessionRef.current
      if (current.status !== 'active') return
      const demoScenario = scenario === 'contact' ? 'motion' : scenario
      const telemetry = createTelemetryPoint(current.telemetry, demoScenario)
      applySample(telemetry, decisionForTelemetry(telemetry))
    }, 1000)
    return () => window.clearInterval(interval)
  }, [applySample, connection, scenario, session.status])

  const connectWebSocket = useCallback((sessionId: string) => {
    websocketRef.current?.close()
    setConnection('connecting')
    try {
      const socket = new WebSocket(`${WS_BASE_URL}/sessions/${sessionId}`)
      websocketRef.current = socket
      const connectionTimer = window.setTimeout(() => {
        if (socket.readyState !== WebSocket.OPEN) {
          socket.close()
          setConnection('disconnected')
          setError('The session started, but the telemetry WebSocket did not connect.')
        }
      }, 3500)

      socket.onopen = () => {
        window.clearTimeout(connectionTimer)
        setConnection('live')
      }
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as Record<string, unknown>
          if (!payload.telemetry) return
          const telemetry = mapTelemetry(payload.telemetry, sessionRef.current.started_at)
          applySample(telemetry, payload.decision ? mapDecision(payload.decision) : undefined)
        } catch (reason) {
          setError(`Telemetry payload rejected: ${(reason as Error).message}`)
        }
      }
      socket.onerror = () => {
        window.clearTimeout(connectionTimer)
        setConnection('disconnected')
        setError('The session is active, but live telemetry transport is unavailable.')
      }
      socket.onclose = () => {
        window.clearTimeout(connectionTimer)
        setConnection((current) => current === 'demo' ? current : 'disconnected')
      }
    } catch (reason) {
      setConnection('disconnected')
      setError(`Telemetry connection failed: ${(reason as Error).message}`)
    }
  }, [applySample])

  const startDemo = useCallback((selection: SessionSelection, reason: string) => {
    const now = new Date().toISOString()
    const started: SessionSnapshot = {
      ...demoSession,
      id: `ses-demo-${Date.now()}`,
      status: 'active',
      patient_id: selection.patient.id,
      patient_name: selection.patient.name,
      device_id: selection.device.id,
      device_label: selection.device.label,
      protocol_id: selection.protocol.id,
      protocol_name: selection.protocol.name,
      started_at: now,
      telemetry: {
        ...demoSession.telemetry,
        timestamp: now,
        elapsed_seconds: 0,
        wavelength_nm: selection.protocol.wavelength_nm,
        irradiance_mw_cm2: (selection.protocol.irradiance_min_mw_cm2 + selection.protocol.irradiance_max_mw_cm2) / 2,
        cumulative_dose_j_cm2: 0,
      },
    }
    sessionRef.current = started
    setSession(started)
    setHistory([started.telemetry])
    setSampleCount(1)
    setConnection('demo')
    setError(`${reason} Synthetic telemetry is active for research demonstration.`)
  }, [])

  const start = useCallback(async (selection: SessionSelection) => {
    setBusy(true)
    setError(null)
    setScenario('normal')
    try {
      const created = await api.post<unknown>('/sessions', {
        patient_id: selection.patient.id,
        device_id: selection.device.id,
        prescription_id: selection.protocol.id,
        planned_duration_seconds: Math.round(selection.protocol.duration_max_min * 60),
        simulator_seed: 20260713,
      })
      const createdId = typeof created === 'object' && created && 'id' in created && typeof created.id === 'string' ? created.id : null
      if (!createdId) throw new Error('Invalid session create payload: missing session.id.')

      const startedRaw = await api.post<unknown>(`/sessions/${createdId}/start`)
      const started = mapSessionRead(startedRaw, selection)
      sessionRef.current = started
      setSession(started)
      // The chart shows recorded samples only; the first point arrives with the first decision.
      setHistory([])
      setSampleCount(0)
      connectWebSocket(started.id)

      try {
        await api.post(`/sessions/${started.id}/simulator/start`, { scenario: 'nominal', interval_seconds: 1 })
      } catch (simulatorError) {
        setError(`Session started, but the deterministic simulator did not start: ${(simulatorError as Error).message}`)
      }
    } catch (reason) {
      const networkFailure = reason instanceof ApiError && reason.status === undefined
      if (DEMO_FALLBACK && networkFailure) startDemo(selection, (reason as Error).message)
      else {
        setConnection('disconnected')
        setError((reason as Error).message)
      }
    } finally {
      setBusy(false)
    }
  }, [connectWebSocket, startDemo])

  const stop = useCallback(async () => {
    setBusy(true)
    setError(null)
    try {
      if (!session.id.startsWith('ses-demo')) await api.post(`/sessions/${session.id}/stop`, { reason: 'operator_request' })
      websocketRef.current?.close()
      setConnection('disconnected')
      setSession((current) => ({ ...current, status: 'stopped' }))
    } catch (reason) {
      setError(`Stop request failed: ${(reason as Error).message}`)
    } finally {
      setBusy(false)
    }
  }, [session.id])

  const inject = useCallback(async (nextScenario: Scenario) => {
    setScenario(nextScenario)
    setError(null)
    if (!session.id.startsWith('ses-demo')) {
      try {
        await api.post(`/sessions/${session.id}/inject-scenario`, { scenario: backendScenario[nextScenario] })
      } catch (reason) {
        setError(`Scenario injection failed: ${(reason as Error).message}`)
      }
    }
  }, [session.id])

  const reset = useCallback(() => {
    websocketRef.current?.close()
    setConnection('disconnected')
    setError(null)
    setScenario('normal')
    setSession({ ...demoSession, status: 'idle' })
    setHistory(buildDemoHistory(demoSession))
    setSampleCount(0)
  }, [])

  useEffect(() => () => websocketRef.current?.close(), [])

  return { session, history, sampleCount, connection, scenario, busy, error, start, stop, inject, reset }
}
