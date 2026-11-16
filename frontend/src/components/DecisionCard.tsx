import { CheckCircle2, Flag, PauseCircle, SlidersHorizontal } from 'lucide-react'
import { formatSeconds } from '../lib/format'
import type { Decision, DecisionAction, FiredRule } from '../types'

const config: Record<DecisionAction, { label: string; caption: string; icon: typeof CheckCircle2 }> = {
  ALLOW: { label: 'Continue as prescribed', caption: 'Checked values are inside the prescription limits.', icon: CheckCircle2 },
  ADJUST: { label: 'Reduce exposure', caption: 'Setpoints were lowered by the rules listed below.', icon: SlidersHorizontal },
  COMPLETE: { label: 'Session complete', caption: 'The prescribed dose allowance has been delivered. This is not a safety event.', icon: Flag },
  HOLD: { label: 'Stop emission', caption: 'A safety interlock requires zero output until the operator reviews the session.', icon: PauseCircle },
}

// Engine provenance uses ASCII units; the console shows typographic units.
const displayUnits = (value: string) => value
  .replace(/mW\/cm2\b/g, 'mW/cm²')
  .replace(/J\/cm2\b/g, 'J/cm²')
  .replace(/(\d) C\b/g, '$1 °C')
  .replace(/>=/g, '≥')
  .replace(/<=/g, '≤')

const effectLabel: Record<FiredRule['severity'], string> = {
  pass: 'Passed',
  info: 'Note',
  warning: 'Reduces',
  complete: 'Completes',
  block: 'Stops',
}

export function DecisionCard({ decision }: { decision: Decision }) {
  const state = config[decision.action]
  const Icon = state.icon
  const certainty = Math.round(decision.confidence * 100)
  const normalise = (value: string) => value.replace(/\s+/g, ' ').trim()
  const ruleText = normalise(decision.fired_rules.map((rule) => rule.label).join(' '))
  const showExplanation = Boolean(decision.explanation) && normalise(decision.explanation) !== ruleText
  const hasRecommendedOutput = decision.recommended_irradiance_mw_cm2 !== undefined || decision.recommended_duration_seconds !== undefined || decision.estimated_additional_dose_j_cm2 !== undefined
  return (
    <section className={`decision-card decision-card--${decision.action.toLowerCase()}`} aria-label={`Decision: ${state.label}`}>
      <header className="decision-card__header">
        <span>Decision support</span>
        <span className={`action-chip action-chip--${decision.action.toLowerCase()}`}>{decision.action}</span>
      </header>
      <div className="decision-card__result">
        <span className="decision-card__icon"><Icon size={22} aria-hidden="true" /></span>
        <div><h2>{state.label}</h2><p>{state.caption}</p></div>
      </div>

      {hasRecommendedOutput && <table className="kv-table" aria-label="Recommended setpoints">
        <caption>Recommended setpoints</caption>
        <tbody>
          {decision.recommended_irradiance_mw_cm2 !== undefined && <tr><th scope="row">Irradiance</th><td>{decision.recommended_irradiance_mw_cm2.toFixed(2)} mW/cm²</td></tr>}
          {decision.recommended_duration_seconds !== undefined && <tr><th scope="row">Duration</th><td>{formatSeconds(decision.recommended_duration_seconds)}</td></tr>}
          {decision.estimated_additional_dose_j_cm2 !== undefined && <tr><th scope="row">Additional dose</th><td>{decision.estimated_additional_dose_j_cm2.toFixed(3)} J/cm²</td></tr>}
        </tbody>
      </table>}

      <section className="rule-list" aria-label="Fired rules">
        <h3>Fired rules</h3>
        {decision.fired_rules.length === 0 ? <p className="rule-list__empty">No rule fired.</p> : <ul>
          {decision.fired_rules.map((rule) => (
            <li key={rule.id} className={`rule-item rule-item--${rule.severity}`}>
              <div className="rule-item__head"><code>{rule.id}</code><span className={`effect effect--${rule.severity}`}>{effectLabel[rule.severity]}</span></div>
              {rule.label !== rule.id && <p>{rule.label}</p>}
              <dl>
                <div><dt>Observed</dt><dd>{displayUnits(rule.observed)}</dd></div>
                <div><dt>Limit</dt><dd>{displayUnits(rule.threshold)}</dd></div>
              </dl>
            </li>
          ))}
        </ul>}
      </section>

      {showExplanation && <p className="decision-card__explanation"><span>Basis:</span> <span>{decision.explanation}</span></p>}
      <footer>
        <span>{decision.model_version}</span>
        <span title="Deterministic rule activation certainty; not a clinical probability">Rule certainty {certainty}%</span>
        <span>{new Date(decision.evaluated_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
      </footer>
    </section>
  )
}
