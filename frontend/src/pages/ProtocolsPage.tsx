import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { BookOpenCheck, Calculator, CheckCircle2, Clock3, FileCheck2, ShieldAlert, Waves } from 'lucide-react'
import { LoadingState, SourceNotice, StatusPill } from '../components/ui'
import { demoProtocols } from '../data/demo'
import { useApiResource } from '../hooks/useApiResource'
import { mapProtocols } from '../lib/mappers'
import { calculateDosePlan } from '../lib/dose'
import { formatDate } from '../lib/format'
import type { Protocol } from '../types'

export function ProtocolsPage() {
  const resource = useApiResource<Protocol[]>('/protocols', demoProtocols, mapProtocols)
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedId, setSelectedId] = useState('pro-301')
  const selected = resource.data.find((protocol) => protocol.id === selectedId) ?? resource.data[0] ?? demoProtocols[0]
  const [irradiance, setIrradiance] = useState(selected.irradiance_min_mw_cm2 + (selected.irradiance_max_mw_cm2 - selected.irradiance_min_mw_cm2) / 2)
  const plan = useMemo(() => calculateDosePlan(selected, irradiance), [irradiance, selected])

  useEffect(() => {
    const requestedId = searchParams.get('record')
    const next = (requestedId ? resource.data.find((protocol) => protocol.id === requestedId) : undefined)
      ?? resource.data.find((protocol) => protocol.id === selectedId)
      ?? resource.data[0]
    if (next && next.id !== selectedId) {
      setSelectedId(next.id)
      setIrradiance(Number(((next.irradiance_min_mw_cm2 + next.irradiance_max_mw_cm2) / 2).toFixed(1)))
    }
  }, [resource.data, searchParams, selectedId])

  const changeProtocol = (id: string) => {
    setSelectedId(id)
    if (searchParams.has('record')) setSearchParams({}, { replace: true })
    const next = resource.data.find((protocol) => protocol.id === id)
    if (next) setIrradiance(Number(((next.irradiance_min_mw_cm2 + next.irradiance_max_mw_cm2) / 2).toFixed(1)))
  }

  if (resource.loading) return <LoadingState label="Loading protocol library" />

  return <div className="page-stack">
    <SourceNotice source={resource.source} error={resource.error} onRetry={resource.retry} />
    <div className="protocol-layout">
      <section className="panel protocol-library">
        <div className="panel__header"><div><span className="section-label">Versioned library</span><h2>Prescriptions</h2></div><StatusPill tone="success">{resource.data.filter((item) => item.status === 'active').length} active</StatusPill></div>
        <div className="protocol-list">{resource.data.map((protocol) => <button key={protocol.id} className={selected.id === protocol.id ? 'protocol-list-item protocol-list-item--selected' : 'protocol-list-item'} onClick={() => changeProtocol(protocol.id)} aria-pressed={selected.id === protocol.id}>
          <span className="protocol-list-item__icon"><Waves size={19} /></span>
          <div><span className="protocol-list-item__code">{protocol.code} · version {protocol.version}</span><strong>{protocol.name}</strong><small>{protocol.indication}</small></div>
          <StatusPill tone={protocol.status === 'active' ? 'success' : 'neutral'}>{protocol.status}</StatusPill>
        </button>)}</div>
      </section>

      <section className="panel protocol-detail">
        <div className="protocol-detail__title"><div><span className="section-label">{selected.code} · version {selected.version}</span><h2>{selected.name}</h2><p>{selected.indication}</p></div><span className="protocol-seal"><FileCheck2 size={18} /><small>Record status</small><strong>{selected.status}</strong></span></div>
        <div className="protocol-envelope">
          <div><span>Wavelength</span><strong>{selected.wavelength_tolerance_nm ? `${selected.wavelength_nm} ± ${selected.wavelength_tolerance_nm}` : selected.wavelength_nm} nm</strong></div>
          <div><span>Target dose</span><strong>{selected.target_dose_j_cm2} J/cm²</strong></div>
          <div><span>Session dose ceiling</span><strong>{selected.max_session_dose_j_cm2} J/cm²</strong></div>
          <div><span>Irradiance</span><strong>{selected.irradiance_min_mw_cm2}–{selected.irradiance_max_mw_cm2} mW/cm²</strong></div>
          <div><span>Maximum duration</span><strong>{selected.duration_max_min} min</strong></div>
          <div><span>Thermal ceiling</span><strong>{selected.skin_temperature_max_c} °C</strong></div>
          <div><span>SpO₂ floor</span><strong>{selected.spo2_min_percent}%</strong></div>
        </div>
        <div className="evidence-note"><BookOpenCheck size={19} /><div><strong>Research record linkage</strong><span>{selected.evidence_label}</span><small>Updated {formatDate(selected.updated_at)} · version {selected.version}</small></div></div>
      </section>

      <section className="panel dose-calculator">
        <div className="panel__header"><div><span className="section-label">Protocol-bound estimate</span><h2>Dose calculator</h2></div><span className="calculator-icon"><Calculator size={20} /></span></div>
        <p className="panel-description">The calculation demonstrates rule execution using synthetic parameters. A clinician must authorize any treatment plan.</p>
        <div className="calculator-form">
          <label><span>Measured irradiance</span><div className="input-with-unit"><input aria-label="Measured irradiance" type="number" step="0.1" min="0" value={irradiance} onChange={(event) => setIrradiance(Number(event.target.value))} /><span>mW/cm²</span></div></label>
          <div className="calculator-range"><span>Allowed envelope</span><strong>{selected.irradiance_min_mw_cm2}–{selected.irradiance_max_mw_cm2} mW/cm²</strong></div>
        </div>
        <div className="calculation-formula" aria-label="Dose duration calculation"><span>{plan.adjustedDose.toFixed(3)} J/cm²</span><i>× 1000 ÷</i><span>{irradiance || 0} mW/cm²</span><i>=</i><strong>{Math.floor(plan.durationSeconds / 60)}:{String(Math.round(plan.durationSeconds % 60)).padStart(2, '0')}</strong></div>
        <div className={`calculation-result ${plan.eligible ? 'calculation-result--eligible' : 'calculation-result--blocked'}`}>
          {plan.eligible ? <CheckCircle2 size={22} /> : <ShieldAlert size={22} />}
          <div><span>{plan.eligible ? 'Estimate inside protocol envelope' : 'Estimate requires adjustment'}</span><strong>{plan.adjustedDose.toFixed(2)} J/cm² over {Math.ceil(plan.durationSeconds)} seconds</strong><small>Uses the stored research prescription target · maximum {selected.duration_max_min * 60} seconds</small></div>
        </div>
        {!plan.inIrradianceRange && <div className="calculator-warning"><ShieldAlert size={16} /> Irradiance is outside the configured protocol range.</div>}
        {!plan.withinDuration && <div className="calculator-warning"><Clock3 size={16} /> Estimated exposure exceeds the protocol duration ceiling.</div>}
      </section>
    </div>
  </div>
}
