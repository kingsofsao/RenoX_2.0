import { useState, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ChevronLeft, ChevronRight, ExternalLink, FileText, FlaskConical, Trash2 } from 'lucide-react'
import { Alert, Button, ButtonLink, Card, CardHeader, EmptyState, LoadingBlock, StatusBadge, buttonClass, cx } from '../components/ui'
import { useProjects } from '../hooks/ProjectContext'
import { useAsync } from '../hooks/useAsync'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { api } from '../services/api'
import { errorText } from '../services/errors'
import { formatBytes, shortHash } from '../services/format'
import type { PaperDetail } from '../types/api'

const FAILURE_HELP: Record<string, MessageKey> = {
  encrypted: 'paper.failure.encrypted',
  no_text: 'paper.failure.no_text',
  empty: 'paper.failure.empty',
  corrupt: 'paper.failure.corrupt',
}

function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="px-5 py-2.5 sm:grid sm:grid-cols-3 sm:gap-4">
      <dt className="text-sm text-fg-subtle">{label}</dt>
      <dd className="mt-0.5 break-words text-sm text-fg sm:col-span-2 sm:mt-0">{children}</dd>
    </div>
  )
}

function Chips({ items, empty }: { items: { name: string; page: number | null }[]; empty: string }) {
  const { t } = useI18n()
  if (!items.length) return <p className="text-sm text-fg-subtle">{empty}</p>
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((m) => (
        <span key={m.name} className="rounded-md bg-surface-3 px-2 py-1 text-xs text-fg" title={m.page ? t('paper.firstEvidence', { page: m.page }) : undefined}>
          {m.name}{m.page ? <span className="ms-1 text-fg-subtle">p.{m.page}</span> : null}
        </span>
      ))}
    </div>
  )
}

function KnowledgeCard({ paper }: { paper: PaperDetail }) {
  const { t } = useI18n()
  const k = paper.knowledge
  if (!k) return null
  const tiles: [string, number][] = [[t('paper.k.chunks'), k.chunks], [t('paper.k.claims'), k.claims], [t('paper.k.findings'), k.findings], [t('paper.k.limitations'), k.limitations]]
  return (
    <Card>
      <CardHeader title={t('paper.knowledge')} subtitle={t('paper.knowledge.subtitle')} />
      <div className="space-y-4 p-5">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {tiles.map(([label, n]) => (
            <div key={label} className="rounded-lg bg-surface-2 px-3 py-2">
              <p className="text-xs text-fg-subtle">{label}</p>
              <p className="text-lg font-semibold tabular-nums text-fg">{n}</p>
            </div>
          ))}
        </div>
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-fg-subtle">{t('paper.methods')}</p>
          <Chips items={k.methods} empty={t('paper.methods.none')} />
        </div>
        <div>
          <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-fg-subtle">{t('paper.datasets')}</p>
          <Chips items={k.datasets} empty={t('paper.datasets.none')} />
        </div>
        {k.sections.length > 0 && (
          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-fg-subtle">{t('paper.sections')}</p>
            <p className="text-sm text-fg-muted">{k.sections.join(' · ')}</p>
          </div>
        )}
      </div>
    </Card>
  )
}

