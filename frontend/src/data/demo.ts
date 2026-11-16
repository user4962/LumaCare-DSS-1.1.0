import type {
  AlertItem,
  AuditEvent,
  Decision,
  Device,
  OverviewData,
  Patient,
  Protocol,
  SessionSnapshot,
  Telemetry,
} from '../types'

export const demoPatients: Patient[] = [
  {
    id: 'pat-1001', mrn: 'LC-10482', name: 'Amelia Carter', date_of_birth: '1987-04-16', sex: 'Female',
    skin_phototype: 2, indication: 'Plaque psoriasis', risk_level: 'moderate', adherence_percent: 94,
    active_protocol: 'NB-UVB Psoriasis Induction', last_session_at: '2026-07-13T08:42:00Z', consent_status: 'active',
    contraindications: ['Photosensitizing medication review required'], completed_sessions: 18, clinical_context_available: true,
  },
  {
    id: 'pat-1002', mrn: 'LC-11806', name: 'Noah Bennett', date_of_birth: '1994-11-03', sex: 'Male',
    skin_phototype: 3, indication: 'Seasonal affective disorder', risk_level: 'low', adherence_percent: 88,
    active_protocol: 'Bright Light Morning Phase', last_session_at: '2026-07-13T06:55:00Z', consent_status: 'active',
    contraindications: [], completed_sessions: 11, clinical_context_available: true,
  },
  {
    id: 'pat-1003', mrn: 'LC-12147', name: 'Sophia Nguyen', date_of_birth: '1978-09-22', sex: 'Female',
    skin_phototype: 4, indication: 'Chronic wound adjunct', risk_level: 'high', adherence_percent: 76,
    active_protocol: 'Red/NIR Wound Support', last_session_at: '2026-07-12T15:18:00Z', consent_status: 'active',
    contraindications: ['Reduced thermal sensation', 'Peripheral vascular disease'], completed_sessions: 7, clinical_context_available: true,
  },
  {
    id: 'pat-1004', mrn: 'LC-12792', name: 'Liam Ortiz', date_of_birth: '2001-02-09', sex: 'Male',
    skin_phototype: 5, indication: 'Atopic dermatitis', risk_level: 'moderate', adherence_percent: 81,
    active_protocol: 'NB-UVB Dermatitis Maintenance', last_session_at: '2026-07-11T12:06:00Z', consent_status: 'pending',
    contraindications: [], completed_sessions: 23, clinical_context_available: true,
  },
  {
    id: 'pat-1005', mrn: 'LC-13103', name: 'Emma Wilson', date_of_birth: '1966-06-30', sex: 'Female',
    skin_phototype: 1, indication: 'Plaque psoriasis', risk_level: 'high', adherence_percent: 69,
    active_protocol: 'NB-UVB Psoriasis Induction', last_session_at: '2026-07-10T09:34:00Z', consent_status: 'expired',
    contraindications: ['History of melanoma'], completed_sessions: 4, clinical_context_available: true,
  },
]

