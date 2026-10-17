import { RefreshCw } from 'lucide-react'
import { useHealth } from '../hooks/HealthContext'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { cx } from './ui'

type Level = 'ok' | 'warn' | 'down' | 'pending'

const dot: Record<Level, string> = {
  ok: 'bg-ok',
  warn: 'bg-warn',
  down: 'bg-bad',
  pending: 'bg-white/30 animate-pulse',
}

function Row({ label, level, value }: { label: string; level: Level; value: string }) {
  return (
    <div className="flex items-center justify-between gap-2 text-xs">
      <span className="text-white/45">{label}</span>
      <span className="flex min-w-0 items-center gap-1.5 text-white/80">
        <span className={cx('h-1.5 w-1.5 shrink-0 rounded-full', dot[level])} />
        <span className="truncate">{value}</span>
      </span>
    </div>
  )
}

/** Compact service status in the sidebar: the service, the database and the AI model, without internals. */
export function HealthIndicator() {
  const { t } = useI18n()
  const { health, error, loading, refresh } = useHealth()

  const service: [Level, MessageKey] = loading && !health && !error ? ['pending', 'health.checking'] : error ? ['down', 'health.offline'] : ['ok', 'health.online']
  let database: [Level, MessageKey] = ['pending', 'health.checking']
  let ai: [Level, MessageKey] = ['pending', 'health.checking']
  if (error) {
    database = ['down', 'health.unknown']
    ai = ['down', 'health.unknown']
  } else if (health) {
    database = health.database.status === 'connected' ? ['ok', 'health.connected'] : ['down', 'health.unavailable']
    const s = health.config.llm.status
    ai = s === 'ready' || s === 'configured' ? ['ok', 'health.ready'] : ['down', 'health.unavailable']
  }

  return (
    <div className="space-y-2 rounded-xl border border-sidebar-line bg-sidebar-2 p-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-white/40">{t('health.title')}</span>
        <button onClick={refresh} className="rounded p-1 text-white/40 transition-colors hover:bg-white/10 hover:text-white" title={t('health.recheck')} aria-label={t('health.recheck')}>
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
      </div>
      <Row label={t('health.service')} level={service[0]} value={t(service[1])} />
      <Row label={t('health.database')} level={database[0]} value={t(database[1])} />
      <Row label={t('health.ai')} level={ai[0]} value={t(ai[1])} />
    </div>
  )
}
