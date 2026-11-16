import { describe, expect, it } from 'vitest'
import { mapDecision, mapPatient, mapProtocol, mapTelemetry } from './mappers'

describe('backend contract mappers', () => {
  it('maps a PatientRead record without inventing unavailable clinical fields', () => {
    const patient = mapPatient({
      id: 'patient-1', medical_record_number: 'DEMO-001', given_name: 'Olena', family_name: 'Koval',
      date_of_birth: '1987-04-18', administrative_sex: 'female', updated_at: '2026-07-13T08:00:00Z',
    })
    expect(patient.name).toBe('Olena Koval')
    expect(patient.skin_phototype).toBeNull()
    expect(patient.risk_level).toBe('unclassified')
    expect(patient.clinical_context_available).toBe(false)
  })

  it('derives the irradiance envelope from backend tolerance percent', () => {
    const protocol = mapProtocol({
      id: 'rx-1', patient_id: 'patient-1', protocol_name: 'Research protocol A', indication_code: 'research-demo',
      target_wavelength_nm: 660, target_irradiance_mw_cm2: 24, target_dose_j_cm2: 4,
      irradiance_tolerance_percent: 10, max_duration_seconds: 900, max_skin_temperature_c: 41,
      min_spo2_percent: 94, status: 'active', protocol_version: 'demo-1.0', updated_at: '2026-07-13T08:00:00Z',
    })
    expect(protocol.irradiance_min_mw_cm2).toBe(21.6)
    expect(protocol.irradiance_max_mw_cm2).toBe(26.4)
    expect(protocol.patient_id).toBe('patient-1')
  })

  it('maps WebSocket telemetry and fired rule fields', () => {
    const telemetry = mapTelemetry({
      captured_at: '2026-07-13T09:15:03Z', sequence: 3, wavelength_nm: 660, irradiance_mw_cm2: 24.1,
      cumulative_dose_j_cm2: 0.36, skin_temperature_c: 36.7, spo2_percent: 97.8,
    }, '2026-07-13T09:15:00Z')
    const decision = mapDecision({
      action: 'ADJUST', confidence: 0.91, explanation: 'Output adjustment recommended.', created_at: '2026-07-13T09:15:03Z',
      engine_version: 'research-engine-1.0', recommended_irradiance_mw_cm2: 18, recommended_duration_seconds: 420, estimated_additional_dose_j_cm2: 2.1,
      fired_rules: [{ rule_id: 'IRRADIANCE_HIGH', severity: 'ADJUST', message: 'Irradiance above target.', observed: '27', threshold: '≤26.4' }],
    })
    expect(telemetry.elapsed_seconds).toBe(3)
    expect(decision.action).toBe('ADJUST')
    expect(decision.fired_rules[0]).toMatchObject({ id: 'IRRADIANCE_HIGH', severity: 'warning' })
    expect(decision.recommended_irradiance_mw_cm2).toBe(18)
  })
})
