import { Link } from 'react-router-dom'
import { demoDevices, demoOverview, demoPatients, demoProtocols } from '../data/demo'
import { useApiResource } from '../hooks/useApiResource'
import { mapDashboard, mapDevices, mapPatients, mapProtocols } from '../lib/mappers'
import { formatDate, formatDateTime, formatRelative } from '../lib/format'
import type { Device, OverviewData, Patient, Protocol } from '../types'
import { EmptyState, LoadingState, SourceNotice, StatusPill } from '../components/ui'

const actionTone = { ALLOW: 'success', ADJUST: 'warning', COMPLETE: 'info', HOLD: 'danger' } as const
const severityTone = { critical: 'danger', high: 'danger', warning: 'warning', info: 'info' } as const
const connectivityTone = { online: 'success', offline: 'neutral', maintenance: 'warning' } as const

export function OverviewPage() {
  const resource = useApiResource<OverviewData>('/overview', demoOverview, mapDashboard)
  const patients = useApiResource<Patient[]>('/patients', demoPatients, mapPatients)
  const devices = useApiResource<Device[]>('/devices', demoDevices, mapDevices)
  const protocols = useApiResource<Protocol[]>('/protocols', demoProtocols, mapProtocols)
  if (resource.loading || patients.loading || devices.loading || protocols.loading) return <LoadingState label="Loading dashboard" />

  const { data } = resource
  const patientName = (id?: string, fallback = '') => patients.data.find((item) => item.id === id)?.name ?? fallback
  const prescriptionName = (id?: string, fallback = '') => protocols.data.find((item) => item.id === id)?.name ?? fallback
  const openAlerts = data.recent_alerts.filter((alert) => alert.status === 'open')
  const sourceOk = resource.source === 'api' && patients.source === 'api' && devices.source === 'api' && protocols.source === 'api'

  return (
    <div className="page-stack">
      <SourceNotice source={sourceOk ? 'api' : 'demo'} error={resource.error} onRetry={resource.retry} />

      <section className="kpi-row" aria-label="Summary counts">
        <div className="kpi"><span>Running sessions</span><strong>{data.active_sessions}</strong><small>{data.sessions_today} session records in total</small></div>
        <div className="kpi"><span>Open safety alerts</span><strong className={data.open_alerts ? 'kpi__value--alert' : undefined}>{data.open_alerts}</strong><small>{data.critical_alerts} critical among recent alerts</small></div>
        <div className="kpi"><span>Patients</span><strong>{data.patients_in_program}</strong><small>research records</small></div>
        <div className="kpi"><span>Devices</span><strong>{data.total_devices}</strong><small>{devices.data.filter((item) => item.status === 'online').length} online</small></div>
      </section>

      <div className="overview-grid">
        <section className="panel">
          <div className="panel__header"><h2>Running sessions</h2><Link to="/live-therapy" className="text-link">Open live session</Link></div>
          {data.active_session_summaries.length ? <div className="table-scroll"><table className="data-table">
            <thead><tr><th>Patient</th><th>Prescription</th><th>Started</th><th className="num">Delivered dose, J/cm²</th><th>Progress</th><th>Last decision</th></tr></thead>
            <tbody>{data.active_session_summaries.map((session) => <tr key={session.id}>
              <td className="nowrap"><strong>{patientName(session.patient_id, session.patient_label)}</strong></td>
              <td>{prescriptionName(session.prescription_id, session.protocol_label)}</td>
              <td className="nowrap">{session.started_at ? formatDateTime(session.started_at) : '—'}</td>
              <td className="num">{session.delivered_dose_j_cm2.toFixed(3)}</td>
              <td><div className="progress-cell"><div className="progress-bar"><span style={{ width: `${session.progress_percent}%` }} /></div><small>{session.progress_percent.toFixed(0)} %</small></div></td>
              <td><StatusPill tone={actionTone[session.decision]}>{session.decision}</StatusPill></td>
            </tr>)}</tbody>
          </table></div> : <EmptyState title="No session is running" detail="Start a supervised session from the Live session page." />}
        </section>

        <section className="panel">
          <div className="panel__header"><h2>Open safety alerts</h2><Link to="/alerts" className="text-link">All alerts</Link></div>
          {openAlerts.length ? <div className="table-scroll"><table className="data-table">
            <thead><tr><th>Raised</th><th>Code</th><th>Patient</th><th>Severity</th></tr></thead>
            <tbody>{openAlerts.slice(0, 6).map((alert) => <tr key={alert.id}>
              <td className="nowrap">{formatDateTime(alert.created_at)}</td>
              <td><code>{alert.code}</code></td>
              <td className="nowrap">{patientName(alert.patient_id, alert.patient_name ?? '—')}</td>
              <td><StatusPill tone={severityTone[alert.severity]}>{alert.severity}</StatusPill></td>
            </tr>)}</tbody>
          </table></div> : <EmptyState title="No open alerts" detail="Alerts raised by safety interlocks appear here until acknowledged." />}
        </section>
      </div>

      <section className="panel">
        <div className="panel__header"><h2>Devices</h2><Link to="/devices" className="text-link">Device register</Link></div>
        <div className="table-scroll"><table className="data-table">
          <thead><tr><th>Serial number</th><th>Model</th><th>Assigned patient</th><th className="num">Wavelength, nm</th><th>Connectivity</th><th>Last seen</th><th>Calibration due</th></tr></thead>
          <tbody>{devices.data.map((device) => <tr key={device.id}>
            <td><strong>{device.serial_number}</strong></td>
            <td>{device.label}</td>
            <td>{patientName(device.assigned_patient_id, '—')}</td>
            <td className="num">{device.wavelength_nm ?? '—'}</td>
            <td><StatusPill tone={connectivityTone[device.status]}>{device.status}</StatusPill></td>
            <td>{formatRelative(device.last_seen_at)}</td>
            <td className="nowrap">{formatDate(device.calibration_due_at)}</td>
          </tr>)}</tbody>
        </table></div>
      </section>
    </div>
  )
}
