import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, AlertTriangle, Check, CheckCircle2, Clock3, Info, Search, ShieldAlert } from 'lucide-react'
import { Button, EmptyState, LoadingState, SourceNotice, StatusPill } from '../components/ui'
import { demoAlerts } from '../data/demo'
import { useApiResource } from '../hooks/useApiResource'
import { api } from '../lib/api'
import { mapAlert, mapAlerts } from '../lib/mappers'
import { formatDateTime } from '../lib/format'
import type { AlertItem } from '../types'

const severityTone = { critical: 'danger', high: 'danger', warning: 'warning', info: 'info' } as const

export function AlertsPage() {
  const resource = useApiResource<AlertItem[]>('/alerts', demoAlerts, mapAlerts)
  const [alerts, setAlerts] = useState<AlertItem[]>(demoAlerts)
  const [filter, setFilter] = useState<'open' | 'all' | 'acknowledged' | 'resolved'>('open')
  const [query, setQuery] = useState('')
  const [busyId, setBusyId] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  useEffect(() => setAlerts(resource.data), [resource.data])
  const filtered = useMemo(() => alerts.filter((alert) => (filter === 'all' || alert.status === filter) && `${alert.title} ${alert.code} ${alert.patient_name ?? ''}`.toLowerCase().includes(query.toLowerCase())), [alerts, filter, query])

  const acknowledge = async (alert: AlertItem) => {
    setBusyId(alert.id)
    setActionMessage(null)
    try {
      const acknowledged = resource.source === 'api'
        ? mapAlert(await api.post<unknown>(`/alerts/${alert.id}/acknowledge`))
        : { ...alert, status: 'acknowledged' as const, acknowledged_at: new Date().toISOString(), acknowledged_by: 'research-demo-user' }
      setAlerts((current) => current.map((item) => item.id === alert.id ? acknowledged : item))
      setActionMessage(`${alert.code} acknowledged and recorded in the audit trail.`)
    } catch (reason) {
      setActionMessage(`Acknowledgement failed: ${(reason as Error).message}`)
    } finally { setBusyId(null) }
  }

  if (resource.loading) return <LoadingState label="Loading safety alerts" />
  const critical = alerts.filter((item) => item.status === 'open' && (item.severity === 'critical' || item.severity === 'high')).length
  const warning = alerts.filter((item) => item.status === 'open' && item.severity === 'warning').length

  return <div className="page-stack">
    <SourceNotice source={resource.source} error={resource.error} onRetry={resource.retry} />
    <section className="alert-summary" aria-label="Alert queue summary">
      <div><span className="alert-summary__icon alert-summary__icon--danger"><ShieldAlert size={20} /></span><span className="alert-summary__text"><strong>{critical}</strong><small>Critical or high, open</small></span></div>
      <div><span className="alert-summary__icon alert-summary__icon--warning"><AlertTriangle size={20} /></span><span className="alert-summary__text"><strong>{warning}</strong><small>Warnings, open</small></span></div>
      <div><span className="alert-summary__icon"><CheckCircle2 size={20} /></span><span className="alert-summary__text"><strong>{alerts.filter((item) => item.status === 'acknowledged').length}</strong><small>Acknowledged</small></span></div>
      <div><span className="alert-summary__icon alert-summary__icon--ok"><Check size={20} /></span><span className="alert-summary__text"><strong>{alerts.filter((item) => item.status === 'resolved').length}</strong><small>Resolved</small></span></div>
    </section>
    {actionMessage && <div className="toast-inline" role="status"><CheckCircle2 size={17} />{actionMessage}</div>}
    <section className="panel alerts-panel">
      <div className="data-toolbar">
        <div className="filter-search"><Search size={17} /><input aria-label="Search safety alerts" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search alert code, patient, or event" /></div>
        <div className="segmented-filter" aria-label="Filter alert status">{(['open', 'all', 'acknowledged', 'resolved'] as const).map((item) => <button key={item} className={filter === item ? 'active' : ''} onClick={() => setFilter(item)} aria-pressed={filter === item}>{item}</button>)}</div>
      </div>
      {filtered.length === 0 ? <EmptyState title="No alerts in this view" detail="The selected status and search criteria returned no safety events." /> : <div className="alert-list">{filtered.map((alert) => <article className={`alert-card alert-card--${alert.severity}`} key={alert.id}>
        <div className="alert-card__severity">{alert.severity === 'critical' || alert.severity === 'high' ? <AlertCircle size={21} /> : alert.severity === 'warning' ? <AlertTriangle size={21} /> : <Info size={21} />}</div>
        <div className="alert-card__body">
          <div className="alert-card__heading"><span><StatusPill tone={severityTone[alert.severity]}>{alert.severity}</StatusPill><code>{alert.code}</code></span><time><Clock3 size={14} />{formatDateTime(alert.created_at)}</time></div>
          <h2>{alert.title}</h2><p>{alert.description}</p>
          <div className="alert-card__context">{alert.patient_name && <span><small>Patient</small><strong>{alert.patient_name}</strong></span>}{alert.device_id && <span><small>Device</small><strong>{alert.device_id}</strong></span>}<span><small>State</small><strong>{alert.status}</strong></span></div>
          {alert.status === 'acknowledged' && <div className="acknowledged-by"><CheckCircle2 size={15} />Acknowledged by {alert.acknowledged_by} · {alert.acknowledged_at && formatDateTime(alert.acknowledged_at)}</div>}
        </div>
        <div className="alert-card__action">{alert.status === 'open' ? <Button variant={alert.severity === 'critical' ? 'primary' : 'secondary'} disabled={busyId === alert.id} onClick={() => void acknowledge(alert)}>{busyId === alert.id ? 'Recording…' : 'Acknowledge'}</Button> : <StatusPill tone={alert.status === 'resolved' ? 'success' : 'neutral'}>{alert.status}</StatusPill>}</div>
      </article>)}</div>}
    </section>
  </div>
}
