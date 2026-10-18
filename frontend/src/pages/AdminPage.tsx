// Admin-only: consented, aggregate usage statistics and contact messages. The server answers 404 to everyone else.
import { useMemo, useState } from 'react'
import { BarChart3, Mail, Table2 } from 'lucide-react'
import { Alert, Badge, Card, CardHeader, LoadingBlock, PageHeader, cx } from '../components/ui'
import { usePageMeta } from '../hooks/usePageMeta'
import { useAsync } from '../hooks/useAsync'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { api } from '../services/api'
import { errorText } from '../services/errors'
import type { AdminAnalytics, MetricEvent } from '../types/api'

const EVENTS: { key: MetricEvent; label: MessageKey }[] = [
  { key: 'page_view', label: 'admin.event.page_view' },
  { key: 'signup', label: 'admin.event.signup' },
  { key: 'upload', label: 'admin.event.upload' },
  { key: 'investigation', label: 'admin.event.investigation' },
]

/** Daily page views: one series, thin bars with 2px gaps, rounded data ends, a tooltip per bar. */
function DailyBars({ data }: { data: AdminAnalytics }) {
  const { t, formatNumber, formatDate } = useI18n()
  const [hover, setHover] = useState<number | null>(null)
  const [asTable, setAsTable] = useState(false)
  const max = Math.max(1, ...data.series.map((d) => d.page_view))
  // Plot area: a left gutter for the axis labels (L) and room above the top label (T).
  const W = 720, H = 180, L = 32, T = 8, gap = 2
  const bw = (W - L) / data.series.length - gap
  const ticks = [...new Set([0, Math.ceil(max / 2), max])]
  const yOf = (v: number) => T + H - (v / max) * H
  const day = (d: string) => formatDate(d + 'T00:00:00Z', { month: 'short', day: 'numeric' })

  return (
    <Card>
      <CardHeader title={t('admin.chart.title', { days: data.days })} subtitle={t('admin.chart.subtitle')}
        action={<button type="button" onClick={() => setAsTable((v) => !v)}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-fg-muted hover:bg-surface-3 hover:text-fg">
          {asTable ? <BarChart3 className="h-3.5 w-3.5" /> : <Table2 className="h-3.5 w-3.5" />}{asTable ? t('admin.chart') : t('admin.table')}
        </button>} />
      {asTable ? (
        <div className="max-h-80 overflow-y-auto">
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-surface-2 text-xs text-fg-subtle"><tr>
              <th className="px-5 py-2 text-start font-medium">{t('admin.day')}</th>
              {EVENTS.map((e) => <th key={e.key} className="px-3 py-2 text-end font-medium">{t(e.label)}</th>)}
            </tr></thead>
            <tbody className="divide-y divide-line">
              {[...data.series].reverse().map((d) => (
                <tr key={d.day}><td className="px-5 py-1.5 text-fg">{day(d.day)}</td>
                  {EVENTS.map((e) => <td key={e.key} className="px-3 py-1.5 text-end tabular-nums text-fg-muted">{formatNumber(d[e.key])}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="relative px-5 pb-4 pt-5" dir="ltr">
          <svg viewBox={`0 0 ${W} ${T + H + 20}`} className="h-auto w-full" role="img" aria-label={t('admin.chart.title', { days: data.days })}>
            {ticks.map((v) => {
              const y = yOf(v)
              return (
                <g key={v}>
                  <line x1={L} x2={W} y1={y} y2={y} stroke="var(--line)" strokeWidth="1" />
                  <text x={L - 8} y={y} textAnchor="end" dominantBaseline="middle" fontSize="10" fill="var(--fg-subtle)">{formatNumber(v)}</text>
                </g>
              )
            })}
            {data.series.map((d, i) => {
              const h = (d.page_view / max) * H
              const x = L + i * (bw + gap)
              return (
                <g key={d.day} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                  <rect x={x - gap / 2} y={T} width={bw + gap} height={H} fill="transparent" />
                  {h > 0 && <path d={`M${x} ${T + H} V${T + H - h + Math.min(4, h)} q0 -${Math.min(4, h)} ${Math.min(4, h)} -${Math.min(4, h)} H${x + bw - Math.min(4, h)} q${Math.min(4, h)} 0 ${Math.min(4, h)} ${Math.min(4, h)} V${T + H} Z`}
                    fill="var(--brand)" opacity={hover === null || hover === i ? 1 : 0.45} />}
                </g>
              )
            })}
            <text x={L} y={T + H + 15} fontSize="10" fill="var(--fg-subtle)">{day(data.series[0].day)}</text>
            <text x={W} y={T + H + 15} textAnchor="end" fontSize="10" fill="var(--fg-subtle)">{day(data.series[data.series.length - 1].day)}</text>
          </svg>
          {hover !== null && (
            <div className="pointer-events-none absolute top-2 rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-pop"
              style={{ left: `clamp(8px, ${((hover + 0.5) / data.series.length) * 100}% - 70px, calc(100% - 150px))` }}>
              <p className="font-medium text-fg">{day(data.series[hover].day)}</p>
              {EVENTS.map((e) => (
                <p key={e.key} className="flex justify-between gap-4 text-fg-muted"><span>{t(e.label)}</span>
                  <span className="tabular-nums text-fg">{formatNumber(data.series[hover][e.key])}</span></p>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

export default function AdminPage() {
  const { t, formatNumber, formatDate } = useI18n()
  usePageMeta(t('admin.title'), undefined, { noindex: true })
  const [days, setDays] = useState(30)
  const stats = useAsync(() => api.adminAnalytics(days), [days])
  const messages = useAsync(() => api.adminMessages(), [])
  const topics = useMemo<Record<string, MessageKey>>(() => ({
    question: 'contact.topic.question', feedback: 'contact.topic.feedback', bug: 'contact.topic.bug', privacy: 'contact.topic.privacy',
  }), [])

  return (
    <>
      <PageHeader title={t('admin.title')} description={t('admin.description')}
        actions={
          <div className="inline-flex rounded-lg bg-surface-3 p-1" role="tablist" aria-label={t('admin.range')}>
            {[7, 30, 90].map((d) => (
              <button key={d} role="tab" aria-selected={days === d} onClick={() => setDays(d)}
                className={cx('rounded-md px-3 py-1.5 text-sm font-medium transition-colors', days === d ? 'bg-surface text-fg shadow-sm' : 'text-fg-muted hover:text-fg')}>
                {t('admin.days', { days: d })}
              </button>
            ))}
          </div>
        } />
      <div className="space-y-6">
        {stats.error ? <Alert tone="error">{errorText(t, stats.error)}</Alert> : !stats.data ? <Card><LoadingBlock rows={5} /></Card> : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {EVENTS.map((e) => (
                <Card key={e.key} className="p-5">
                  <p className="text-sm text-fg-muted">{t(e.label)}</p>
                  <p className="mt-1.5 text-3xl font-semibold tabular-nums tracking-tight text-fg">{formatNumber(stats.data!.totals[e.key])}</p>
                </Card>
              ))}
            </div>
            <DailyBars data={stats.data} />
            <div className="grid gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader title={t('admin.paths')} />
                {stats.data.top_paths.length === 0 ? <p className="px-5 py-6 text-sm text-fg-subtle">{t('admin.none')}</p> : (
                  <table className="min-w-full text-sm"><tbody className="divide-y divide-line">
                    {stats.data.top_paths.map((p) => (
                      <tr key={p.path}><td className="px-5 py-2 font-mono text-xs text-fg">{p.path}</td>
                        <td className="px-5 py-2 text-end tabular-nums text-fg-muted">{formatNumber(p.views)}</td></tr>
                    ))}
                  </tbody></table>
                )}
              </Card>
              <Card>
                <CardHeader title={t('admin.campaigns')} subtitle={t('admin.campaigns.subtitle')} />
                {stats.data.campaigns.length === 0 ? <p className="px-5 py-6 text-sm text-fg-subtle">{t('admin.none')}</p> : (
                  <table className="min-w-full text-sm">
                    <thead className="bg-surface-2 text-xs text-fg-subtle"><tr>
                      <th className="px-5 py-2 text-start font-medium">utm</th>
                      <th className="px-3 py-2 text-end font-medium">{t('admin.event.page_view')}</th>
                      <th className="px-5 py-2 text-end font-medium">{t('admin.event.signup')}</th>
                    </tr></thead>
                    <tbody className="divide-y divide-line">
                      {stats.data.campaigns.map((c) => (
                        <tr key={c.campaign}><td className="px-5 py-2 text-fg">{c.campaign}</td>
                          <td className="px-3 py-2 text-end tabular-nums text-fg-muted">{formatNumber(c.page_view)}</td>
                          <td className="px-5 py-2 text-end tabular-nums text-fg-muted">{formatNumber(c.signup)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </Card>
            </div>
          </>
        )}
        <Card>
          <CardHeader title={<span className="flex items-center gap-2"><Mail className="h-4 w-4 text-brand" />{t('admin.messages')}</span>} />
          {messages.error ? <div className="p-5"><Alert tone="error">{errorText(t, messages.error)}</Alert></div>
            : !messages.data ? <LoadingBlock rows={3} />
              : messages.data.messages.length === 0 ? <p className="px-5 py-6 text-sm text-fg-subtle">{t('admin.none')}</p> : (
                <ul className="divide-y divide-line">
                  {messages.data.messages.map((m) => (
                    <li key={m.id} className="px-5 py-4">
                      <div className="flex flex-wrap items-center gap-2 text-sm">
                        <span className="font-medium text-fg">{m.name}</span>
                        <a href={`mailto:${m.email}`} className="text-brand hover:underline">{m.email}</a>
                        <Badge>{topics[m.topic] ? t(topics[m.topic]) : m.topic}</Badge>
                        {m.user_id && <Badge tone="brand">{t('admin.member')}</Badge>}
                        <span className="ms-auto text-xs text-fg-subtle">{formatDate(m.created_at)}</span>
                      </div>
                      <p className="mt-2 whitespace-pre-wrap break-words text-sm text-fg-muted" dir="auto">{m.message}</p>
                    </li>
                  ))}
                </ul>
              )}
        </Card>
      </div>
    </>
  )
}
