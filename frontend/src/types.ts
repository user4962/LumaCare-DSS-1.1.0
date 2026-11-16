export type RiskLevel = 'low' | 'moderate' | 'high' | 'unclassified'
export type ConnectionStatus = 'online' | 'offline' | 'maintenance'
export type DecisionAction = 'ALLOW' | 'ADJUST' | 'COMPLETE' | 'HOLD'
export type AlertSeverity = 'critical' | 'high' | 'warning' | 'info'

export interface Patient {
  id: string
  mrn: string
  name: string
  date_of_birth: string
  sex: 'Female' | 'Male' | 'Other'
  skin_phototype: 1 | 2 | 3 | 4 | 5 | 6 | null
  indication: string
  risk_level: RiskLevel
  adherence_percent: number | null
  active_protocol: string
  last_session_at: string
  consent_status: 'active' | 'pending' | 'expired' | 'not_recorded'
  contraindications: string[]
  completed_sessions: number | null
  clinical_context_available: boolean
}

export interface Device {
  id: string
  serial_number: string
  label: string
  model: string
  status: ConnectionStatus
  assigned_patient_id?: string
  battery_percent: number | null
  firmware_version: string
  last_seen_at: string
  calibration_due_at: string
  wavelength_nm: number | null
  irradiance_mw_cm2: number | null
  operating_hours: number | null
  signal_rssi: number | null
}

export interface Protocol {
  id: string
  patient_id?: string
  device_id?: string
  code: string
  name: string
  indication: string
  wavelength_nm: number
  wavelength_tolerance_nm: number
  target_irradiance_mw_cm2: number
  target_dose_j_cm2: number
  max_session_dose_j_cm2: number
  irradiance_min_mw_cm2: number
  irradiance_max_mw_cm2: number
  duration_max_min: number
  skin_temperature_max_c: number
  spo2_min_percent: number
  sessions_per_week: number
  version: string
  status: 'active' | 'draft' | 'retired'
  evidence_label: string
  updated_at: string
}

export interface AlertItem {
  id: string
  severity: AlertSeverity
  status: 'open' | 'acknowledged' | 'resolved'
  code: string
  title: string
  description: string
  patient_id?: string
  patient_name?: string
  device_id?: string
  created_at: string
  acknowledged_at?: string
  acknowledged_by?: string
}

export interface FiredRule {
  id: string
  label: string
  severity: 'pass' | 'info' | 'warning' | 'complete' | 'block'
  observed: string
  threshold: string
}

export interface Decision {
  action: DecisionAction
  confidence: number
  recommended_irradiance_mw_cm2?: number
  recommended_duration_seconds?: number
  estimated_additional_dose_j_cm2?: number
  explanation: string
  fired_rules: FiredRule[]
  evaluated_at: string
  model_version: string
}

export interface Telemetry {
  timestamp: string
  elapsed_seconds: number
  wavelength_nm: number
  irradiance_mw_cm2: number
  cumulative_dose_j_cm2: number
  skin_temperature_c: number
  spo2_percent: number
}

export interface SessionSnapshot {
  id: string
  status: 'idle' | 'active' | 'paused' | 'completed' | 'stopped'
  patient_id: string
  patient_name: string
  device_id: string
  device_label: string
  protocol_id: string
  protocol_name: string
  started_at?: string
  telemetry: Telemetry
  decision: Decision
}

export interface OverviewData {
  active_sessions: number
  connected_devices: number
  total_devices: number
  patients_in_program: number
  adherence_percent: number | null
  open_alerts: number
  critical_alerts: number
  sessions_today: number
  dose_completion_percent: number | null
  weekly_sessions: Array<{ day: string; completed: number; adjusted: number; held: number }>
  device_health: Array<{ label: string; value: number; color: string }>
  recent_alerts: AlertItem[]
  active_session_summaries: Array<{
    id: string
    patient_id?: string
    prescription_id?: string
    started_at?: string
    patient_label: string
    protocol_label: string
    delivered_dose_j_cm2: number
    progress_percent: number
    decision: DecisionAction
  }>
  recent_activity: Array<{ id: string; time: string; title: string; detail: string; type: 'session' | 'alert' | 'device' }>
}

export interface AuditEvent {
  id: string
  timestamp: string
  actor: string
  actor_role: string
  action: string
  resource_type: string
  resource_id: string
  outcome: 'recorded'
  details: Record<string, unknown>
}

export interface ApiEnvelope<T> {
  data: T
  meta?: {
    total?: number
    page?: number
    page_size?: number
  }
}