export const demoDevices: Device[] = [
  { id: 'dev-201', serial_number: 'LUX-NB-240118', label: 'Therapy Bay 01', model: 'LumaPanel UVB-311', status: 'online', assigned_patient_id: 'pat-1001', battery_percent: 100, firmware_version: '3.4.2', last_seen_at: '2026-07-13T10:18:42Z', calibration_due_at: '2026-09-02', wavelength_nm: null, irradiance_mw_cm2: 8.4, operating_hours: 1842, signal_rssi: -48 },
  { id: 'dev-202', serial_number: 'LUX-RN-240207', label: 'Therapy Bay 02', model: 'LumaPanel Red/NIR', status: 'online', assigned_patient_id: 'pat-1003', battery_percent: 92, firmware_version: '3.4.2', last_seen_at: '2026-07-13T10:18:38Z', calibration_due_at: '2026-08-18', wavelength_nm: null, irradiance_mw_cm2: 32.1, operating_hours: 1267, signal_rssi: -55 },
  { id: 'dev-203', serial_number: 'LUX-BL-231114', label: 'Home Kit 14', model: 'LumaBright 10K', status: 'online', assigned_patient_id: 'pat-1002', battery_percent: 78, firmware_version: '2.9.7', last_seen_at: '2026-07-13T10:16:04Z', calibration_due_at: '2026-11-12', wavelength_nm: null, irradiance_mw_cm2: 4.8, operating_hours: 742, signal_rssi: -64 },
  { id: 'dev-204', serial_number: 'LUX-NB-230901', label: 'Therapy Bay 04', model: 'LumaPanel UVB-311', status: 'maintenance', battery_percent: 100, firmware_version: '3.3.9', last_seen_at: '2026-07-13T07:41:12Z', calibration_due_at: '2026-07-15', wavelength_nm: null, irradiance_mw_cm2: 7.6, operating_hours: 2311, signal_rssi: -71 },
  { id: 'dev-205', serial_number: 'LUX-NB-240309', label: 'Home Kit 21', model: 'LumaHand UVB-311', status: 'offline', assigned_patient_id: 'pat-1004', battery_percent: 21, firmware_version: '3.4.1', last_seen_at: '2026-07-12T19:22:31Z', calibration_due_at: '2026-10-03', wavelength_nm: null, irradiance_mw_cm2: 6.2, operating_hours: 386, signal_rssi: -88 },
]

export const demoProtocols: Protocol[] = [
  { id: 'pro-301', code: 'UVB-PSO-IND', name: 'NB-UVB Psoriasis Induction', indication: 'Plaque psoriasis', wavelength_nm: 311, wavelength_tolerance_nm: 2, target_irradiance_mw_cm2: 8.25, target_dose_j_cm2: 1.5, max_session_dose_j_cm2: 1.875, irradiance_min_mw_cm2: 7.5, irradiance_max_mw_cm2: 9.0, duration_max_min: 4.0, skin_temperature_max_c: 39.0, spo2_min_percent: 94, sessions_per_week: 3, version: '2.3', status: 'active', evidence_label: 'Synthetic research prescription UVB-PSO-IND', updated_at: '2026-05-21' },
  { id: 'pro-302', code: 'BLT-SAD-AM', name: 'Bright Light Morning Phase', indication: 'Seasonal affective disorder', wavelength_nm: 480, wavelength_tolerance_nm: 25, target_irradiance_mw_cm2: 4.85, target_dose_j_cm2: 8.64, max_session_dose_j_cm2: 10.8, irradiance_min_mw_cm2: 4.5, irradiance_max_mw_cm2: 5.2, duration_max_min: 30, skin_temperature_max_c: 38.5, spo2_min_percent: 94, sessions_per_week: 7, version: '1.8', status: 'active', evidence_label: 'Synthetic research prescription BLT-SAD-AM', updated_at: '2026-03-08' },
  { id: 'pro-303', code: 'RN-WND-ADJ', name: 'Red/NIR Wound Support', indication: 'Chronic wound adjunct', wavelength_nm: 660, wavelength_tolerance_nm: 10, target_irradiance_mw_cm2: 31.5, target_dose_j_cm2: 12.0, max_session_dose_j_cm2: 15.0, irradiance_min_mw_cm2: 28, irradiance_max_mw_cm2: 35, duration_max_min: 8, skin_temperature_max_c: 38.0, spo2_min_percent: 92, sessions_per_week: 4, version: '1.4', status: 'active', evidence_label: 'Synthetic research prescription RN-WND-ADJ', updated_at: '2026-06-17' },
  { id: 'pro-304', code: 'UVB-AD-MNT', name: 'NB-UVB Dermatitis Maintenance', indication: 'Atopic dermatitis', wavelength_nm: 311, wavelength_tolerance_nm: 2, target_irradiance_mw_cm2: 6.4, target_dose_j_cm2: 0.9, max_session_dose_j_cm2: 1.125, irradiance_min_mw_cm2: 5.8, irradiance_max_mw_cm2: 7.0, duration_max_min: 3.5, skin_temperature_max_c: 39.0, spo2_min_percent: 94, sessions_per_week: 2, version: '3.1', status: 'active', evidence_label: 'Synthetic research prescription UVB-AD-MNT', updated_at: '2026-04-29' },
]

