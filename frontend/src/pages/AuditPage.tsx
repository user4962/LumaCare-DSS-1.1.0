import { useMemo, useState } from 'react'
import { CheckCircle2, ClipboardCheck, Code2, Database, Download, ExternalLink, FileJson, Link2, Search, ShieldCheck } from 'lucide-react'
import { Button, EmptyState, LoadingState, SourceNotice, StatusPill } from '../components/ui'
import { buildDemoFhirBundle, demoAudit } from '../data/demo'
import { useApiResource } from '../hooks/useApiResource'
import { api, downloadJson } from '../lib/api'
import { mapAudit } from '../lib/mappers'
import { formatDateTime } from '../lib/format'
import type { AuditEvent } from '../types'

const outcomeTone = { recorded: 'success' } as const

export function AuditPage() {
  const resource = useApiResource<AuditEvent[]>('/audit', demoAudit, mapAudit)
  const [query, setQuery] = useState('')
  const [exporting, setExporting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const filtered = useMemo(() => resource.data.filter((event) => `${event.actor} ${event.action} ${event.resource_type} ${event.resource_id}`.toLowerCase().includes(query.toLowerCase())), [query, resource.data])

  const exportFhir = async () => {
    setExporting(true)
    setMessage(null)
    try {
      const bundle = resource.source === 'api' ? await api.get<unknown>('/interop/fhir/export') : buildDemoFhirBundle()
      downloadJson(`lumacare-fhir-bundle-${new Date().toISOString().slice(0, 10)}.json`, bundle)
      setMessage(resource.source === 'api' ? 'FHIR-aligned bundle exported from the connected service.' : 'Synthetic FHIR R4 research bundle exported.')
    } catch (reason) { setMessage(`Export failed: ${(reason as Error).message}`) }
    finally { setExporting(false) }
  }

  const exportAudit = () => {
    downloadJson(`lumacare-audit-${new Date().toISOString().slice(0, 10)}.json`, filtered)
    setMessage(`${filtered.length} visible audit events exported.`)
  }

  if (resource.loading) return <LoadingState label="Loading audit and interoperability workspace" />
  return <div className="page-stack">
    <SourceNotice source={resource.source} error={resource.error} onRetry={resource.retry} />
    {message && <div className="toast-inline" role="status"><CheckCircle2 size={17} />{message}</div>}
    <section className="interop-grid">
      <article className="interop-card interop-card--primary">
        <div className="interop-card__icon"><FileJson size={23} /></div>
        <div><span className="section-label">FHIR R4-aligned JSON</span><h2>Research data bundle</h2><p>Exports Patient, Device, ServiceRequest, Procedure, Observation, and DetectedIssue resources.</p></div>
        <Button icon={<Download size={16} />} disabled={exporting} onClick={() => void exportFhir()}>{exporting ? 'Preparing…' : 'Export FHIR bundle'}</Button>
      </article>
      <article className="interop-card"><div className="interop-card__icon interop-card__icon--blue"><Link2 size={22} /></div><div><span className="section-label">Exchange endpoint</span><h2>HL7 FHIR interface</h2><p><code>/api/v1/interop/fhir/export</code></p><div className="interop-status"><span className="system-state__dot" />Endpoint configuration available</div></div></article>
      <article className="interop-card"><div className="interop-card__icon interop-card__icon--amber"><Database size={22} /></div><div><span className="section-label">Persisted trace</span><h2>Append-style event log</h2><p>State transitions and operator actions are stored with actor, entity, timestamp, and structured details.</p><StatusPill tone="info">{resource.data.length} events loaded</StatusPill></div></article>
    </section>

    <section className="panel mapping-panel">
      <div className="panel__header"><div><span className="section-label">Semantic mapping</span><h2>Clinical resource coverage</h2></div><a href="https://hl7.org/fhir/R4/" target="_blank" rel="noreferrer" className="text-link">FHIR R4 specification <ExternalLink size={14} /></a></div>
      <div className="mapping-flow" aria-label="Internal domain to FHIR mapping">
        <div className="mapping-pair"><div><strong>Patient record</strong><span>Identifiers, name, sex, birth date</span></div><Code2 size={17} /><div><strong>Patient</strong><span>FHIR resource</span></div></div>
        <div className="mapping-pair"><div><strong>Connected device</strong><span>Serial, model, firmware, assignment</span></div><Code2 size={17} /><div><strong>Device</strong><span>FHIR resource</span></div></div>
        <div className="mapping-pair"><div><strong>Research prescription</strong><span>Protocol targets and validity</span></div><Code2 size={17} /><div><strong>ServiceRequest</strong><span>FHIR resource</span></div></div>
        <div className="mapping-pair"><div><strong>Session + telemetry</strong><span>Delivery state and sensor samples</span></div><Code2 size={17} /><div><strong>Procedure + Observation</strong><span>FHIR resources</span></div></div>
        <div className="mapping-pair"><div><strong>Engine decision</strong><span>Action, risk, explanation</span></div><Code2 size={17} /><div><strong>DetectedIssue</strong><span>FHIR resource</span></div></div>
      </div>
      <div className="research-disclaimer"><ShieldCheck size={17} /><span>This mapping supports research interoperability testing. Conformance certification and production clinical validation are outside the prototype scope.</span></div>
    </section>

    <section className="panel data-panel">
      <div className="panel__header audit-header"><div><span className="section-label">Persisted event trace</span><h2>Audit events</h2></div><Button variant="secondary" icon={<Download size={15} />} onClick={exportAudit}>Export visible events</Button></div>
      <div className="data-toolbar">
        <div className="filter-search"><Search size={17} /><input aria-label="Search audit events" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search actor, action, or resource" /></div>
        <span className="record-count">{filtered.length} visible events</span>
      </div>
      {filtered.length === 0 ? <EmptyState title="No matching audit events" detail="Change the event search term to restore records." /> : <div className="table-scroll"><table className="data-table audit-table"><thead><tr><th>Timestamp</th><th>Actor</th><th>Event</th><th>Entity</th><th>State</th><th>Structured details</th><th>Event ID</th></tr></thead><tbody>{filtered.map((event) => <tr key={event.id}>
        <td>{formatDateTime(event.timestamp)}</td><td><div className="table-person"><strong>{event.actor}</strong><span>{event.actor_role}</span></div></td><td><code>{event.action}</code></td><td><div className="table-person"><strong>{event.resource_type}</strong><span>{event.resource_id}</span></div></td><td><StatusPill tone={outcomeTone[event.outcome]}><ClipboardCheck size={13} />{event.outcome}</StatusPill></td><td><code>{Object.keys(event.details).length ? JSON.stringify(event.details) : '{}'}</code></td><td><span className="event-id">{event.id}</span></td>
      </tr>)}</tbody></table></div>}
    </section>
  </div>
}
