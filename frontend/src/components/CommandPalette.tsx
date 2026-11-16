import { ArrowRight, Cpu, Database, FileClock, LayoutDashboard, Radio, Search, ShieldAlert, Users, Waves, X } from 'lucide-react'
import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { demoDevices, demoPatients, demoProtocols } from '../data/demo'
import { useApiResource } from '../hooks/useApiResource'
import { mapDevices, mapPatients, mapProtocols } from '../lib/mappers'
import type { Device, Patient, Protocol } from '../types'
import { IconButton } from './ui'

const routeResults = [
  { id: 'overview', title: 'Overview', subtitle: 'Operational dashboard', to: '/', icon: LayoutDashboard },
  { id: 'live', title: 'Live Therapy', subtitle: 'Supervised telemetry session', to: '/live-therapy', icon: Radio },
  { id: 'patients', title: 'Patients', subtitle: 'Research programme records', to: '/patients', icon: Users },
  { id: 'devices', title: 'Devices', subtitle: 'Connected research fleet', to: '/devices', icon: Cpu },
  { id: 'protocols', title: 'Protocols', subtitle: 'Research prescriptions', to: '/protocols', icon: Waves },
  { id: 'alerts', title: 'Safety Alerts', subtitle: 'Prioritized event queue', to: '/alerts', icon: ShieldAlert },
  { id: 'audit', title: 'Audit & Interoperability', subtitle: 'Persisted events and FHIR export', to: '/audit', icon: FileClock },
]

export function CommandPalette({ open, query, onQueryChange, onClose }: { open: boolean; query: string; onQueryChange: (value: string) => void; onClose: () => void }) {
  const navigate = useNavigate()
  const patients = useApiResource<Patient[]>('/patients', demoPatients, mapPatients)
  const devices = useApiResource<Device[]>('/devices', demoDevices, mapDevices)
  const protocols = useApiResource<Protocol[]>('/protocols', demoProtocols, mapProtocols)

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase()
    const routes = routeResults.filter((item) => !needle || `${item.title} ${item.subtitle}`.toLowerCase().includes(needle))
    const patientResults = patients.data.filter((item) => needle && `${item.name} ${item.mrn}`.toLowerCase().includes(needle)).map((item) => ({ id: `patient-${item.id}`, title: item.name, subtitle: `Patient · ${item.mrn}`, to: `/patients?record=${encodeURIComponent(item.id)}`, icon: Users }))
    const deviceResults = devices.data.filter((item) => needle && `${item.label} ${item.serial_number} ${item.model}`.toLowerCase().includes(needle)).map((item) => ({ id: `device-${item.id}`, title: item.label, subtitle: `Device · ${item.serial_number}`, to: `/devices?record=${encodeURIComponent(item.id)}`, icon: Cpu }))
    const protocolResults = protocols.data.filter((item) => needle && `${item.name} ${item.code}`.toLowerCase().includes(needle)).map((item) => ({ id: `protocol-${item.id}`, title: item.name, subtitle: `Protocol · ${item.code}`, to: `/protocols?record=${encodeURIComponent(item.id)}`, icon: Waves }))
    return [...routes, ...patientResults, ...deviceResults, ...protocolResults].slice(0, 10)
  }, [devices.data, patients.data, protocols.data, query])

  if (!open) return null
  const fallback = patients.source === 'demo' || devices.source === 'demo' || protocols.source === 'demo'

  const choose = (to: string) => {
    navigate(to)
    onClose()
  }

  return <div className="command-layer" role="presentation">
    <button className="command-backdrop" aria-label="Close global search" onClick={onClose} />
    <section className="command-palette" role="dialog" aria-modal="true" aria-labelledby="command-title">
      <div className="command-search">
        <Search size={19} aria-hidden="true" />
        <input autoFocus value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Search routes, patients, devices, or protocols" aria-label="Global search" />
        <IconButton label="Close global search" onClick={onClose}><X size={18} /></IconButton>
      </div>
      <div className="command-meta"><strong id="command-title">Global research workspace search</strong>{fallback && <span><Database size={13} />Synthetic fallback records included</span>}</div>
      <div className="command-results" aria-label="Search results">
        {results.length ? results.map(({ id, title, subtitle, to, icon: Icon }) => <button key={id} onClick={() => choose(to)}>
          <span className="command-result__icon"><Icon size={17} /></span><span><strong>{title}</strong><small>{subtitle}</small></span><ArrowRight size={15} />
        </button>) : <div className="command-empty"><Search size={22} /><strong>No matching workspace records</strong><span>Try a name, MRN, serial number, protocol code, or route.</span></div>}
      </div>
      <footer><span><kbd>Tab</kbd> navigate</span><span><kbd>Enter</kbd> open</span><span><kbd>Esc</kbd> close</span></footer>
    </section>
  </div>
}
