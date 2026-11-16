import type {
  AlertItem, AuditEvent, Decision, Device, OverviewData, Patient, Protocol, SessionSnapshot, Telemetry,
} from '../types'

type JsonRecord = Record<string, unknown>

const record = (value: unknown, label = 'record'): JsonRecord => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`Invalid ${label} payload.`)
  return value as JsonRecord
}

const array = (value: unknown, label: string): unknown[] => {
  if (!Array.isArray(value)) throw new Error(`Invalid ${label} payload: expected an array.`)
  return value
}

const requiredString = (value: unknown, field: string) => {
  if (typeof value !== 'string' || !value) throw new Error(`Invalid API payload: missing ${field}.`)
  return value
}

const optionalString = (value: unknown, fallback = '') => typeof value === 'string' ? value : fallback
const number = (value: unknown, fallback = 0) => typeof value === 'number' && Number.isFinite(value) ? value : fallback

const humanize = (value: string) => {
  const words = value.replace(/[._-]+/g, ' ').trim().toLowerCase().replace(/\bspo2\b/g, 'SpO2')
  return words.charAt(0).toUpperCase() + words.slice(1)
}

export const mapPatient = (value: unknown): Patient => {
  const item = record(value, 'patient')
  const sex = optionalString(item.administrative_sex, 'other')
  const normalizedSex: Patient['sex'] = sex === 'female' ? 'Female' : sex === 'male' ? 'Male' : 'Other'
  return {
    id: requiredString(item.id, 'patient.id'),
    mrn: requiredString(item.medical_record_number, 'patient.medical_record_number'),
    name: `${requiredString(item.given_name, 'patient.given_name')} ${requiredString(item.family_name, 'patient.family_name')}`,
    date_of_birth: requiredString(item.date_of_birth, 'patient.date_of_birth'),
    sex: normalizedSex,
    skin_phototype: null,
    indication: 'Research programme record',
    risk_level: 'unclassified',
    adherence_percent: null,
    active_protocol: 'Linked prescription required',
    last_session_at: optionalString(item.updated_at, new Date(0).toISOString()),
    consent_status: 'not_recorded',
    contraindications: [],
    completed_sessions: null,
    clinical_context_available: false,
  }
}

export const mapPatients = (value: unknown) => array(value, 'patients').map(mapPatient)

export const mapDevice = (value: unknown): Device => {
  const item = record(value, 'device')
  const connectivity = optionalString(item.connectivity, 'offline')
  const lifecycle = optionalString(item.status, 'available')
  const status: Device['status'] = lifecycle === 'maintenance' || connectivity === 'degraded' ? 'maintenance' : connectivity === 'online' ? 'online' : 'offline'
  const manufacturer = requiredString(item.manufacturer, 'device.manufacturer')
  const model = requiredString(item.model_name, 'device.model_name')
  return {
    id: requiredString(item.id, 'device.id'),
    serial_number: requiredString(item.serial_number, 'device.serial_number'),
    label: `${manufacturer} ${model}`,
    model,
    status,
    assigned_patient_id: typeof item.patient_id === 'string' ? item.patient_id : undefined,
    battery_percent: null,
    firmware_version: requiredString(item.firmware_version, 'device.firmware_version'),
    last_seen_at: optionalString(item.last_seen_at, optionalString(item.updated_at, new Date(0).toISOString())),
    calibration_due_at: optionalString(item.calibration_due_at, new Date(0).toISOString()),
    wavelength_nm: typeof item.wavelength_nm === 'number' ? item.wavelength_nm : null,
    irradiance_mw_cm2: null,
    operating_hours: null,
    signal_rssi: null,
  }
}

export const mapDevices = (value: unknown) => array(value, 'devices').map(mapDevice)

export const mapProtocol = (value: unknown): Protocol => {
  const item = record(value, 'prescription')
  const targetIrradiance = number(item.target_irradiance_mw_cm2)
  const tolerance = number(item.irradiance_tolerance_percent, 10) / 100
  const sourceStatus = optionalString(item.status, 'draft')
  return {
    id: requiredString(item.id, 'prescription.id'),
    patient_id: typeof item.patient_id === 'string' ? item.patient_id : undefined,
    device_id: typeof item.device_id === 'string' ? item.device_id : undefined,
    code: optionalString(item.indication_code, 'research-demo').toUpperCase(),
    name: requiredString(item.protocol_name, 'prescription.protocol_name'),
    indication: optionalString(item.indication_code, 'research-demo'),
    wavelength_nm: number(item.target_wavelength_nm),
    wavelength_tolerance_nm: number(item.wavelength_tolerance_nm),
    target_irradiance_mw_cm2: targetIrradiance,
    target_dose_j_cm2: number(item.target_dose_j_cm2),
    max_session_dose_j_cm2: number(item.max_session_dose_j_cm2, number(item.target_dose_j_cm2)),
    irradiance_min_mw_cm2: Number((targetIrradiance * (1 - tolerance)).toFixed(2)),
    irradiance_max_mw_cm2: Number((targetIrradiance * (1 + tolerance)).toFixed(2)),
    duration_max_min: number(item.max_duration_seconds) / 60,
    skin_temperature_max_c: number(item.max_skin_temperature_c),
    spo2_min_percent: number(item.min_spo2_percent),
    sessions_per_week: 0,
    version: optionalString(item.protocol_version, 'unversioned'),
    status: sourceStatus === 'active' ? 'active' : sourceStatus === 'draft' ? 'draft' : 'retired',
    evidence_label: 'Research-only prescription record',
    updated_at: optionalString(item.updated_at, optionalString(item.valid_from, new Date(0).toISOString())),
  }
}