export const demoAlerts: AlertItem[] = [
  { id: 'alt-401', severity: 'critical', status: 'open', code: 'TEMP-HIGH', title: 'Skin temperature safety threshold', description: 'Observed 38.4 °C against the 38.0 °C protocol ceiling. Session was placed on hold automatically.', patient_id: 'pat-1003', patient_name: 'Sophia Nguyen', device_id: 'dev-202', created_at: '2026-07-13T10:12:18Z' },
  { id: 'alt-402', severity: 'warning', status: 'open', code: 'CAL-DUE', title: 'Calibration window approaching', description: 'Therapy Bay 04 requires optical calibration within 48 hours.', device_id: 'dev-204', created_at: '2026-07-13T08:31:04Z' },
  { id: 'alt-403', severity: 'warning', status: 'acknowledged', code: 'DOSE-VARIANCE', title: 'Delivered dose variance', description: 'Dose delivery ended 7.1% below the prescribed target after a connectivity interruption.', patient_id: 'pat-1004', patient_name: 'Liam Ortiz', device_id: 'dev-205', created_at: '2026-07-12T19:24:10Z', acknowledged_at: '2026-07-13T07:06:00Z', acknowledged_by: 'research-demo-user' },
  { id: 'alt-404', severity: 'info', status: 'resolved', code: 'FW-AVAILABLE', title: 'Validated firmware available', description: 'Firmware 3.4.2 passed the deployment compatibility policy.', device_id: 'dev-205', created_at: '2026-07-12T14:45:00Z' },
]

export const demoOverview: OverviewData = {
  recent_alerts: demoAlerts,
  active_sessions: 3, connected_devices: 3, total_devices: 5, patients_in_program: 48, adherence_percent: 86.7,
  open_alerts: 2, critical_alerts: 1, sessions_today: 17, dose_completion_percent: 92.4,
  weekly_sessions: [
    { day: 'Mon', completed: 26, adjusted: 3, held: 1 }, { day: 'Tue', completed: 31, adjusted: 4, held: 2 },
    { day: 'Wed', completed: 28, adjusted: 2, held: 1 }, { day: 'Thu', completed: 35, adjusted: 5, held: 1 },
    { day: 'Fri', completed: 32, adjusted: 3, held: 2 }, { day: 'Sat', completed: 21, adjusted: 2, held: 0 },
    { day: 'Sun', completed: 17, adjusted: 1, held: 1 },
  ],
  device_health: [
    { label: 'Online', value: 3, color: '#15a899' }, { label: 'Maintenance', value: 1, color: '#f2a65a' }, { label: 'Offline', value: 1, color: '#e76f6b' },
  ],
  active_session_summaries: [
    { id: 'ses-demo-9001', patient_label: 'Amelia Carter', protocol_label: 'NB-UVB Psoriasis Induction', delivered_dose_j_cm2: 0.52, progress_percent: 35, decision: 'ALLOW' },
    { id: 'ses-demo-9002', patient_label: 'Noah Bennett', protocol_label: 'Bright Light Morning Phase', delivered_dose_j_cm2: 5.36, progress_percent: 62, decision: 'ADJUST' },
    { id: 'ses-demo-9003', patient_label: 'Sophia Nguyen', protocol_label: 'Red/NIR Wound Support', delivered_dose_j_cm2: 5.64, progress_percent: 47, decision: 'HOLD' },
  ],
  recent_activity: [
    { id: 'act-1', time: '10:16', title: 'Session completed', detail: 'Amelia Carter · 1.50 J/cm² delivered', type: 'session' },
    { id: 'act-2', time: '10:12', title: 'Automatic safety hold', detail: 'Sophia Nguyen · temperature rule LC-T04', type: 'alert' },
    { id: 'act-3', time: '09:48', title: 'Device state received', detail: 'Therapy Bay 01 · reported firmware 3.4.2', type: 'device' },
    { id: 'act-4', time: '09:31', title: 'Dose adjustment recorded', detail: 'Noah Bennett · synthetic research event', type: 'session' },
  ],
}

