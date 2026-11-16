import { describe, expect, it } from 'vitest'
import { demoProtocols } from '../data/demo'
import { calculateDosePlan } from './dose'

describe('calculateDosePlan', () => {
  it('converts target dose and irradiance into exposure seconds', () => {
    const plan = calculateDosePlan(demoProtocols[0], 8.4)
    expect(plan.durationSeconds).toBeCloseTo(178.57, 2)
    expect(plan.adjustedDose).toBe(1.5)
    expect(plan.eligible).toBe(true)
  })

  it('blocks an estimate outside the prescription irradiance envelope', () => {
    const plan = calculateDosePlan(demoProtocols[0], 3)
    expect(plan.inIrradianceRange).toBe(false)
    expect(plan.eligible).toBe(false)
  })
})
