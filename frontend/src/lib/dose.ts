import type { Protocol } from '../types'

export function calculateDosePlan(protocol: Protocol, irradiance: number) {
  const adjustedDose = protocol.target_dose_j_cm2
  const durationSeconds = irradiance > 0 ? adjustedDose * 1000 / irradiance : 0
  const inIrradianceRange = irradiance >= protocol.irradiance_min_mw_cm2 && irradiance <= protocol.irradiance_max_mw_cm2
  const withinDuration = durationSeconds <= protocol.duration_max_min * 60
  return { adjustedDose, durationSeconds, inIrradianceRange, withinDuration, eligible: inIrradianceRange && withinDuration && irradiance > 0 }
}
