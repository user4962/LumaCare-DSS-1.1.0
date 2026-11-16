import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Battery, CheckCircle2, ChevronRight, Clock3, Cpu, Radio, Search, Settings2, Signal } from 'lucide-react'
import { Drawer, EmptyState, LoadingState, SourceNotice, StatusPill } from '../components/ui'
import { demoDevices, demoPatients } from '../data/demo'
import { useApiResource } from '../hooks/useApiResource'
import { mapDevices, mapPatients } from '../lib/mappers'
import { formatRelative } from '../lib/format'
import type { Device, Patient } from '../types'

const statusTone = { online: 'success', offline: 'danger', maintenance: 'warning' } as const

export function DevicesPage() {
  const resource = useApiResource<Device[]>('/devices', demoDevices, mapDevices)
  const patientResource = useApiResource<Patient[]>('/patients', demoPatients, mapPatients)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [selected, setSelected] = useState<Device | null>(null)
  const [searchParams] = useSearchParams()

  useEffect(() => {
    const requestedId = searchParams.get('record')
    const requested = requestedId ? resource.data.find((device) => device.id === requestedId) : undefined
    if (requested) setSelected(requested)
  }, [resource.data, searchParams])
  const filtered = useMemo(() => resource.data.filter((device) => `${device.label} ${device.model} ${device.serial_number}`.toLowerCase().includes(query.toLowerCase()) && (status === 'all' || device.status === status)), [query, resource.data, status])

  if (resource.loading || patientResource.loading) return <LoadingState label="Loading connected device fleet" />
  const counts = resource.data.reduce((acc, item) => ({ ...acc, [item.status]: acc[item.status] + 1 }), { online: 0, offline: 0, maintenance: 0 })

  return <div className="page-stack">
    <SourceNotice source={resource.source === 'api' && patientResource.source === 'api' ? 'api' : 'demo'} error={resource.error ?? patientResource.error} onRetry={() => { resource.retry(); patientResource.retry() }} />
    <section className="compact-metrics" aria-label="Device fleet status">
      <div><span className="compact-metrics__icon compact-metrics__icon--ok"><Radio size={20} /></span><span className="compact-metrics__text"><strong>{counts.online}</strong><small>Online</small></span></div>
      <div><span className="compact-metrics__icon compact-metrics__icon--warning"><Settings2 size={20} /></span><span className="compact-metrics__text"><strong>{counts.maintenance}</strong><small>Maintenance</small></span></div>
      <div><span className="compact-metrics__icon compact-metrics__icon--neutral"><Cpu size={20} /></span><span className="compact-metrics__text"><strong>{counts.offline}</strong><small>Offline</small></span></div>
      <div><span className="compact-metrics__icon"><CheckCircle2 size={20} /></span><span className="compact-metrics__text"><strong>{resource.data.filter((device) => new Date(device.calibration_due_at) > new Date()).length}</strong><small>Calibration valid</small></span></div>
    </section>
    <section className="panel data-panel">
      <div className="data-toolbar">
        <div className="filter-search"><Search size={17} /><input aria-label="Search devices" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search label, model, or serial" /></div>
        <div className="segmented-filter" aria-label="Filter by device status">{['all', 'online', 'maintenance', 'offline'].map((item) => <button key={item} className={status === item ? 'active' : ''} onClick={() => setStatus(item)} aria-pressed={status === item}>{item}</button>)}</div>
        <span className="record-count">{filtered.length} devices</span>
      </div>
      {filtered.length === 0 ? <EmptyState title="No matching devices" detail="Change the search term or connectivity filter." /> : <div className="table-scroll"><table className="data-table"><thead><tr><th>Serial number</th><th>Model</th><th>Status</th><th>Assigned patient</th><th className="num">Wavelength, nm</th><th>Calibration due</th><th>Last seen</th><th><span className="sr-only">Open</span></th></tr></thead>
        <tbody>{filtered.map((device) => { const patient = patientResource.data.find((item) => item.id === device.assigned_patient_id); return <tr key={device.id} onClick={() => setSelected(device)}>
          <td><strong>{device.serial_number}</strong></td>
          <td>{device.label}</td>
          <td><StatusPill tone={statusTone[device.status]}><span className={`status-dot status-dot--${device.status}`} />{device.status}</StatusPill></td>
          <td>{patient ? <div className="table-person"><strong>{patient.name}</strong><span>{patient.mrn}</span></div> : <span className="muted">Unassigned</span>}</td>
          <td className="num">{device.wavelength_nm ?? '—'}</td>
          <td>{new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(device.calibration_due_at))}</td>
          <td>{formatRelative(device.last_seen_at)}</td>
          <td><button className="row-action" aria-label={`Open ${device.label} details`} onClick={(event) => { event.stopPropagation(); setSelected(device) }}><ChevronRight size={18} /></button></td>
        </tr>})}</tbody>
      </table></div>}
    </section>
    <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.label ?? ''} eyebrow={selected?.serial_number}>
      {selected && <DeviceDetails device={selected} patient={patientResource.data.find((item) => item.id === selected.assigned_patient_id)} />}
    </Drawer>
  </div>
}

