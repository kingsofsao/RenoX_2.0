import { Link } from 'react-router-dom'
import { AlertOctagon, BookOpen, CheckCircle2, Database, FlaskConical, Layers, Network, Upload } from 'lucide-react'
import { DatabaseNotice } from '../components/DatabaseNotice'
import { PaperTable } from '../components/PaperTable'
import { StatCard } from '../components/StatCard'
import { Alert, Button, Card, CardHeader, EmptyState, LoadingBlock, PageHeader } from '../components/ui'
import { useHealth } from '../hooks/HealthContext'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'

export function DashboardPage() {
  const { health } = useHealth()
  const dbStatus = health?.database.status
  // Refetch when the database comes (back) online.
  const papers = useAsync(() => api.listPapers({ limit: 5 }), [dbStatus])
  const stats = useAsync(() => api.graphStats(), [dbStatus])

  const counts = papers.data?.counts
  const nodes = stats.data?.nodes ?? {}
  const unavailable = !!papers.error

  return (
    <>
      <PageHeader
        title="Research workspace"
        description="Live overview of the papers and knowledge stored in your FalkorDB graph."
        actions={
          <Link to="/upload"><Button><Upload className="h-4 w-4" /> Upload PDFs</Button></Link>
        }
      />
      <div className="space-y-6">
        <DatabaseNotice />

        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Total papers" value={unavailable ? null : counts?.total ?? null} loading={papers.loading && !papers.data}
            icon={<BookOpen className="h-5 w-5" />} hint="Every uploaded PDF recorded in the graph" />
          <StatCard label="Processed" value={unavailable ? null : counts?.processed ?? null} loading={papers.loading && !papers.data}
            tone="emerald" icon={<CheckCircle2 className="h-5 w-5" />} hint="Text extracted and linked in the graph" />
          <StatCard label="Failed uploads" value={unavailable ? null : counts?.failed ?? null} loading={papers.loading && !papers.data}
            tone="red" icon={<AlertOctagon className="h-5 w-5" />} hint="Encrypted, corrupt, scanned or empty PDFs" />
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Evidence chunks" value={stats.error ? null : nodes.Chunk ?? 0} loading={stats.loading && !stats.data} tone="slate" icon={<Layers className="h-5 w-5" />} />
          <StatCard label="Methods" value={stats.error ? null : nodes.Method ?? 0} loading={stats.loading && !stats.data} tone="slate" icon={<FlaskConical className="h-5 w-5" />} />
          <StatCard label="Datasets" value={stats.error ? null : nodes.Dataset ?? 0} loading={stats.loading && !stats.data} tone="slate" icon={<Database className="h-5 w-5" />} />
          <StatCard label="Relationships" value={stats.error ? null : stats.data?.relationships ?? 0} loading={stats.loading && !stats.data} tone="slate" icon={<Network className="h-5 w-5" />} />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader title="Recently updated papers" action={<Link to="/library" className="text-sm font-medium text-indigo-600 hover:text-indigo-500">View all</Link>} />
            {papers.loading && !papers.data ? (
              <LoadingBlock />
            ) : papers.error ? (
              <div className="p-5"><Alert tone="error" title="Could not load papers">{papers.error.message}</Alert></div>
            ) : papers.data && papers.data.papers.length > 0 ? (
              <PaperTable papers={papers.data.papers} compact />
            ) : (
              <EmptyState icon={<BookOpen className="h-6 w-6" />} title="No papers yet"
                description="Upload research PDFs to start building the knowledge graph."
                action={<Link to="/upload"><Button>Upload PDFs</Button></Link>} />
            )}
          </Card>

          <Card>
            <CardHeader title="Backend health" subtitle="Polled every 15 seconds" />
            <dl className="divide-y divide-slate-100 text-sm">
              {[
                ['API', health ? `Online · v${health.backend.version}` : 'Unreachable'],
                ['FalkorDB', health ? health.database.status.replace('_', ' ') : '—'],
                ['Graph', health?.database.graph ?? '—'],
                ['Latency', health?.database.latency_ms != null ? `${health.database.latency_ms} ms` : '—'],
                ['Upload limit', health ? `${health.config.max_upload_mb} MB · ${health.config.max_files_per_upload} files` : '—'],
                ['Embeddings', health?.config.embedding_model ?? 'Loading…'],
                ['LLM', health ? (health.config.llm.provider === 'none' ? 'Not configured (offline mode)' : `${health.config.llm.provider} / ${health.config.llm.model ?? '?'} · ${health.config.llm.status.replace('_', ' ')}`) : '—'],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-4 px-5 py-2.5">
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="truncate text-right font-medium capitalize text-slate-800">{v}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>
      </div>
    </>
  )
}
