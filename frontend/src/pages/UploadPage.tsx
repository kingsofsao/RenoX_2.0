import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, FlaskConical, ShieldCheck, Trash2 } from 'lucide-react'
import { DatabaseNotice } from '../components/DatabaseNotice'
import { UploadDropzone } from '../components/UploadDropzone'
import { Alert, Button, ButtonLink, Card, CardHeader, PageHeader, ProgressBar, StatusBadge, cx } from '../components/ui'
import { useHealth } from '../hooks/HealthContext'
import { useProjects } from '../hooks/ProjectContext'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { api } from '../services/api'
import { errorText } from '../services/errors'
import { formatBytes } from '../services/format'
import type { UploadResult } from '../types/api'

type ItemState = 'queued' | 'invalid' | 'uploading' | 'processing' | 'done' | 'error'

interface QueueItem {
  key: string
  file: File
  state: ItemState
  progress: number
  problem?: { key: MessageKey; vars?: Record<string, string | number> }
  message?: string
  result?: UploadResult
}

const DEFAULT_MAX_MB = 25

function validate(file: File, maxMb: number): QueueItem['problem'] {
  if (!file.name.toLowerCase().endsWith('.pdf')) return { key: 'upload.invalid.type' }
  if (file.size === 0) return { key: 'upload.invalid.empty' }
  if (file.size > maxMb * 1024 * 1024) return { key: 'upload.invalid.size', vars: { mb: maxMb, size: formatBytes(file.size) } }
  return undefined
}

const FAILURE_KEYS: Record<string, MessageKey> = {
  encrypted: 'paper.failure.encrypted', no_text: 'paper.failure.no_text', empty: 'paper.failure.empty', corrupt: 'paper.failure.corrupt',
  not_pdf: 'upload.invalid.type', empty_file: 'upload.invalid.empty', too_large: 'error.tooLarge',
}

/** The server's per-file outcome in the UI language (the server's own text when the code is unknown). */
function resultMessage(t: (k: MessageKey, v?: Record<string, string | number>) => string, r: UploadResult): string {
  if (r.status === 'processed') return t('upload.result.processed', { pages: r.page_count ?? '?' })
  if (r.status === 'duplicate') return t('upload.result.duplicate')
  const key = r.error_code ? FAILURE_KEYS[r.error_code] : undefined
  return key ? t(key, { mb: '' }) : r.message
}