function DeviceDetails({ device, patient }: { device: Device; patient?: Patient }) {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const daysUntilCalibration = Math.ceil((new Date(device.calibration_due_at).getTime() - today.getTime()) / 86_400_000)
  return <div className="detail-stack">
    <div className="detail-hero"><span className="detail-avatar"><Cpu size={27} /></span><div><strong>{device.model}</strong><span>Firmware {device.firmware_version}{device.operating_hours === null ? '' : ` · ${device.operating_hours.toLocaleString()} operating hours`}</span></div><StatusPill tone={statusTone[device.status]}>{device.status}</StatusPill></div>
    <section className="detail-section"><div className="section-label">Connectivity & power</div>
      <div className="device-gauges"><div><Signal size={20} /><strong>{device.signal_rssi === null ? 'Not exposed' : `${device.signal_rssi} dBm`}</strong><span>Signal strength</span>{device.signal_rssi !== null && <div className="mini-progress"><span style={{ width: `${Math.max(10, 100 + device.signal_rssi)}%` }} /></div>}</div><div><Battery size={20} /><strong>{device.battery_percent === null ? 'Not exposed' : `${device.battery_percent}%`}</strong><span>Battery level</span>{device.battery_percent !== null && <div className="mini-progress"><span style={{ width: `${device.battery_percent}%` }} /></div>}</div></div>
    </section>
    <section className="detail-section"><div className="section-label">Optical performance</div>
      <div className="detail-metrics"><div><strong>{device.irradiance_mw_cm2 === null ? 'Not exposed' : `${device.irradiance_mw_cm2.toFixed(1)} mW/cm²`}</strong><span>Last irradiance</span></div><div><strong>{daysUntilCalibration} days</strong><span>Calibration window</span></div><div><strong>{device.firmware_version}</strong><span>Reported firmware</span></div></div>
      <div className={daysUntilCalibration <= 7 ? 'clinical-callout clinical-callout--warning' : 'clinical-callout clinical-callout--success'}><Clock3 size={18} /><div><strong>Calibration due {device.calibration_due_at}</strong><span>{daysUntilCalibration <= 7 ? 'Schedule service before the next supervised use.' : 'Current calibration remains inside the configured interval.'}</span></div></div>
    </section>
    <section className="detail-section"><div className="section-label">Assignment</div>{patient ? <div className="protocol-summary"><span className="avatar avatar--small">{patient.name.split(' ').map((part) => part[0]).join('')}</span><div><strong>{patient.name}</strong><span>{patient.mrn} · {patient.active_protocol}</span></div></div> : <div className="clinical-callout"><Cpu size={18} /><div><strong>No active patient assignment</strong><span>The device is available for a protocol-compatible assignment.</span></div></div>}</section>
  </div>
}
