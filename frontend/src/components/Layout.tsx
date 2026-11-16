import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { Menu, Radio, Search, X } from 'lucide-react'
import { CommandPalette } from './CommandPalette'
import { useSystemHealth } from '../hooks/useSystemHealth'

const navigation = [
  { to: '/', label: 'Dashboard' },
  { to: '/live-therapy', label: 'Live session' },
  { to: '/patients', label: 'Patients' },
  { to: '/protocols', label: 'Prescriptions' },
  { to: '/devices', label: 'Devices' },
  { to: '/alerts', label: 'Safety alerts' },
  { to: '/audit', label: 'Audit & FHIR' },
]

const pageMeta: Record<string, { title: string; description: string }> = {
  '/': { title: 'Dashboard', description: 'Running sessions, open safety alerts and the state of connected devices.' },
  '/live-therapy': { title: 'Live session', description: 'Telemetry, the current recommendation and the rules behind it.' },
  '/patients': { title: 'Patients', description: 'Research records and their linked prescriptions.' },
  '/devices': { title: 'Devices', description: 'Connectivity, assignment and calibration of light-therapy devices.' },
  '/protocols': { title: 'Prescriptions', description: 'Exposure limits that the decision engine applies to each session.' },
  '/alerts': { title: 'Safety alerts', description: 'Alerts raised by safety interlocks and their acknowledgement.' },
  '/audit': { title: 'Audit & FHIR', description: 'Recorded events and FHIR R4-aligned research bundles.' },
}

function Logo() {
  return (
    <svg className="brand__icon" viewBox="0 0 48 48" aria-hidden="true">
      <rect x="7" y="13" width="28" height="20" rx="4" fill="none" stroke="currentColor" strokeWidth="2.6" />
      <path d="M11 24h5l2.5-5 4 10 2.5-5h6" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M21 33v5M15 39h12" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" />
      <circle cx="38.5" cy="9.5" r="4.5" fill="none" stroke="currentColor" strokeWidth="2.4" />
      <path d="M38.5 2v1.6M46 9.5h-1.6M43.8 4.2l-1.1 1.1" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  )
}

export function Layout() {
  const [menuOpen, setMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const health = useSystemHealth()
  const location = useLocation()
  const meta = pageMeta[location.pathname] ?? pageMeta['/']

  useEffect(() => {
    setMenuOpen(false)
    setSearchOpen(false)
  }, [location.pathname])

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault()
        setSearchOpen(true)
      }
      if (event.key === 'Escape') setSearchOpen(false)
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  const healthLabel = health.state === 'ready' ? 'Server online' : health.state === 'offline' ? 'Offline · demo records' : 'Connecting'

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar__inner">
          <Link to="/" className="brand" aria-label="LumaCare DSS dashboard">
            <Logo />
            <span className="brand__name">LumaCare</span>
            <span className="brand__tag">DSS</span>
          </Link>
          <nav className={`topnav ${menuOpen ? 'topnav--open' : ''}`} aria-label="Primary navigation">
            {navigation.map(({ to, label }) => <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>)}
          </nav>
          <div className="topbar__tools">
            <button className="tool-button" onClick={() => setSearchOpen(true)} aria-label="Search records (Ctrl K)" title="Search records (Ctrl K)"><Search size={18} /></button>
            <span className={`server-state server-state--${health.state}`} role="status" aria-live="polite"><i aria-hidden="true" />{healthLabel}</span>
            {location.pathname !== '/live-therapy' && <Link to="/live-therapy" className="button button--primary topbar__cta"><Radio size={16} aria-hidden="true" /><span>Live session</span></Link>}
            <button className="tool-button topbar__menu" onClick={() => setMenuOpen((value) => !value)} aria-label={menuOpen ? 'Close navigation' : 'Open navigation'} aria-expanded={menuOpen}>{menuOpen ? <X size={20} /> : <Menu size={20} />}</button>
          </div>
        </div>
      </header>

      <main className="page-content" id="main-content">
        <div className="page-heading">
          <div>
            <h1>{meta.title}</h1>
            <p>{meta.description}</p>
          </div>
          <span className="page-heading__note">Research use only · synthetic records</span>
        </div>
        <Outlet />
      </main>
      <footer className="app-footer">
        <span>LumaCare DSS 1.1.0 · light-therapy decision support research prototype</span>
        <span>Recommendations are not intended for clinical decisions.</span>
      </footer>
      {searchOpen && <CommandPalette open query={searchQuery} onQueryChange={setSearchQuery} onClose={() => setSearchOpen(false)} />}
    </div>
  )
}