export function PaperDetailPage() {
  const { t, formatDate, formatNumber } = useI18n()
  const { paperId = '' } = useParams()
  const navigate = useNavigate()
  const { refresh: refreshProjects } = useProjects()
  const [page, setPage] = useState(1)
  const [deleting, setDeleting] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const { data, error, loading } = useAsync(() => api.getPaper(paperId, page, 1), [paperId, page])

  const back = <Link to="/library" className="inline-flex items-center gap-1 text-sm text-fg-muted transition-colors hover:text-fg"><ArrowLeft className="h-4 w-4 rtl:rotate-180" /> {t('paper.back')}</Link>
  if (loading && !data) return <Card><LoadingBlock rows={6} /></Card>
  if (error && !data) {
    return (
      <div className="space-y-4">
        {back}
        <Alert tone="error" title={error.status === 404 ? t('paper.notFound') : t('paper.loadFailed')}>{errorText(t, error)}</Alert>
      </div>
    )
  }
  if (!data) return null

  const { paper, pages, pagination } = data
  const unknown = <span className="italic text-fg-subtle">{t('common.unknown')}</span>
  const remove = async () => {
    setDeleting(true)
    try {
      await api.deletePaper(paper.id)
      void refreshProjects()
      navigate('/library')
    } catch (err) {
      setDeleteError(errorText(t, err))
      setDeleting(false)
    }
  }

  return (
    <div className="space-y-6">
      {back}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="mb-2 flex items-center gap-2"><StatusBadge status={paper.status} /></div>
          <h1 className="text-2xl font-semibold tracking-tight text-fg">
            {paper.title ?? <span className="italic text-fg-muted">{t('paper.untitled')}</span>}
          </h1>
          <p className="mt-1 text-sm text-fg-muted">{paper.authors.length ? paper.authors.join(', ') : t('paper.authorsUnknown')}{paper.year ? ` · ${paper.year}` : ''}</p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {paper.status === 'processed' && (
            <ButtonLink to={`/investigate?paper=${encodeURIComponent(paper.id)}`}><FlaskConical className="h-4 w-4" /> {t('paper.analyse')}</ButtonLink>
          )}
          <a href={api.paperFileUrl(paper.id)} target="_blank" rel="noopener noreferrer" className={buttonClass('secondary')}>
            <ExternalLink className="h-4 w-4" /> {t('paper.openPdf')}
          </a>
          <Button variant="danger" onClick={() => setConfirming(true)} disabled={deleting}><Trash2 className="h-4 w-4" /> {t('common.delete')}</Button>
        </div>
      </div>
      {confirming && (
        <Alert tone="error" title={t('paper.delete.title')}
          action={<div className="flex gap-2">
            <Button variant="danger" size="sm" loading={deleting} onClick={() => void remove()}>{t('common.delete')}</Button>
            <Button variant="ghost" size="sm" onClick={() => setConfirming(false)}>{t('common.cancel')}</Button>
          </div>}>
          {t('paper.delete.text', { title: paper.display_title })}
        </Alert>
      )}
      {deleteError && <Alert tone="error" title={t('paper.delete.failed')}>{deleteError}</Alert>}

      {paper.status === 'failed' && (
        <Alert tone="error" title={t('paper.failed.title')}>
          {paper.error_code && FAILURE_HELP[paper.error_code] ? t(FAILURE_HELP[paper.error_code]) : paper.error}
        </Alert>
      )}

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader title={t('paper.metadata')} />
            <dl className="divide-y divide-line">
              <Meta label={t('paper.col.title')}>{paper.title ?? unknown}</Meta>
              <Meta label={t('paper.authors')}>{paper.authors.length ? paper.authors.join(', ') : unknown}</Meta>
              <Meta label={t('paper.year')}>{paper.year ?? unknown}</Meta>
              <Meta label={t('paper.filename')}>{paper.filename ?? unknown}</Meta>
              <Meta label={t('paper.col.pages')}>{paper.page_count ?? unknown}</Meta>
              <Meta label={t('paper.col.size')}>{formatBytes(paper.file_size)}</Meta>
              <Meta label={t('paper.id')}><code className="text-xs">{paper.id}</code></Meta>
              <Meta label="SHA-256"><code className="text-xs" title={paper.sha256 ?? ''}>{shortHash(paper.sha256, 20)}</code></Meta>
              <Meta label={t('paper.ingested')}>{formatDate(paper.ingested_at ?? paper.updated_at)}</Meta>
              {Object.entries(paper.pdf_metadata).map(([k, v]) => <Meta key={k} label={`PDF ${k}`}>{v}</Meta>)}
            </dl>
          </Card>
          <KnowledgeCard paper={paper} />
        </div>

        <Card className="lg:col-span-3">
          <CardHeader
            title={t('paper.text')}
            subtitle={data.text_available ? t('paper.text.subtitle', { page: pagination.page, total: pagination.total_pages }) : undefined}
            action={data.text_available && pagination.total_pages > 1 ? (
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" disabled={page <= 1 || loading} onClick={() => setPage((p) => p - 1)} title={t('common.previous')}>
                  <ChevronLeft className="h-4 w-4 rtl:rotate-180" />
                </Button>
                <span className="w-16 text-center text-sm tabular-nums text-fg-muted">{pagination.page} / {pagination.total_pages}</span>
                <Button variant="ghost" size="sm" disabled={page >= pagination.total_pages || loading} onClick={() => setPage((p) => p + 1)} title={t('common.next')}>
                  <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                </Button>
              </div>
            ) : undefined}
          />
          {!data.text_available ? (
            <EmptyState icon={<FileText className="h-6 w-6" />} title={t('paper.text.none')} description={paper.status === 'failed' ? t('paper.text.failed') : t('paper.text.unavailable')} />
          ) : (
            <div className={cx('max-h-[70vh] overflow-y-auto p-5 transition-opacity', loading && 'opacity-60')}>
              {pages.map((p) => (
                <article key={p.page}>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wide text-fg-subtle">{t('paper.text.page', { page: p.page, chars: formatNumber(p.chars) })}</p>
                  {p.text.trim() ? (
                    <pre dir="auto" className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-fg">{p.text}</pre>
                  ) : (
                    <p className="text-sm italic text-fg-subtle">{t('paper.text.blank')}</p>
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
