import { Link } from 'react-router-dom'
import { AlertOctagon, ArrowRight, BookOpen, CheckCircle2, Database, FlaskConical, History, Layers, Network, Sparkles, Upload } from 'lucide-react'
import { useAuth } from '../auth/AuthProvider'
import { DatabaseNotice } from '../components/DatabaseNotice'
import { PaperTable } from '../components/PaperTable'
import { StatCard } from '../components/StatCard'
import { Alert, Badge, ButtonLink, Card, CardHeader, EmptyState, LoadingBlock, PageHeader } from '../components/ui'
import { useHealth } from '../hooks/HealthContext'
import { useProjects } from '../hooks/ProjectContext'
import { useAsync } from '../hooks/useAsync'
import { usePageMeta } from '../hooks/usePageMeta'
import { useI18n } from '../i18n/I18nProvider'
import { api } from '../services/api'
import { errorText } from '../services/errors'

export function DashboardPage() {
  const { t, formatDate } = useI18n()
  usePageMeta(t('nav.overview'), undefined, { noindex: true })
  const { user } = useAuth()
  const { active } = useProjects()
  const { health } = useHealth()
  const dbStatus = health?.database.status
  // Refetch when the database comes (back) online.
  const papers = useAsync(() => api.listPapers({ limit: 5 }), [dbStatus])
  const stats = useAsync(() => api.graphStats(), [dbStatus])
  const recent = useAsync(() => api.listInvestigations(5), [dbStatus])

  const counts = papers.data?.counts
  const nodes = stats.data?.nodes ?? {}
  const unavailable = !!papers.error
  const ai = health?.config.llm
  const aiReady = ai?.status === 'ready' || ai?.status === 'configured'
  const firstName = user?.name.split(/\s+/)[0] ?? ''

  return (
    <>
      <PageHeader
        eyebrow={active?.name}
        title={t('dashboard.greeting', { name: firstName })}
        description={t('dashboard.description')}
        actions={
          <>
            <ButtonLink to="/upload" variant="secondary"><Upload className="h-4 w-4" /> {t('nav.upload')}</ButtonLink>
            <ButtonLink to="/investigate"><FlaskConical className="h-4 w-4" /> {t('dashboard.newInvestigation')}</ButtonLink>
          </>
        }
      />
      <div className="space-y-6">
        <DatabaseNotice />

        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label={t('dashboard.stat.papers')} value={unavailable ? null : counts?.total ?? null} loading={papers.loading && !papers.data}
            icon={<BookOpen className="h-5 w-5" />} hint={t('dashboard.stat.papers.hint')} />
          <StatCard label={t('dashboard.stat.processed')} value={unavailable ? null : counts?.processed ?? null} loading={papers.loading && !papers.data}
            tone="ok" icon={<CheckCircle2 className="h-5 w-5" />} hint={t('dashboard.stat.processed.hint')} />
          <StatCard label={t('dashboard.stat.failed')} value={unavailable ? null : counts?.failed ?? null} loading={papers.loading && !papers.data}
            tone="bad" icon={<AlertOctagon className="h-5 w-5" />} hint={t('dashboard.stat.failed.hint')} />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label={t('dashboard.stat.chunks')} value={stats.error ? null : nodes.Chunk ?? 0} loading={stats.loading && !stats.data} tone="neutral" icon={<Layers className="h-5 w-5" />} />
          <StatCard label={t('dashboard.stat.methods')} value={stats.error ? null : nodes.Method ?? 0} loading={stats.loading && !stats.data} tone="neutral" icon={<FlaskConical className="h-5 w-5" />} />
          <StatCard label={t('dashboard.stat.datasets')} value={stats.error ? null : nodes.Dataset ?? 0} loading={stats.loading && !stats.data} tone="neutral" icon={<Database className="h-5 w-5" />} />
          <StatCard label={t('dashboard.stat.relationships')} value={stats.error ? null : stats.data?.relationships ?? 0} loading={stats.loading && !stats.data} tone="neutral" icon={<Network className="h-5 w-5" />} />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader title={t('dashboard.recentPapers')}
              action={<Link to="/library" className="inline-flex items-center gap-1 text-sm font-medium text-brand hover:text-brand-hover">{t('common.viewAll')}<ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" /></Link>} />
            {papers.loading && !papers.data ? (
              <LoadingBlock />
            ) : papers.error ? (
              <div className="p-5"><Alert tone="error" title={t('library.loadFailed')}>{errorText(t, papers.error)}</Alert></div>
            ) : papers.data && papers.data.papers.length > 0 ? (
              <PaperTable papers={papers.data.papers} compact />
            ) : (
              <EmptyState icon={<BookOpen className="h-6 w-6" />} title={t('library.empty.title')} description={t('library.empty.text')}
                action={<ButtonLink to="/upload"><Upload className="h-4 w-4" />{t('nav.upload')}</ButtonLink>} />
            )}
          </Card>

          <div className="space-y-6">
            <Card className="overflow-hidden">
              <div className="relative bg-black p-5 text-white">
                <div className="pointer-events-none absolute -end-10 -top-10 h-40 w-40 rounded-full bg-[#1c69d4]/40 blur-3xl" />
                <div className="relative">
                  <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.12em] text-white/60">
                    <Sparkles className="h-3.5 w-3.5 text-[#5ea2ff]" /> {t('dashboard.ai.title')}
                  </div>
                  <p className="mt-2 text-lg font-semibold">{aiReady ? t('dashboard.ai.ready') : t('dashboard.ai.unavailable')}</p>
                  <p className="mt-1 text-sm text-white/60">{aiReady ? t('dashboard.ai.readyText') : t('dashboard.ai.unavailableText')}</p>
                  {ai?.model && aiReady && <Badge className="mt-3 bg-white/10 text-white/85">{ai.model}</Badge>}
                </div>
              </div>
            </Card>
            <Card>
              <CardHeader title={t('dashboard.recentInvestigations')}
                action={<Link to="/investigate" className="text-sm font-medium text-brand hover:text-brand-hover">{t('common.viewAll')}</Link>} />
              {recent.loading && !recent.data ? <LoadingBlock rows={2} /> : recent.data && recent.data.investigations.length > 0 ? (
                <ul className="divide-y divide-line">
                  {recent.data.investigations.map((it) => (
                    <li key={it.id}>
                      <Link to={`/investigate?open=${it.id}`} className="flex gap-3 px-5 py-3 transition-colors hover:bg-surface-2">
                        <History className="mt-0.5 h-4 w-4 shrink-0 text-fg-subtle" />
                        <span className="min-w-0">
                          <span className="line-clamp-2 text-sm text-fg">{it.question}</span>
                          <span className="text-xs text-fg-subtle">{it.paper_title ? `${it.paper_title} · ` : ''}{formatDate(it.created_at)}</span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-5 py-6 text-sm text-fg-subtle">{t('dashboard.noInvestigations')}</p>
              )}
            </Card>
          </div>
        </div>
      </div>
    </>
  )
}
