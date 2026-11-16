import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { DecisionCard } from './DecisionCard'
import type { Decision } from '../types'

const decision: Decision = {
  action: 'HOLD',
  confidence: 0.99,
  recommended_irradiance_mw_cm2: 0,
  recommended_duration_seconds: 0,
  estimated_additional_dose_j_cm2: 0,
  explanation: 'Temperature reached the configured research threshold.',
  fired_rules: [{ id: 'TEMP_HOLD', label: 'Temperature ceiling', severity: 'block', observed: '41.2 °C', threshold: '≤ 41.0 °C' }],
  evaluated_at: '2026-07-13T10:00:00Z',
  model_version: 'research-engine-1.1',
}

describe('DecisionCard', () => {
  it('announces the safety action and explanation', () => {
    render(<DecisionCard decision={decision} />)
    expect(screen.getByLabelText('Decision: Stop emission')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Stop emission' })).toBeInTheDocument()
    expect(screen.getByText('Rule certainty 99%')).toHaveAttribute('title', 'Deterministic rule activation certainty; not a clinical probability')
    expect(screen.getByText(decision.explanation)).toBeInTheDocument()
  })

  it('renders rule provenance with observed and threshold values', () => {
    render(<DecisionCard decision={decision} />)
    expect(screen.getByText('TEMP_HOLD')).toBeInTheDocument()
    expect(screen.getByText('41.2 °C')).toBeInTheDocument()
    expect(screen.getByText('≤ 41.0 °C')).toBeInTheDocument()
    expect(screen.getByText('Stops')).toBeInTheDocument()
  })

  it('shows deterministic recommended outputs including zero-value holds', () => {
    render(<DecisionCard decision={decision} />)
    expect(screen.getByText('0.00 mW/cm²')).toBeInTheDocument()
    expect(screen.getByText('0 s')).toBeInTheDocument()
    expect(screen.getByText('0.000 J/cm²')).toBeInTheDocument()
  })

  it('presents dose completion as a non-safety outcome with fractional duration support', () => {
    render(<DecisionCard decision={{
      ...decision,
      action: 'COMPLETE',
      confidence: 1,
      fired_rules: [{ id: 'TARGET_DOSE_DELIVERED', label: 'The prescribed target dose has been delivered.', severity: 'complete', observed: '4 J/cm2', threshold: '>= 4 J/cm2' }],
    }} />)
    expect(screen.getByRole('heading', { name: 'Session complete' })).toBeInTheDocument()
    expect(screen.getByText('Completes')).toBeInTheDocument()
  })
})
