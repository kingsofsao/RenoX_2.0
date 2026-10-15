import { RefreshCw } from 'lucide-react'
import { useHealth } from '../hooks/HealthContext'
import { cx } from './ui'

type Level = 'ok' | 'warn' | 'down' | 'pending'

const dot: Record<Level, string> = {
  ok: 'bg-emerald-500',
  warn: 'bg-amber-500',
  down: 'bg-red-500',
  pending: 'bg-slate-300 animate-pulse',
}

function Row({ label, level, value }: { label: string; level: Level; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 text-xs">
      <span className="text-slate-400">{label}</span>
      <span className="flex min-w-0 items-center gap-1.5 text-slate-200">
        <span className={cx('h-2 w-2 shrink-0 rounded-full', dot[level])} />
        <span className="truncate">{value}</span>
      </span>
    </div>
  )
}

/** Compact backend + database status shown in the sidebar footer. */
export function HealthIndicator() {
  const { health, error, loading, lastChecked, refresh } = useHealth()

  const backend: [Level, string] = loading && !health && !error ? ['pending', 'Checking…'] : error ? ['down', 'Offline'] : ['ok', 'Online']
  let database: [Level, string] = ['pending', 'Checking…']
  if (error) database = ['down', 'Unknown']
  else if (health) {
    const s = health.database.status
    database = s === 'connected'
      ? ['ok', `Connected${health.database.latency_ms != null ? ` · ${health.database.latency_ms} ms` : ''}`]
      : s === 'not_configured' ? ['warn', 'Not configured'] : ['down', 'Unavailable']
  }

  return (
    <div className="space-y-2 rounded-lg bg-slate-800/60 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium uppercase tracking-wide text-slate-400">System status</span>
        <button onClick={refresh} className="rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-slate-200" title="Re-check now" aria-label="Re-check status">
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
      <Row label="API" level={backend[0]} value={backend[1]} />
      <Row label="FalkorDB" level={database[0]} value={database[1]} />
      {health && <Row label="Graph" level={database[0] === 'ok' ? 'ok' : 'pending'} value={health.database.graph} />}
      {lastChecked && <p className="text-[10px] text-slate-500">Checked {lastChecked.toLocaleTimeString()}</p>}
    </div>
  )
}
