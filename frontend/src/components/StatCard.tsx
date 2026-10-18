import type { ReactNode } from 'react'
import { useI18n } from '../i18n/I18nProvider'
import { Card, cx } from './ui'

export function StatCard({
  label, value, icon, hint, tone = 'brand', loading,
}: {
  label: string
  value: number | null
  icon: ReactNode
  hint?: string
  tone?: 'brand' | 'ok' | 'bad' | 'neutral'
  loading?: boolean
}) {
  const { formatNumber } = useI18n()
  const tones = {
    brand: 'bg-brand-soft text-brand',
    ok: 'bg-ok-soft text-ok',
    bad: 'bg-bad-soft text-bad',
    neutral: 'bg-surface-3 text-fg-muted',
  }
  return (
    <Card className="group p-5 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-pop">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm text-fg-muted">{label}</p>
          <p className="mt-1.5 text-3xl font-semibold tracking-tight tabular-nums text-fg">
            {loading ? <span className="skeleton inline-block h-8 w-14 align-middle" /> : value == null ? '-' : formatNumber(value)}
          </p>
        </div>
        <div className={cx('rounded-xl p-2.5 transition-transform duration-200 group-hover:scale-110', tones[tone])}>{icon}</div>
      </div>
      {hint && <p className="mt-3 text-xs text-fg-subtle">{hint}</p>}
    </Card>
  )
}
