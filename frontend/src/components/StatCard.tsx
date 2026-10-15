import type { ReactNode } from 'react'
import { Card, cx } from './ui'

export function StatCard({
  label, value, icon, hint, tone = 'indigo', loading,
}: {
  label: string
  value: number | null
  icon: ReactNode
  hint?: string
  tone?: 'indigo' | 'emerald' | 'red' | 'slate'
  loading?: boolean
}) {
  const tones = {
    indigo: 'bg-indigo-50 text-indigo-600',
    emerald: 'bg-emerald-50 text-emerald-600',
    red: 'bg-red-50 text-red-600',
    slate: 'bg-slate-100 text-slate-600',
  }
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="mt-1 text-3xl font-semibold tabular-nums text-slate-900">
            {loading ? <span className="inline-block h-8 w-12 animate-pulse rounded bg-slate-100" /> : value == null ? '—' : value.toLocaleString()}
          </p>
        </div>
        <div className={cx('rounded-lg p-2.5', tones[tone])}>{icon}</div>
      </div>
      {hint && <p className="mt-3 text-xs text-slate-500">{hint}</p>}
    </Card>
  )
}