export const demoAudit: AuditEvent[] = [
  { id: 'aud-501', timestamp: '2026-07-13T10:16:42Z', actor: 'decision-engine', actor_role: 'system', action: 'session.completed', resource_type: 'therapy_session', resource_id: 'ses-9001', outcome: 'recorded', details: { synthetic: true } },
  { id: 'aud-502', timestamp: '2026-07-13T10:12:18Z', actor: 'safety-monitor', actor_role: 'system', action: 'session.safety_hold', resource_type: 'therapy_session', resource_id: 'ses-9003', outcome: 'recorded', details: { reason: 'temperature_threshold', synthetic: true } },
  { id: 'aud-503', timestamp: '2026-07-13T09:31:06Z', actor: 'researcher-01', actor_role: 'researcher', action: 'alert.acknowledged', resource_type: 'alert', resource_id: 'alt-403', outcome: 'recorded', details: { synthetic: true } },
  { id: 'aud-504', timestamp: '2026-07-13T08:58:29Z', actor: 'simulator', actor_role: 'system', action: 'simulator.started', resource_type: 'therapy_session', resource_id: 'ses-9001', outcome: 'recorded', details: { scenario: 'nominal', synthetic: true } },
  { id: 'aud-505', timestamp: '2026-07-13T08:17:11Z', actor: 'demo-seeder', actor_role: 'system', action: 'dataset.seeded', resource_type: 'dataset', resource_id: 'deterministic-demo-v1', outcome: 'recorded', details: { synthetic: true, research_use_only: true } },
]

export const normalDecision: Decision = {
  action: 'ALLOW', confidence: 0.97,
  explanation: 'Current telemetry remains within the active protocol envelope. Dose delivery may continue under continuous sensor supervision.',
  fired_rules: [
    { id: 'LC-WL01', label: 'Wavelength conformity', severity: 'pass', observed: '311 nm', threshold: '309–313 nm' },
    { id: 'LC-IR02', label: 'Irradiance envelope', severity: 'pass', observed: '8.4 mW/cm²', threshold: '7.5–9.0 mW/cm²' },
    { id: 'LC-T04', label: 'Skin temperature ceiling', severity: 'pass', observed: '36.8 °C', threshold: '< 39.0 °C' },
  ], evaluated_at: new Date().toISOString(), model_version: 'ruleset-2.3.1',
}

export const initialTelemetry: Telemetry = {
  timestamp: new Date().toISOString(), elapsed_seconds: 62, wavelength_nm: 311,
  irradiance_mw_cm2: 8.4, cumulative_dose_j_cm2: 0.52, skin_temperature_c: 36.8, spo2_percent: 98,
}

export const demoSession: SessionSnapshot = {
  id: 'ses-demo-9001', status: 'active', patient_id: 'pat-1001', patient_name: 'Amelia Carter',
  device_id: 'dev-201', device_label: 'Therapy Bay 01', protocol_id: 'pro-301', protocol_name: 'NB-UVB Psoriasis Induction',
  started_at: new Date(Date.now() - 62_000).toISOString(), telemetry: initialTelemetry, decision: normalDecision,
}

export const createTelemetryPoint = (previous: Telemetry, scenario: 'normal' | 'heat' | 'motion' | 'spo2' | 'irradiance' = 'normal'): Telemetry => {
  const elapsed = previous.elapsed_seconds + 1
  const heatRise = scenario === 'heat' ? 0.24 : 0.015
  const doseIncrement = previous.irradiance_mw_cm2 / 1000
  return {
    timestamp: new Date().toISOString(), elapsed_seconds: elapsed,
    wavelength_nm: 311 + (Math.random() - 0.5) * 0.4,
    irradiance_mw_cm2: scenario === 'motion' ? 0 : scenario === 'irradiance' ? 10.2 + Math.random() * 0.5 : 8.25 + Math.random() * 0.3,
    cumulative_dose_j_cm2: Math.min(1.5, previous.cumulative_dose_j_cm2 + doseIncrement),
    skin_temperature_c: Math.min(40.5, previous.skin_temperature_c + heatRise + (Math.random() - 0.5) * 0.04),
    spo2_percent: scenario === 'spo2' ? Math.max(89, previous.spo2_percent - 0.8) : 97 + Math.random(),
  }
}