export const mapProtocols = (value: unknown) => array(value, 'protocols').map(mapProtocol)

export const mapAlert = (value: unknown): AlertItem => {
  const item = record(value, 'alert')
  const severity = optionalString(item.severity, 'info') as AlertItem['severity']
  const code = requiredString(item.code, 'alert.code')
  return {
    id: requiredString(item.id, 'alert.id'),
    severity,
    status: optionalString(item.status, 'open') as AlertItem['status'],
    code,
    title: humanize(code),
    description: requiredString(item.message, 'alert.message'),
    patient_id: typeof item.patient_id === 'string' ? item.patient_id : undefined,
    device_id: undefined,
    created_at: requiredString(item.created_at, 'alert.created_at'),
    acknowledged_at: typeof item.acknowledged_at === 'string' ? item.acknowledged_at : undefined,
    acknowledged_by: typeof item.acknowledged_by === 'string' ? item.acknowledged_by : undefined,
  }
}

export const mapAlerts = (value: unknown) => array(value, 'alerts').map(mapAlert)

export const mapAuditEvent = (value: unknown): AuditEvent => {
  const item = record(value, 'audit event')
  return {
    id: requiredString(item.id, 'audit.id'),
    timestamp: requiredString(item.occurred_at, 'audit.occurred_at'),
    actor: requiredString(item.actor_id, 'audit.actor_id'),
    actor_role: requiredString(item.actor_role, 'audit.actor_role'),
    action: requiredString(item.event_type, 'audit.event_type'),
    resource_type: requiredString(item.entity_type, 'audit.entity_type'),
    resource_id: requiredString(item.entity_id, 'audit.entity_id'),
    outcome: 'recorded',
    details: item.details && typeof item.details === 'object' && !Array.isArray(item.details) ? item.details as Record<string, unknown> : {},
  }
}

export const mapAudit = (value: unknown) => array(value, 'audit').map(mapAuditEvent)

export const mapTelemetry = (value: unknown, startedAt?: string): Telemetry => {
  const item = record(value, 'telemetry')
  const capturedAt = requiredString(item.captured_at, 'telemetry.captured_at')
  const elapsedFromStart = startedAt ? Math.max(0, Math.round((new Date(capturedAt).getTime() - new Date(startedAt).getTime()) / 1000)) : number(item.sequence)
  return {
    timestamp: capturedAt,
    elapsed_seconds: elapsedFromStart,
    wavelength_nm: number(item.wavelength_nm),
    irradiance_mw_cm2: number(item.irradiance_mw_cm2),
    cumulative_dose_j_cm2: number(item.cumulative_dose_j_cm2),
    skin_temperature_c: number(item.skin_temperature_c),
    spo2_percent: number(item.spo2_percent),
  }
}

const ruleSeverity = (severity: string): Decision['fired_rules'][number]['severity'] => {
  if (severity === 'HOLD') return 'block'
  if (severity === 'COMPLETE') return 'complete'
  if (severity === 'INFO') return 'info'
  return 'warning'
}

const decisionActions: Decision['action'][] = ['ALLOW', 'ADJUST', 'COMPLETE', 'HOLD']

export const mapDecision = (value: unknown): Decision => {
  const item = record(value, 'decision')
  const action = requiredString(item.action, 'decision.action') as Decision['action']
  const rules = Array.isArray(item.fired_rules) ? item.fired_rules.map((rawRule, index) => {
    const rule = record(rawRule, `decision.fired_rules[${index}]`)
    const severity = optionalString(rule.severity)
    return {
      id: optionalString(rule.rule_id, `RULE-${index + 1}`),
      label: optionalString(rule.message, optionalString(rule.rule_id, 'Activated rule')),
      severity: ruleSeverity(severity),
      observed: optionalString(rule.observed, 'Recorded'),
      threshold: optionalString(rule.threshold, 'Configured threshold'),
    }
  }) : []
  return {
    action,
    confidence: number(item.confidence),
    recommended_irradiance_mw_cm2: typeof item.recommended_irradiance_mw_cm2 === 'number' ? item.recommended_irradiance_mw_cm2 : undefined,
    recommended_duration_seconds: typeof item.recommended_duration_seconds === 'number' ? item.recommended_duration_seconds : undefined,
    estimated_additional_dose_j_cm2: typeof item.estimated_additional_dose_j_cm2 === 'number' ? item.estimated_additional_dose_j_cm2 : undefined,
    explanation: requiredString(item.explanation, 'decision.explanation'),
    fired_rules: rules,
    evaluated_at: requiredString(item.created_at, 'decision.created_at'),
    model_version: optionalString(item.engine_version, 'research-engine'),
  }
}

