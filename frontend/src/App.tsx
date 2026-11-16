import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { LoadingState } from './components/ui'

const OverviewPage = lazy(() => import('./pages/OverviewPage').then((module) => ({ default: module.OverviewPage })))
const LiveTherapyPage = lazy(() => import('./pages/LiveTherapyPage').then((module) => ({ default: module.LiveTherapyPage })))
const PatientsPage = lazy(() => import('./pages/PatientsPage').then((module) => ({ default: module.PatientsPage })))
const DevicesPage = lazy(() => import('./pages/DevicesPage').then((module) => ({ default: module.DevicesPage })))
const ProtocolsPage = lazy(() => import('./pages/ProtocolsPage').then((module) => ({ default: module.ProtocolsPage })))
const AlertsPage = lazy(() => import('./pages/AlertsPage').then((module) => ({ default: module.AlertsPage })))
const AuditPage = lazy(() => import('./pages/AuditPage').then((module) => ({ default: module.AuditPage })))

export default function App() {
  return (
    <Suspense fallback={<div className="route-loading"><LoadingState label="Loading workspace module" /></div>}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<OverviewPage />} />
          <Route path="live-therapy" element={<LiveTherapyPage />} />
          <Route path="patients" element={<PatientsPage />} />
          <Route path="devices" element={<DevicesPage />} />
          <Route path="protocols" element={<ProtocolsPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="audit" element={<AuditPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
