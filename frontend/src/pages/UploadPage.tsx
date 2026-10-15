import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { FileText, Loader2, Trash2 } from 'lucide-react'
import { DatabaseNotice } from '../components/DatabaseNotice'
import { UploadDropzone } from '../components/UploadDropzone'
import { Alert, Button, Card, CardHeader, PageHeader, StatusBadge, cx } from '../components/ui'
import { useHealth } from '../hooks/HealthContext'
import { api } from '../services/api'
import { formatBytes } from '../services/format'
import type { UploadResult } from '../types/api'

type ItemState = 'queued' | 'invalid' | 'uploading' | 'processing' | 'done' | 'error'

interface QueueItem {
  key: string
  file: File
  state: ItemState
  progress: number
  message?: string
  result?: UploadResult
}

const DEFAULT_MAX_MB = 25

function validate(file: File, maxMb: number): string | null {
  if (!file.name.toLowerCase().endsWith('.pdf')) return 'Not a PDF file (.pdf only).'
  if (file.size === 0) return 'The file is empty.'
  if (file.size > maxMb * 1024 * 1024) return `Larger than the ${maxMb} MB limit (${formatBytes(file.size)}).`
  return null
}

export function UploadPage() {
  const { health } = useHealth()
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
          return { key, file, state: problem ? 'invalid' : 'queued', progress: 0, message: problem ?? undefined }
        })
      return [...q, ...added]
    })
  }

  const pending = queue.filter((i) => i.state === 'queued')

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
        update(item.key, { state: 'done', progress: 100, result, message: result.message })
      } catch (err) {
        update(item.key, { state: 'error', message: err instanceof Error ? err.message : 'Upload failed.' })
      }
    }
    setRunning(false)
  }

  const results = queue.filter((i) => i.result).map((i) => i.result!)
  const summary = useMemo(() => {
    const count = (s: UploadResult['status']) => results.filter((r) => r.status === s).length
    return { processed: count('processed'), duplicate: count('duplicate'), failed: count('failed') + count('rejected'),
      errors: queue.filter((i) => i.state === 'error').length }
  }, [results, queue])

  return (
    <>
      <PageHeader
        title="Upload PDFs"
        description="Each PDF is validated, hashed (identical files are detected as duplicates), parsed page by page with pdfplumber, and stored in the FalkorDB knowledge graph."
      />
      <div className="space-y-6">
        <DatabaseNotice />
        <UploadDropzone onFiles={addFiles} disabled={running} maxMb={maxMb} />

        {queue.length > 0 && (
          <Card>
            <CardHeader
              title={`Files (${queue.length})`}
              subtitle={running ? 'Uploading and processing — keep this page open.' : `${pending.length} ready to upload`}
              action={
                <div className="flex gap-2">
                  <Button variant="ghost" disabled={running} onClick={() => setQueue([])}>Clear</Button>
                  <Button disabled={running || pending.length === 0 || !dbReady} onClick={startUpload}
                    title={!dbReady ? 'FalkorDB must be connected to store papers' : undefined}>
                    {running && <Loader2 className="h-4 w-4 animate-spin" />}
                    {running ? 'Uploading…' : `Upload ${pending.length || ''} file${pending.length === 1 ? '' : 's'}`}
                  </Button>
                </div>
              }
            />
            <ul className="divide-y divide-slate-100">
              {queue.map((item) => (
                <li key={item.key} className="flex items-start gap-3 px-5 py-3">
                  <FileText className={cx('mt-0.5 h-5 w-5 shrink-0', item.state === 'invalid' ? 'text-amber-500' : 'text-slate-400')} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span className="truncate font-medium text-slate-900">{item.file.name}</span>
                      <span className="text-xs text-slate-500">{formatBytes(item.file.size)}</span>
                      {item.result && <StatusBadge status={item.result.status} />}
                      {item.state === 'invalid' && <StatusBadge status="rejected" />}
                    </div>
                    {(item.state === 'uploading' || item.state === 'processing') && (
                      <div className="mt-2">
                        <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className={cx('h-full rounded-full bg-indigo-500 transition-all', item.state === 'processing' && 'animate-pulse')}
                            style={{ width: `${item.progress}%` }}
                          />
                        </div>
                        <p className="mt-1 text-xs text-slate-500">
                          {item.state === 'uploading' ? `Uploading… ${item.progress}%` : 'Processing on server: extracting text and writing to the graph…'}
                        </p>
                      </div>
                    )}
                    {item.message && (
                      <p className={cx('mt-1 text-sm', item.state === 'error' || item.result?.status === 'failed' ? 'text-red-600'
                        : item.state === 'invalid' || item.result?.status === 'rejected' ? 'text-amber-700' : 'text-slate-600')}>
                        {item.message}
                      </p>
                    )}
                    {item.result?.paper_id && item.result.status !== 'rejected' && (
                      <Link to={`/papers/${item.result.paper_id}`} className="mt-1 inline-block text-sm font-medium text-indigo-600 hover:text-indigo-500">
                        View paper →
                      </Link>
                    )}
                  </div>
                  {!running && (item.state === 'queued' || item.state === 'invalid') && (
                    <button onClick={() => setQueue((q) => q.filter((i) => i.key !== item.key))} className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600" aria-label={`Remove ${item.file.name}`}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </Card>
        )}

        {!running && results.length > 0 && (
          <Alert tone={summary.failed || summary.errors ? 'warning' : 'success'} title="Upload finished"
            action={<Link to="/library" className="whitespace-nowrap text-sm font-medium underline">Open library</Link>}>
            {summary.processed} processed · {summary.duplicate} already in the library · {summary.failed} failed or rejected
            {summary.errors ? ` · ${summary.errors} request error(s)` : ''}
          </Alert>
        )}
      </div>
    </>
  )
}