export const decisionForTelemetry = (telemetry: Telemetry): Decision => {
  if (telemetry.skin_temperature_c >= 39 || telemetry.spo2_percent < 94) {
    const temperatureBreach = telemetry.skin_temperature_c >= 39
    return {
      action: 'HOLD', confidence: 0.99,
      explanation: temperatureBreach
        ? 'Skin temperature reached the protocol safety ceiling. Emission is suspended pending clinician assessment.'
        : 'Peripheral oxygen saturation crossed the configured safety floor. Emission is suspended pending signal verification.',
      fired_rules: [{
        id: temperatureBreach ? 'LC-T04' : 'LC-O05',
        label: temperatureBreach ? 'Skin temperature ceiling' : 'SpO₂ safety floor', severity: 'block',
        observed: temperatureBreach ? `${telemetry.skin_temperature_c.toFixed(1)} °C` : `${telemetry.spo2_percent.toFixed(0)}%`,
        threshold: temperatureBreach ? '< 39.0 °C' : '≥ 94%',
      }], evaluated_at: new Date().toISOString(), model_version: 'ruleset-2.3.1',
    }
  }
  if (telemetry.irradiance_mw_cm2 < 7.5 || telemetry.irradiance_mw_cm2 > 9) {
    return {
      action: 'ADJUST', confidence: 0.94,
      explanation: 'Measured irradiance is outside the protocol delivery envelope. Restore a configured output level before continuing.',
      fired_rules: [{ id: 'LC-IR02', label: 'Irradiance envelope', severity: 'warning', observed: `${telemetry.irradiance_mw_cm2.toFixed(1)} mW/cm²`, threshold: '7.5–9.0 mW/cm²' }],
      evaluated_at: new Date().toISOString(), model_version: 'ruleset-2.3.1',
    }
  }
  return { ...normalDecision, evaluated_at: new Date().toISOString() }
}

export const buildDemoFhirBundle = () => ({
  resourceType: 'Bundle', type: 'collection', timestamp: new Date().toISOString(),
  identifier: { system: 'urn:lumacare:export', value: `LC-${Date.now()}` },
  entry: [
    { fullUrl: 'urn:uuid:pat-1001', resource: { resourceType: 'Patient', id: 'pat-1001', identifier: [{ system: 'urn:lumacare:mrn', value: 'LC-10482' }], name: [{ text: 'Amelia Carter' }] } },
    { fullUrl: 'urn:uuid:dev-201', resource: { resourceType: 'Device', id: 'dev-201', status: 'active', deviceName: [{ name: 'Therapy Bay 01', type: 'user-friendly-name' }] } },
    { fullUrl: 'urn:uuid:pro-301', resource: { resourceType: 'ServiceRequest', id: 'pro-301', status: 'active', intent: 'plan', code: { text: 'Synthetic research light-therapy protocol' }, subject: { reference: 'Patient/pat-1001' } } },
    { fullUrl: 'urn:uuid:ses-demo-9001', resource: { resourceType: 'Procedure', id: 'ses-demo-9001', status: 'in-progress', code: { text: 'Synthetic research light-therapy session' }, subject: { reference: 'Patient/pat-1001' }, basedOn: [{ reference: 'ServiceRequest/pro-301' }], usedReference: [{ reference: 'Device/dev-201' }] } },
    { fullUrl: 'urn:uuid:telemetry-1', resource: { resourceType: 'Observation', id: 'telemetry-1', status: 'final', code: { text: 'Light-therapy device telemetry panel' }, subject: { reference: 'Patient/pat-1001' }, focus: [{ reference: 'Procedure/ses-demo-9001' }] } },
    { fullUrl: 'urn:uuid:decision-1', resource: { resourceType: 'DetectedIssue', id: 'decision-1', status: 'final', severity: 'low', code: { text: 'Decision-support action: ALLOW' }, implicated: [{ reference: 'Procedure/ses-demo-9001' }] } },
  ],
})
