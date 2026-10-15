import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight, ExternalLink, FileText, Trash2 } from 'lucide-react'
import { Alert, Button, Card, CardHeader, EmptyState, LoadingBlock, StatusBadge, cx } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { api } from '../services/api'
import { formatBytes, formatDate, shortHash } from '../services/format'
import type { PaperDetail } from '../types/api'

const FAILURE_HELP: Record<string, string> = {
  encrypted: 'Remove the password protection (e.g. print to PDF) and upload again.',
  no_text: 'This looks like a scanned document. OCR support is planned as a later enhancement.',
  empty: 'The PDF has no extractable text content.',
  corrupt: 'The file could not be parsed. Try re-exporting or re-downloading the PDF.',
}

function Meta({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="px-5 py-2.5 sm:grid sm:grid-cols-3 sm:gap-4">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className="mt-0.5 break-words text-sm text-slate-900 sm:col-span-2 sm:mt-0">{children}</dd>
    </div>
  )
}

const unknown = <span className="italic text-slate-400">Unknown</span>

function Chips({ items, empty }: { items: { name: string; page: number | null }[]; empty: string }) {
  if (!items.length) return <p className="text-sm text-slate-400">{empty}</p>
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((m) => (
        <span key={m.name} className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-700" title={m.page ? `First evidence on page ${m.page}` : undefined}>
          {m.name}{m.page ? <span className="ml-1 text-slate-400">p.{m.page}</span> : null}
        </span>
      ))}
    </div>
  )
}

function KnowledgeCard({ paper }: { paper: PaperDetail }) {
  const k = paper.knowledge
  if (!k) return null
  return (
    <Card>
      <CardHeader title="Extracted knowledge" subtitle={`Extractor: ${k.extractor ?? 'unknown'} · candidate entities, each linked to its evidence page`} />
      <div className="space-y-4 p-5">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[['Evidence chunks', k.chunks], ['Claims', k.claims], ['Findings', k.findings], ['Limitations', k.limitations]].map(([label, n]) => (
            <div key={label} className="rounded-lg bg-slate-50 px-3 py-2">
              <p className="text-xs text-slate-500">{label}</p>
              <p className="text-lg font-semibold tabular-nums text-slate-900">{n}</p>
            </div>
          ))}
        </div>
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">Methods</p>
          <Chips items={k.methods} empty="No methods detected." />
        </div>
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">Datasets</p>
          <Chips items={k.datasets} empty="No datasets detected." />
        </div>
        {k.sections.length > 0 && (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-slate-500">Detected sections</p>
            <p className="text-sm text-slate-700">{k.sections.join(' · ')}</p>
          </div>
        )}
      </div>
    </Card>
  )
}

export function PaperDetailPage() {
  const { paperId = '' } = useParams()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const { data, error, loading } = useAsync(() => api.getPaper(paperId, page, 1), [paperId, page])

  if (loading && !data) return <LoadingBlock label="Loading paper…" />
  if (error && !data) {
    return (
      <div className="space-y-4">
        <Link to="/library" className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"><ArrowLeft className="h-4 w-4" /> Back to library</Link>
        <Alert tone="error" title={error.status === 404 ? 'Paper not found' : 'Could not load this paper'}>{error.message}</Alert>
      </div>
    )
  }
  if (!data) return null

  const { paper, pages, pagination } = data
  const remove = async () => {
    if (!window.confirm(`Delete "${paper.display_title}" from the knowledge graph? This cannot be undone.`)) return
    setDeleting(true)
    try {
      await api.deletePaper(paper.id)
      navigate('/library')
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : 'Delete failed.')
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-6">
      <Link to="/library" className="inline-flex items-center gap-1 text-sm text-slate-600 hover:text-slate-900"><ArrowLeft className="h-4 w-4" /> Back to library</Link>

      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex items-center gap-2"><StatusBadge status={paper.status} /></div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            {paper.title ?? <span className="italic text-slate-500">Title not detected</span>}
          </h1>
          <p className="mt-1 text-sm text-slate-500">{paper.authors.length ? paper.authors.join(', ') : 'Authors unknown'}{paper.year ? ` · ${paper.year}` : ''}</p>
        </div>
        <div className="flex shrink-0 gap-2">
          <a href={api.paperFileUrl(paper.id)} target="_blank" rel="noreferrer"><Button variant="secondary"><ExternalLink className="h-4 w-4" /> Open PDF</Button></a>
          <Button variant="danger" onClick={remove} disabled={deleting}><Trash2 className="h-4 w-4" /> {deleting ? 'Deleting…' : 'Delete'}</Button>
        </div>
      </div>
      {deleteError && <Alert tone="error" title="Delete failed">{deleteError}</Alert>}

      {paper.status === 'failed' && (
        <Alert tone="error" title="This PDF could not be processed">
          {paper.error}{paper.error_code && FAILURE_HELP[paper.error_code] ? ` ${FAILURE_HELP[paper.error_code]}` : ''}
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title="Document metadata" />
            <dl className="divide-y divide-slate-100">
              <Meta label="Title">{paper.title ?? unknown}</Meta>
              <Meta label="Authors">{paper.authors.length ? paper.authors.join(', ') : unknown}</Meta>
              <Meta label="Year">{paper.year ?? unknown}</Meta>
              <Meta label="File name">{paper.filename ?? unknown}</Meta>
              <Meta label="Pages">{paper.page_count ?? unknown}</Meta>
              <Meta label="File size">{formatBytes(paper.file_size)}</Meta>
              <Meta label="Paper ID"><code className="text-xs">{paper.id}</code></Meta>
              <Meta label="SHA-256"><code className="text-xs" title={paper.sha256 ?? ''}>{shortHash(paper.sha256, 20)}</code></Meta>
              <Meta label="Ingested">{formatDate(paper.ingested_at ?? paper.updated_at)}</Meta>
              {Object.entries(paper.pdf_metadata).map(([k, v]) => <Meta key={k} label={`PDF ${k}`}>{v}</Meta>)}
            </dl>
          </Card>
          <KnowledgeCard paper={paper} />
        </div>

        <Card className="lg:col-span-3">
          <CardHeader
            title="Extracted text"
            subtitle={data.text_available ? `Page ${pagination.page} of ${pagination.total_pages} · exactly as extracted by pdfplumber` : undefined}
            action={data.text_available && pagination.total_pages > 1 ? (
              <div className="flex items-center gap-1">
                <Button variant="ghost" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)} title="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
                <span className="w-16 text-center text-sm tabular-nums text-slate-600">{pagination.page} / {pagination.total_pages}</span>
                <Button variant="ghost" disabled={page >= pagination.total_pages || loading} onClick={() => setPage((p) => p + 1)} title="Next page"><ChevronRight className="h-4 w-4" /></Button>
              </div>
            ) : undefined}
          />
          {!data.text_available ? (
            <EmptyState icon={<FileText className="h-6 w-6" />} title="No extracted text" description={paper.status === 'failed' ? 'Text extraction failed for this file.' : 'Page text is not available for this paper.'} />
          ) : (
            <div className={cx('max-h-[70vh] overflow-y-auto p-5', loading && 'opacity-60')}>
              {pages.map((p) => (
                <article key={p.page}>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">Page {p.page} · {p.chars.toLocaleString()} characters</p>
                  {p.text.trim() ? (
                    <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-slate-800">{p.text}</pre>
                  ) : (
                    <p className="text-sm italic text-slate-400">No text on this page (it may contain only images or figures).</p>
                  )}
                </article>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
