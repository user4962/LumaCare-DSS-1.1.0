import type { ButtonHTMLAttributes, PropsWithChildren, ReactNode } from 'react'
import { AlertTriangle, Database, Inbox, RefreshCw, X } from 'lucide-react'
import type { DataSource } from '../hooks/useApiResource'

export function StatusPill({ tone = 'neutral', children }: PropsWithChildren<{ tone?: 'success' | 'warning' | 'danger' | 'info' | 'neutral' }>) {
  return <span className={`status-pill status-pill--${tone}`}>{children}</span>
}

export function Button({ variant = 'primary', icon, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'danger' | 'ghost'; icon?: ReactNode }) {
  return (
    <button className={`button button--${variant}`} {...props}>
      {icon}<span>{children}</span>
    </button>
  )
}

export function IconButton({ label, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <button className="icon-button" aria-label={label} title={label} {...props}>{children}</button>
}

export function SourceNotice({ source, error, onRetry }: { source: DataSource; error: string | null; onRetry?: () => void }) {
  if (source === 'api' && !error) return null
  return (
    <div className="source-notice" role="status">
      <div className="source-notice__icon"><Database size={16} aria-hidden="true" /></div>
      <div>
        <strong>Synthetic demo data</strong>
        <span>{error ? `${error} Research workflows remain available with deterministic fallback records.` : 'This view uses synthetic records for research demonstration.'}</span>
      </div>
      {onRetry && <button className="text-button" onClick={onRetry}><RefreshCw size={14} aria-hidden="true" /> Retry API</button>}
    </div>
  )
}

export function LoadingState({ label = 'Loading research workspace' }: { label?: string }) {
  return (
    <div className="loading-state" role="status" aria-label={label}>
      <div className="skeleton skeleton--title" />
      <div className="skeleton-grid">
        <div className="skeleton skeleton--card" /><div className="skeleton skeleton--card" /><div className="skeleton skeleton--card" />
      </div>
      <span className="sr-only">{label}</span>
    </div>
  )
}

export function EmptyState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return (
    <div className="empty-state">
      <Inbox size={26} aria-hidden="true" />
      <strong>{title}</strong>
      <p>{detail}</p>
      {action}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="error-state" role="alert">
      <AlertTriangle size={20} aria-hidden="true" />
      <div><strong>Data could not be loaded</strong><p>{message}</p></div>
      <Button variant="secondary" onClick={onRetry}>Try again</Button>
    </div>
  )
}

export function Drawer({ open, onClose, title, eyebrow, children }: PropsWithChildren<{ open: boolean; onClose: () => void; title: string; eyebrow?: string }>) {
  // The drawer is mounted only while open, so a hidden panel never widens the page.
  if (!open) return null
  return (
    <>
      <button className="drawer-backdrop" aria-label="Close details" onClick={onClose} />
      <aside className="drawer" aria-label={`${title} details`}>
        <div className="drawer__header">
          <div>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{title}</h2></div>
          <IconButton label="Close details" onClick={onClose}><X size={20} /></IconButton>
        </div>
        <div className="drawer__body">{children}</div>
      </aside>
    </>
  )
}

export function MetricCard({ label, value, detail, icon, tone = 'teal', delta }: { label: string; value: ReactNode; detail: string; icon: ReactNode; tone?: 'teal' | 'coral' | 'blue' | 'amber'; delta?: string }) {
  return (
    <article className="metric-card">
      <div className={`metric-card__icon metric-card__icon--${tone}`}>{icon}</div>
      <div className="metric-card__content">
        <div className="metric-card__label">{label}</div>
        <div className="metric-card__value">{value}</div>
        <div className="metric-card__detail">{detail}{delta && <span className="metric-card__delta">{delta}</span>}</div>
      </div>
    </article>
  )
}
