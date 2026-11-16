import { useEffect, useState } from 'react'
import { Radio, RotateCcw, ShieldAlert, Square } from 'lucide-react'
import { DecisionCard } from '../components/DecisionCard'
import { TelemetryChart } from '../components/TelemetryChart'
import { Button, LoadingState, SourceNotice, StatusPill } from '../components/ui'
import { demoDevices, demoPatients, demoProtocols } from '../data/demo'
import { useApiResource } from '../hooks/useApiResource'
import { useLiveSession } from '../hooks/useLiveSession'
import { mapDevices, mapPatients, mapProtocols } from '../lib/mappers'
import type { Device, Patient, Protocol, SessionSnapshot } from '../types'

const scenarioOptions = [
  { id: 'normal' as const, label: 'Nominal', description: 'Values stay inside the prescription.' },
  { id: 'heat' as const, label: 'Thermal rise', description: 'Skin temperature climbs towards the limit.' },
  { id: 'spo2' as const, label: 'SpO₂ decrease', description: 'Saturation falls below the minimum.' },
  { id: 'contact' as const, label: 'Contact loss', description: 'Applicator contact sensor reports false.' },
  { id: 'irradiance' as const, label: 'Irradiance spike', description: 'Measured output exceeds the envelope.' },
]

const statusLabel: Record<SessionSnapshot['status'], string> = {
  idle: 'No session',
  active: 'Running',
  paused: 'Stopped by interlock',
  completed: 'Completed',
  stopped: 'Stopped by operator',
}

const connectionTone = { live: 'success', demo: 'warning', connecting: 'info', disconnected: 'neutral' } as const
const connectionLabel = { live: 'Telemetry stream connected', demo: 'Synthetic fallback stream', connecting: 'Connecting stream', disconnected: 'Stream closed' } as const

type VitalStatus = 'normal' | 'warning' | 'danger' | 'complete'