export const mapSessionRead = (value: unknown, context: { patient: Patient; device: Device; protocol: Protocol }): SessionSnapshot => {
  const item = record(value, 'session')
  const backendStatus = requiredString(item.status, 'session.status')
  const status: SessionSnapshot['status'] = backendStatus === 'running' ? 'active' : backendStatus === 'safety_hold' ? 'paused' : backendStatus === 'completed' ? 'completed' : backendStatus === 'stopped' ? 'stopped' : 'idle'
  const startedAt = typeof item.started_at === 'string' ? item.started_at : undefined
  const telemetry: Telemetry = {
    timestamp: new Date().toISOString(), elapsed_seconds: 0, wavelength_nm: context.protocol.wavelength_nm,
    irradiance_mw_cm2: 0, cumulative_dose_j_cm2: number(item.delivered_dose_j_cm2), skin_temperature_c: 36.5, spo2_percent: 98,
  }
  return {
    id: requiredString(item.id, 'session.id'), status,
    patient_id: context.patient.id, patient_name: context.patient.name,
    device_id: context.device.id, device_label: context.device.label,
    protocol_id: context.protocol.id, protocol_name: context.protocol.name,
    started_at: startedAt, telemetry,
    decision: {
      action: 'HOLD', confidence: 0,
      explanation: 'Awaiting the first telemetry sample and deterministic rule evaluation. Emission state remains pending.',
      fired_rules: [], evaluated_at: new Date().toISOString(), model_version: `pending · ${context.protocol.version}`,
    },
  }
}

export const mapDashboard = (value: unknown): OverviewData => {
  const root = record(value, 'dashboard')
  const counts = record(root.counts, 'dashboard.counts')
  const snapshots = Array.isArray(root.active_sessions) ? root.active_sessions : []
  const activeDeviceIds = new Set(snapshots.map((snapshot) => {
    const session = record(record(snapshot, 'session snapshot').session, 'session snapshot.session')
    return optionalString(session.device_id)
  }).filter(Boolean))
  const activeSessionSummaries = snapshots.map((snapshot, index) => {
    const snapshotRecord = record(snapshot, `session snapshot ${index + 1}`)
    const session = record(snapshotRecord.session, `session snapshot ${index + 1}.session`)
    const latestDecision = snapshotRecord.latest_decision && typeof snapshotRecord.latest_decision === 'object'
      ? record(snapshotRecord.latest_decision, `session snapshot ${index + 1}.latest_decision`)
      : null
    const patientId = requiredString(session.patient_id, 'session.patient_id')
    const prescriptionId = requiredString(session.prescription_id, 'session.prescription_id')
    const plannedDuration = Math.max(1, number(session.planned_duration_seconds, 1))
    const startedAt = typeof session.started_at === 'string' ? Date.parse(session.started_at) : Number.NaN
    const elapsedSeconds = Number.isFinite(startedAt) ? Math.max(0, (Date.now() - startedAt) / 1000) : 0
    const action = optionalString(latestDecision?.action, 'HOLD') as Decision['action']
    const decision: Decision['action'] = decisionActions.includes(action) ? action : 'HOLD'
    return {
      id: requiredString(session.id, 'session.id'),
      patient_id: patientId,
      prescription_id: prescriptionId,
      started_at: typeof session.started_at === 'string' ? session.started_at : undefined,
      patient_label: `Patient …${patientId.slice(-8)}`,
      protocol_label: `Prescription …${prescriptionId.slice(-8)}`,
      delivered_dose_j_cm2: number(session.delivered_dose_j_cm2),
      progress_percent: Math.min(100, elapsedSeconds / plannedDuration * 100),
      decision,
    }
  })
  const deviceCount = number(counts.devices)
  const recentAlerts = Array.isArray(root.recent_alerts) ? root.recent_alerts.map(mapAlert) : []
  return {
    active_sessions: number(counts.running_sessions),
    connected_devices: activeDeviceIds.size,
    total_devices: deviceCount,
    patients_in_program: number(counts.patients),
    adherence_percent: null,
    open_alerts: number(counts.open_alerts),
    critical_alerts: recentAlerts.filter((alert) => alert.status === 'open' && alert.severity === 'critical').length,
    sessions_today: number(counts.sessions),
    dose_completion_percent: null,
    weekly_sessions: [],
    recent_alerts: recentAlerts,
    device_health: [
      { label: 'Running-session devices', value: activeDeviceIds.size, color: '#15a899' },
      { label: 'Other registered devices', value: Math.max(0, deviceCount - activeDeviceIds.size), color: '#8294aa' },
    ],
    active_session_summaries: activeSessionSummaries,
    recent_activity: recentAlerts.slice(0, 5).map((alert) => ({
      id: alert.id,
      time: new Date(alert.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      title: alert.title,
      detail: `${alert.code} · ${alert.status}`,
      type: 'alert' as const,
    })),
  }
}
