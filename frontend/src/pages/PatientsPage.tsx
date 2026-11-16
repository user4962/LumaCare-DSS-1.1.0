import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronRight, Search } from 'lucide-react'
import { Drawer, EmptyState, LoadingState, SourceNotice } from '../components/ui'
import { demoPatients, demoProtocols } from '../data/demo'
import { useApiResource } from '../hooks/useApiResource'
import { mapPatients, mapProtocols } from '../lib/mappers'
import { formatDateTime } from '../lib/format'
import type { Patient, Protocol } from '../types'


const getAge = (date: string) => {
  const birth = new Date(date)
  const now = new Date()
  let age = now.getFullYear() - birth.getFullYear()
  if (now < new Date(now.getFullYear(), birth.getMonth(), birth.getDate())) age -= 1
  return age
}

export function PatientsPage() {
  const resource = useApiResource<Patient[]>('/patients', demoPatients, mapPatients)
  const protocolResource = useApiResource<Protocol[]>('/protocols', demoProtocols, mapProtocols)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<Patient | null>(null)
  const [searchParams] = useSearchParams()

  useEffect(() => {
    const requestedId = searchParams.get('record')
    const requested = requestedId ? resource.data.find((patient) => patient.id === requestedId) : undefined
    if (requested) setSelected(requested)
  }, [resource.data, searchParams])

  const filtered = useMemo(() => resource.data.filter((patient) => (
    `${patient.name} ${patient.mrn}`.toLowerCase().includes(query.toLowerCase())
  )), [query, resource.data])

  if (resource.loading || protocolResource.loading) return <LoadingState label="Loading patient registry" />

  return (
    <div className="page-stack">
      <SourceNotice source={resource.source === 'api' && protocolResource.source === 'api' ? 'api' : 'demo'} error={resource.error ?? protocolResource.error} onRetry={() => { resource.retry(); protocolResource.retry() }} />
      <section className="panel data-panel">
        <div className="data-toolbar">
          <div className="filter-search"><Search size={16} /><input aria-label="Search patients" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name or record number" /></div>
          <span className="record-count">{filtered.length} of {resource.data.length} records</span>
        </div>

        {filtered.length === 0 ? <EmptyState title="No matching patients" detail="Change the search term to restore records." /> : (
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>Patient</th><th>Record number</th><th>Date of birth</th><th>Sex</th><th>Prescription</th><th>Record updated</th><th><span className="sr-only">Open</span></th></tr></thead>
              <tbody>{filtered.map((patient) => (
                <tr key={patient.id} onClick={() => setSelected(patient)}>
                  <td><strong>{patient.name}</strong></td>
                  <td>{patient.mrn}</td>
                  <td>{new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(patient.date_of_birth))} <span className="muted">({getAge(patient.date_of_birth)} y)</span></td>
                  <td>{patient.sex}</td>
                  <td>{protocolResource.data.find((protocol) => protocol.patient_id === patient.id)?.name ?? <span className="muted">No linked prescription</span>}</td>
                  <td className="nowrap">{formatDateTime(patient.last_session_at)}</td>
                  <td><button className="row-action" aria-label={`Open ${patient.name} details`} onClick={(event) => { event.stopPropagation(); setSelected(patient) }}><ChevronRight size={18} /></button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </section>

      <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.name ?? ''} eyebrow={selected?.mrn}>
        {selected && <PatientDetails patient={selected} activeProtocol={protocolResource.data.find((protocol) => protocol.patient_id === selected.id)?.name ?? 'No linked prescription'} />}
      </Drawer>
    </div>
  )
}

function PatientDetails({ patient, activeProtocol }: { patient: Patient; activeProtocol: string }) {
  return <div className="detail-stack">
    <table className="kv-table kv-table--wide" aria-label="Patient record">
      <tbody>
        <tr><th scope="row">Record number</th><td>{patient.mrn}</td></tr>
        <tr><th scope="row">Date of birth</th><td>{new Intl.DateTimeFormat('en-GB', { day: '2-digit', month: 'long', year: 'numeric' }).format(new Date(patient.date_of_birth))} ({getAge(patient.date_of_birth)} years)</td></tr>
        <tr><th scope="row">Sex</th><td>{patient.sex}</td></tr>
        <tr><th scope="row">Linked prescription</th><td>{activeProtocol}</td></tr>
        <tr><th scope="row">Record updated</th><td>{formatDateTime(patient.last_session_at)}</td></tr>
      </tbody>
    </table>
    <p className="panel__note">Clinical eligibility data (phototype, contraindications, consent) are not stored in this research prototype. The decision engine receives only the limits held in the prescription.</p>
  </div>
}