export function LiveTherapyPage() {
  const live = useLiveSession()
  const patients = useApiResource<Patient[]>('/patients', demoPatients, mapPatients)
  const devices = useApiResource<Device[]>('/devices', demoDevices, mapDevices)
  const protocols = useApiResource<Protocol[]>('/protocols?active_only=true', demoProtocols, mapProtocols)
  const [patientId, setPatientId] = useState('pat-1001')
  const [deviceId, setDeviceId] = useState('dev-201')
  const [protocolId, setProtocolId] = useState('pro-301')
  const [showStopConfirm, setShowStopConfirm] = useState(false)
  const eligibleProtocols = protocols.data.filter((item) => item.status === 'active' && (!item.patient_id || item.patient_id === patientId))
  const eligibleDevices = devices.data.filter((item) => item.status === 'online' && (!item.assigned_patient_id || item.assigned_patient_id === patientId))
  const selectedPatient = patients.data.find((item) => item.id === patientId) ?? patients.data[0]
  const selectedDevice = eligibleDevices.find((item) => item.id === deviceId) ?? eligibleDevices[0]
  const selectedProtocol = eligibleProtocols.find((item) => item.id === protocolId) ?? eligibleProtocols[0]
  const protocol = protocols.data.find((item) => item.id === live.session.protocol_id) ?? selectedProtocol ?? demoProtocols[0]
  const telemetry = live.session.telemetry
  const status = live.session.status
  const progress = Math.min(100, telemetry.cumulative_dose_j_cm2 / protocol.target_dose_j_cm2 * 100)
  const elapsedSeconds = Math.max(0, Math.floor(telemetry.elapsed_seconds))
  const elapsedLabel = `${String(Math.floor(elapsedSeconds / 60)).padStart(2, '0')}:${String(elapsedSeconds % 60).padStart(2, '0')}`
  const sessionShown = status === 'active' || status === 'paused' || status === 'completed'

  useEffect(() => {
    if (!patients.data.some((item) => item.id === patientId) && patients.data[0]) setPatientId(patients.data[0].id)
  }, [patientId, patients.data])

  useEffect(() => {
    if (selectedDevice && selectedDevice.id !== deviceId) setDeviceId(selectedDevice.id)
    if (selectedProtocol && selectedProtocol.id !== protocolId) setProtocolId(selectedProtocol.id)
  }, [deviceId, protocolId, selectedDevice, selectedProtocol])

  if (patients.loading || devices.loading || protocols.loading) return <LoadingState label="Loading session configuration" />

  const wavelengthLow = protocol.wavelength_nm - protocol.wavelength_tolerance_nm
  const wavelengthHigh = protocol.wavelength_nm + protocol.wavelength_tolerance_nm
  const temperatureStatus: VitalStatus = telemetry.skin_temperature_c >= protocol.skin_temperature_max_c ? 'danger' : telemetry.skin_temperature_c > protocol.skin_temperature_max_c - 2 ? 'warning' : 'normal'
  const spo2Status: VitalStatus = telemetry.spo2_percent <= protocol.spo2_min_percent - 4 ? 'danger' : telemetry.spo2_percent < protocol.spo2_min_percent ? 'warning' : 'normal'
  const irradianceStatus: VitalStatus = telemetry.irradiance_mw_cm2 > protocol.irradiance_max_mw_cm2 * 1.25 ? 'danger' : telemetry.irradiance_mw_cm2 > protocol.irradiance_max_mw_cm2 ? 'warning' : 'normal'
  const wavelengthStatus: VitalStatus = telemetry.wavelength_nm < wavelengthLow || telemetry.wavelength_nm > wavelengthHigh ? 'danger' : 'normal'

  return (
    <div className="page-stack">
      <SourceNotice source={patients.source === 'api' && devices.source === 'api' && protocols.source === 'api' ? 'api' : 'demo'} error={patients.error ?? devices.error ?? protocols.error} onRetry={() => { patients.retry(); devices.retry(); protocols.retry() }} />

      <section className="panel session-bar">
        <div className="session-bar__identity">
          <span className={`session-state session-state--${status}`}>{statusLabel[status]}</span>
          <div>
            <strong>{sessionShown ? live.session.patient_name : 'New supervised session'}</strong>
            <span>{sessionShown ? `${live.session.protocol_name} · ${live.session.device_label}` : 'Select a patient, an online device and an active prescription.'}</span>
          </div>
        </div>
        <div className="session-bar__controls">
          {!sessionShown && <>
            <label><span>Patient</span><select aria-label="Patient" value={patientId} onChange={(event) => setPatientId(event.target.value)}>{patients.data.map((patient) => <option key={patient.id} value={patient.id}>{patient.name}</option>)}</select></label>
            <label><span>Device</span><select aria-label="Device" value={selectedDevice?.id ?? ''} onChange={(event) => setDeviceId(event.target.value)}>{eligibleDevices.length === 0 && <option value="">No eligible online device</option>}{eligibleDevices.map((device) => <option key={device.id} value={device.id}>{device.serial_number} · {device.model}</option>)}</select></label>
            <label><span>Prescription</span><select aria-label="Prescription" value={selectedProtocol?.id ?? ''} onChange={(event) => setProtocolId(event.target.value)}>{eligibleProtocols.length === 0 && <option value="">No active linked prescription</option>}{eligibleProtocols.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            <Button disabled={live.busy || !selectedPatient || !selectedDevice || !selectedProtocol} icon={<Radio size={16} />} onClick={() => selectedPatient && selectedDevice && selectedProtocol && live.start({ patient: selectedPatient, device: selectedDevice, protocol: selectedProtocol })}>{live.busy ? 'Starting…' : 'Start session'}</Button>
          </>}
          {sessionShown && <>
            <StatusPill tone={connectionTone[live.connection]}>{connectionLabel[live.connection]}</StatusPill>
            {status === 'active'
              ? <Button variant="danger" icon={<Square size={14} />} disabled={live.busy} onClick={() => setShowStopConfirm(true)}>Stop session</Button>
              : <Button variant="secondary" icon={<RotateCcw size={15} />} onClick={live.reset}>New session</Button>}
          </>}
        </div>
      </section>

      {live.error && <div className="inline-warning" role="status"><ShieldAlert size={16} /><span>{live.error}</span></div>}

      {sessionShown ? <>
        <section className="vitals" aria-label="Current telemetry">
          <Vital label="Wavelength" value={telemetry.wavelength_nm.toFixed(1)} unit="nm" limit={`${wavelengthLow}–${wavelengthHigh} nm`} status={wavelengthStatus} />
          <Vital label="Irradiance" value={telemetry.irradiance_mw_cm2.toFixed(2)} unit="mW/cm²" limit={`envelope ${protocol.irradiance_min_mw_cm2}–${protocol.irradiance_max_mw_cm2}`} status={irradianceStatus} />
          <Vital label="Delivered dose" value={telemetry.cumulative_dose_j_cm2.toFixed(3)} unit="J/cm²" limit={`target ${protocol.target_dose_j_cm2} · ceiling ${protocol.max_session_dose_j_cm2}`} status={progress >= 100 ? 'complete' : 'normal'} />
          <Vital label="Skin temperature" value={telemetry.skin_temperature_c.toFixed(2)} unit="°C" limit={`limit ${protocol.skin_temperature_max_c} °C`} status={temperatureStatus} />
          <Vital label="SpO₂" value={telemetry.spo2_percent.toFixed(1)} unit="%" limit={`minimum ${protocol.spo2_min_percent} %`} status={spo2Status} />
        </section>

        <div className="live-grid">
          <div className="live-grid__main page-stack">
            <section className="panel">
              <div className="panel__header">
                <h2>Telemetry</h2>
                <div className="timeline-meta"><span>Elapsed <strong>{elapsedLabel}</strong></span><span>Samples <strong>{live.sampleCount}</strong></span></div>
              </div>
              <div className="panel__body">
                <TelemetryChart points={live.history} irradianceMin={protocol.irradiance_min_mw_cm2} irradianceMax={protocol.irradiance_max_mw_cm2} temperatureMax={protocol.skin_temperature_max_c} />
                <div className="dose-progress">
                  <span>Delivered dose <strong>{telemetry.cumulative_dose_j_cm2.toFixed(3)}</strong> of target <strong>{protocol.target_dose_j_cm2.toFixed(2)} J/cm²</strong></span>
                  <div className={status === 'completed' ? 'progress-bar progress-bar--complete' : 'progress-bar'}><span style={{ width: `${progress}%` }} /></div>
                  <span>{progress.toFixed(0)} %</span>
                </div>
              </div>
            </section>

            <section className="panel scenario-panel">
              <div className="panel__header"><h2>Simulator scenario</h2><span className="panel__hint">Synthetic telemetry for rule testing; not clinical validation</span></div>
              <div className="panel__body scenario-grid">
                {scenarioOptions.map((option) => <button key={option.id} className={live.scenario === option.id ? 'scenario-option scenario-option--active' : 'scenario-option'} disabled={status !== 'active'} onClick={() => live.inject(option.id)} aria-pressed={live.scenario === option.id}><strong>{option.label}</strong><span>{option.description}</span></button>)}
              </div>
            </section>
          </div>
          <aside className="live-grid__decision"><DecisionCard decision={live.session.decision} /></aside>
        </div>
      </> : <section className="panel">
        <div className="panel__header"><h2>Session preflight</h2><StatusPill tone="neutral">Telemetry inactive</StatusPill></div>
        <div className="panel__body">
          <table className="kv-table kv-table--wide" aria-label="Session preflight">
            <tbody>
              <tr><th scope="row">Patient</th><td>{selectedPatient ? `${selectedPatient.name} · ${selectedPatient.mrn}` : 'No eligible patient'}</td></tr>
              <tr><th scope="row">Device</th><td>{selectedDevice ? `${selectedDevice.label} · ${selectedDevice.serial_number}` : 'No eligible online device'}</td></tr>
              <tr><th scope="row">Prescription</th><td>{selectedProtocol ? `${selectedProtocol.name} · version ${selectedProtocol.version}` : 'No eligible prescription'}</td></tr>
              {selectedProtocol && <>
                <tr><th scope="row">Target wavelength</th><td>{selectedProtocol.wavelength_nm} ± {selectedProtocol.wavelength_tolerance_nm} nm</td></tr>
                <tr><th scope="row">Irradiance</th><td>target {selectedProtocol.target_irradiance_mw_cm2} mW/cm², envelope {selectedProtocol.irradiance_min_mw_cm2}–{selectedProtocol.irradiance_max_mw_cm2} mW/cm²</td></tr>
                <tr><th scope="row">Target dose</th><td>{selectedProtocol.target_dose_j_cm2} J/cm²</td></tr>
                <tr><th scope="row">Session dose ceiling</th><td>{selectedProtocol.max_session_dose_j_cm2} J/cm²</td></tr>
                <tr><th scope="row">Maximum duration</th><td>{selectedProtocol.duration_max_min} min</td></tr>
                <tr><th scope="row">Skin temperature limit</th><td>{selectedProtocol.skin_temperature_max_c} °C</td></tr>
                <tr><th scope="row">Minimum SpO₂</th><td>{selectedProtocol.spo2_min_percent} %</td></tr>
              </>}
            </tbody>
          </table>
          <p className="panel__note">The server re-checks prescription validity, device calibration and session exclusivity when the session starts.</p>
        </div>
      </section>}

      {showStopConfirm && <div className="modal-layer" role="presentation">
        <button className="modal-backdrop" aria-label="Cancel stop session" onClick={() => setShowStopConfirm(false)} />
        <div className="confirm-modal" role="alertdialog" aria-modal="true" aria-labelledby="stop-title" aria-describedby="stop-description">
          <h2 id="stop-title">Stop the session?</h2>
          <p id="stop-description">The session ends with status “stopped”. Delivered dose and all decisions stay in the audit trail. A new session requires a new start.</p>
          <div className="confirm-modal__actions"><Button variant="secondary" onClick={() => setShowStopConfirm(false)}>Continue session</Button><Button variant="danger" onClick={() => { setShowStopConfirm(false); void live.stop() }}>Stop and record</Button></div>
        </div>
      </div>}
    </div>
  )
}

function Vital({ label, value, unit, limit, status }: { label: string; value: string; unit: string; limit: string; status: VitalStatus }) {
  return (
    <div className={`vital vital--${status}`}>
      <span className="vital__label">{label}</span>
      <span className="vital__value"><strong>{value}</strong> {unit}</span>
      <span className="vital__limit">{limit}</span>
    </div>
  )
}