export function UploadPage() {
  const { t, tn } = useI18n()
  const { health } = useHealth()
  const { refresh: refreshProjects } = useProjects()
  const maxMb = health?.config.max_upload_mb ?? DEFAULT_MAX_MB
  const dbReady = health?.database.status === 'connected'
  const [queue, setQueue] = useState<QueueItem[]>([])
  const [running, setRunning] = useState(false)

  const update = (key: string, patch: Partial<QueueItem>) =>
    setQueue((q) => q.map((item) => (item.key === key ? { ...item, ...patch } : item)))

  const addFiles = (files: File[]) => {
    setQueue((q) => {
      const existing = new Set(q.map((i) => i.key))
      const added = files
        .map((file) => ({ file, key: `${file.name}:${file.size}:${file.lastModified}` }))
        .filter(({ key }) => !existing.has(key))
        .map(({ file, key }): QueueItem => {
          const problem = validate(file, maxMb)
          return { key, file, state: problem ? 'invalid' : 'queued', progress: 0, problem }
        })
      return [...q, ...added]
    })
  }

  const pending = queue.filter((i) => i.state === 'queued')
  const finished = queue.filter((i) => i.state === 'done' || i.state === 'error').length
  const batchSize = queue.filter((i) => i.state !== 'invalid').length

  // Files go up one request each so every file gets its own progress bar and result,
  // even though the API also accepts several files in one request.
  const startUpload = async () => {
    setRunning(true)
    for (const item of pending) {
      update(item.key, { state: 'uploading', progress: 0, message: undefined })
      try {
        const res = await api.uploadPapers([item.file], (pct) =>
          update(item.key, pct >= 100 ? { progress: 100, state: 'processing' } : { progress: pct }),
        )
        const result = res.results[0]
        update(item.key, { state: 'done', progress: 100, result, message: resultMessage(t, result) })
      } catch (err) {
        update(item.key, { state: 'error', message: errorText(t, err) })
      }
    }
    setRunning(false)
    void refreshProjects()  // paper counts in the project switcher
  }

  const results = queue.filter((i) => i.result).map((i) => i.result!)
  const ready = results.filter((r) => (r.status === 'processed' || r.status === 'duplicate') && r.paper_id)
  const summary = useMemo(() => {
    const count = (s: UploadResult['status']) => results.filter((r) => r.status === s).length
    return { processed: count('processed'), duplicate: count('duplicate'), failed: count('failed') + count('rejected'),
      errors: queue.filter((i) => i.state === 'error').length }
  }, [results, queue])

  return (
    <>
      <PageHeader title={t('upload.title')} description={t('upload.description')} />
      <div className="space-y-6">
        <DatabaseNotice />
        <UploadDropzone onFiles={addFiles} disabled={running} maxMb={maxMb} />
        <p className="flex items-center gap-2 text-xs text-fg-subtle"><ShieldCheck className="h-4 w-4 text-ok" />{t('upload.privacy')}</p>

        {queue.length > 0 && (
          <Card className="animate-fade-up">
            <CardHeader
              title={t('upload.files', { count: queue.length })}
              subtitle={running ? t('upload.running') : tn('upload.ready', pending.length)}
              action={
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" disabled={running} onClick={() => setQueue([])}>{t('common.clear')}</Button>
                  <Button size="sm" loading={running} disabled={pending.length === 0 || !dbReady} onClick={startUpload}
                    title={!dbReady ? t('error.unavailable') : undefined}>
                    {running ? t('upload.uploading') : tn('upload.submit', pending.length)}
                  </Button>
                </div>
              }
            />
            {running && batchSize > 0 && (
              <div className="border-b border-line px-5 py-3">
                <div className="mb-1.5 flex justify-between text-xs text-fg-muted">
                  <span>{t('upload.overall')}</span><span className="tabular-nums">{finished} / {batchSize}</span>
                </div>
                <ProgressBar value={(finished / batchSize) * 100} label={t('upload.overall')} />
              </div>
            )}
            <ul className="divide-y divide-line">
              {queue.map((item) => (
                <li key={item.key} className="flex items-start gap-3 px-5 py-3.5">
                  <FileText className={cx('mt-0.5 h-5 w-5 shrink-0', item.state === 'invalid' ? 'text-warn' : 'text-fg-subtle')} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="truncate font-medium text-fg">{item.file.name}</span>
                      <span className="text-xs text-fg-subtle">{formatBytes(item.file.size)}</span>
                      {item.result && <StatusBadge status={item.result.status} />}
                      {item.state === 'invalid' && <StatusBadge status="rejected" />}
                    </div>
                    {(item.state === 'uploading' || item.state === 'processing') && (
                      <div className="mt-2">
                        <ProgressBar value={item.progress} indeterminate={item.state === 'processing'} />
                        <p className="mt-1 text-xs text-fg-muted">
                          {item.state === 'uploading' ? t('upload.progress', { pct: item.progress }) : t('upload.processing')}
                        </p>
                      </div>
                    )}
                    {(item.problem || item.message) && (
                      <p className={cx('mt-1 text-sm', item.state === 'error' || item.result?.status === 'failed' ? 'text-bad-fg'
                        : item.state === 'invalid' || item.result?.status === 'rejected' ? 'text-warn-fg' : 'text-fg-muted')}>
                        {item.problem ? t(item.problem.key, item.problem.vars) : item.message}
                      </p>
                    )}
                    {item.result?.paper_id && (item.result.status === 'processed' || item.result.status === 'duplicate') && (
                      <div className="mt-1.5 flex flex-wrap gap-3 text-sm">
                        <Link to={`/investigate?paper=${item.result.paper_id}`} className="inline-flex items-center gap-1 font-medium text-brand hover:text-brand-hover">
                          <FlaskConical className="h-3.5 w-3.5" />{t('paper.analyse')}
                        </Link>
                        <Link to={`/papers/${item.result.paper_id}`} className="font-medium text-fg-muted hover:text-fg">{t('upload.viewPaper')}</Link>
                      </div>
                    )}
                  </div>
                  {!running && (item.state === 'queued' || item.state === 'invalid') && (
                    <button onClick={() => setQueue((q) => q.filter((i) => i.key !== item.key))}
                      className="rounded p-1 text-fg-subtle transition-colors hover:bg-surface-3 hover:text-fg"
                      aria-label={t('upload.remove', { name: item.file.name })}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {!running && results.length > 0 && (
          <Alert tone={summary.failed || summary.errors ? 'warning' : 'success'} title={t('upload.finished')}
            action={ready.length === 1 ? (
              <ButtonLink to={`/investigate?paper=${ready[0].paper_id}`} size="sm"><FlaskConical className="h-4 w-4" />{t('paper.analyse')}</ButtonLink>
            ) : ready.length > 1 ? <ButtonLink to="/investigate" size="sm"><FlaskConical className="h-4 w-4" />{t('upload.chooseToAnalyse')}</ButtonLink> : undefined}>
            {t('upload.summary', { processed: summary.processed, duplicate: summary.duplicate, failed: summary.failed })}
            {summary.errors ? ` · ${t('upload.summary.errors', { count: summary.errors })}` : ''}
          </Alert>
        )}
      </div>
    </>
  )
}
