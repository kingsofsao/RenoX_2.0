import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Check, CheckCircle2, ChevronDown, ChevronRight, Clock, Download, FileText, FlaskConical, History, Loader2, Network, RotateCcw, Search, Sparkles,
  Trash2, Upload, XCircle,
} from 'lucide-react'
import { ConfidenceBadge, InvestigationResultView } from '../components/InvestigationResult'
import { ConfirmDialog } from '../components/Modal'
import { PaperPicker } from '../components/PaperPicker'
import { Alert, Badge, Button, ButtonLink, Card, CardHeader, EmptyState, PageHeader, ProgressBar, Textarea, cx } from '../components/ui'
import { useHealth } from '../hooks/HealthContext'
import { usePageMeta } from '../hooks/usePageMeta'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { ApiError, api, getActiveProject, pollInvestigation, toApiError } from '../services/api'
import { track } from '../services/analytics'
import { errorText } from '../services/errors'
import { buildMarkdownExport, downloadText, reportFilename } from '../services/report'
import type { Investigation, InvestigationSummary, PaperSummary } from '../types/api'

const MIN_CHARS = 10
const MAX_CHARS = 1000
const EXAMPLES: MessageKey[] = ['investigate.example.1', 'investigate.example.2', 'investigate.example.3']
// Per project: reopening the page resumes that project's last investigation, never another project's.
const storageKey = () => `researchmind.investigation.current.${getActiveProject()}`

function storedId(): string | null {
  try { return sessionStorage.getItem(storageKey()) } catch { return null }
}
function storeId(id: string | null) {
  try { if (id) sessionStorage.setItem(storageKey(), id); else sessionStorage.removeItem(storageKey()) } catch { /* storage unavailable */ }
}

function useElapsed(running: boolean, startedAt: string | null): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return
    const timer = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(timer)
  }, [running])
  if (!startedAt) return 0
  return Math.max(0, (now - new Date(startedAt).getTime()) / 1000)
}

const STAGES: MessageKey[] = ['progress.stage.retrieve', 'progress.stage.ai', 'progress.stage.verify', 'progress.stage.report']

/**
 * Where an investigation is, from its live events: evidence retrieval through the graph tools,
 * the AI writing (with its token count), citation verification, done. Returns a stage and a percentage.
 */
export function estimateProgress(inv: Investigation | null): { stage: number; pct: number } {
  if (!inv) return { stage: 0, pct: 2 }
  if (inv.status === 'completed') return { stage: 4, pct: 100 }
  const events = inv.progress
  if (!events.length) return { stage: 0, pct: 4 }
  let stage = 0
  let pct = 8
  const results = events.filter((e) => e.type === 'tool_result').length
  pct = Math.max(pct, 8 + (Math.min(results, 8) / 8) * 37)
  let tokens = 0
  for (const e of events) {
    if (/reading \d+ sources|planning the investigation|generating/i.test(e.message)) stage = Math.max(stage, 1)
    const m = e.message.match(/generating\D*(\d+) tokens/i)
    if (m) tokens = Number(m[1])
    if (/building structured report|verifying citations/i.test(e.message)) stage = Math.max(stage, 2)
  }
  if (stage >= 1) pct = Math.max(pct, 50 + Math.min(tokens / 900, 1) * 35)
  if (stage >= 2) pct = Math.max(pct, 92)
  return { stage, pct: Math.min(pct, 97) }
}

function ProgressPanel({ inv, paperTitle }: { inv: Investigation | null; paperTitle: string | null }) {
  const { t, formatNumber } = useI18n()
  const running = !inv || inv.status === 'queued' || inv.status === 'running'
  const elapsed = useElapsed(running, inv?.started_at ?? inv?.created_at ?? null)
  const [showLog, setShowLog] = useState(false)
  const events = inv?.progress ?? []
  const { stage, pct } = estimateProgress(inv)
  const listRef = useRef<HTMLOListElement>(null)
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight }) }, [events.length, showLog])

  return (
    <Card className="animate-fade-up overflow-hidden">
      <CardHeader
        title={<span className="flex items-center gap-2"><Loader2 className="h-4 w-4 animate-spin text-brand" />{t('progress.title')}</span>}
        subtitle={paperTitle ? t('progress.subtitle', { title: paperTitle }) : undefined}
        action={<span className="inline-flex items-center gap-1.5 text-xs tabular-nums text-fg-subtle"><Clock className="h-3.5 w-3.5" />{formatNumber(Math.round(elapsed))} s</span>}
      />
      <div className="space-y-5 p-5">
        <div>
          <div className="mb-2 flex items-baseline justify-between">
            <span className="text-sm font-medium text-fg">{t(STAGES[Math.min(stage, 3)])}</span>
            <span className="text-sm font-semibold tabular-nums text-brand">{Math.round(pct)}%</span>
          </div>
          <ProgressBar value={pct} label={t('progress.title')} className="h-2" />
        </div>
        <ol className="grid gap-3 sm:grid-cols-4">
          {STAGES.map((key, i) => {
            const done = i < stage
            const current = i === stage
            return (
              <li key={key} className={cx('flex items-center gap-2 rounded-lg border px-3 py-2 text-xs transition-colors duration-300',
                done ? 'border-ok/30 bg-ok-soft text-ok-fg' : current ? 'border-brand/40 bg-brand-soft text-brand-fg' : 'border-line text-fg-subtle')}>
                <span className={cx('flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold',
                  done ? 'bg-ok text-white' : current ? 'bg-brand-solid text-white' : 'bg-surface-3 text-fg-subtle')}>
                  {done ? <Check className="h-3 w-3" /> : current ? <Loader2 className="h-3 w-3 animate-spin" /> : i + 1}
                </span>
                <span className="font-medium">{t(key)}</span>
              </li>
            )
          })}
        </ol>
        <p className="text-xs text-fg-subtle">{t('progress.hint')}</p>
        <div>
          <button type="button" onClick={() => setShowLog((v) => !v)} className="inline-flex items-center gap-1 text-xs font-medium text-fg-muted hover:text-fg">
            {showLog ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5 rtl:rotate-180" />}{t('progress.log')}
          </button>
          {showLog && (
            <ol ref={listRef} className="mt-2 max-h-60 animate-fade-in space-y-1.5 overflow-y-auto rounded-lg bg-surface-2 p-3 text-xs" dir="ltr" aria-live="polite">
              {events.map((e, i) => (
                <li key={i} className="flex items-start gap-2">
                  {e.type === 'tool_call' ? <Network className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand" />
                    : e.type === 'tool_result' ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok" />
                      : e.type === 'error' ? <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-bad" />
                        : <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-fg-subtle" />}
                  <span className="min-w-0 flex-1 break-words text-fg-muted">{e.message}</span>
                  <span className="shrink-0 tabular-nums text-fg-subtle">{e.at.toFixed(1)}s</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </Card>
  )
}

function HistoryList({ items, currentId, onOpen, onDelete }: { items: InvestigationSummary[]; currentId: string | null; onOpen: (id: string) => void; onDelete: (id: string) => void }) {
  const { t, formatDate } = useI18n()
  const [confirm, setConfirm] = useState<string | null>(null)
  return (
    <Card>
      <CardHeader title={<span className="flex items-center gap-2"><History className="h-4 w-4 text-brand" />{t('history.title')}</span>} subtitle={t('history.subtitle')} />
      {!items.length ? <p className="px-5 py-6 text-sm text-fg-subtle">{t('history.empty')}</p> : (
        <ul className="max-h-[480px] divide-y divide-line overflow-y-auto">
          {items.map((it) => (
            <li key={it.id} className={cx('group relative transition-colors', it.id === currentId ? 'bg-brand-soft/50' : 'hover:bg-surface-2')}>
              <button type="button" onClick={() => onOpen(it.id)} className="flex w-full items-start gap-3 px-5 py-3 pe-12 text-start">
                <span className={cx('mt-1.5 h-2 w-2 shrink-0 rounded-full', it.status === 'completed' ? 'bg-ok' : it.status === 'failed' ? 'bg-bad' : 'animate-pulse bg-brand')} />
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-2 text-sm text-fg" dir="auto">{it.question}</span>
                  <span className="mt-0.5 block truncate text-xs text-fg-subtle">{it.paper_title ? `${it.paper_title} · ` : ''}{formatDate(it.created_at)}</span>
                </span>
              </button>
              {it.status !== 'running' && it.status !== 'queued' && (
                <button type="button" onClick={() => setConfirm(it.id)} title={t('history.delete')} aria-label={t('history.delete')}
                  className="absolute end-3 top-3 rounded p-1.5 text-fg-subtle opacity-0 transition-all hover:bg-bad-soft hover:text-bad-fg focus:opacity-100 group-hover:opacity-100">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      <ConfirmDialog open={confirm !== null} onCancel={() => setConfirm(null)} onConfirm={() => { if (confirm) onDelete(confirm); setConfirm(null) }}
        title={t('history.delete.title')} description={t('history.delete.text')} confirmLabel={t('common.delete')} />
    </Card>
  )
}

export function InvestigatePage() {
  const { t, lang } = useI18n()
  usePageMeta(t('investigate.title'), undefined, { noindex: true })
  const { health } = useHealth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [question, setQuestion] = useState('')
  const [requirements, setRequirements] = useState('')
  const [showReq, setShowReq] = useState(false)
  const [inv, setInv] = useState<Investigation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [recent, setRecent] = useState<InvestigationSummary[]>([])
  const [stalls, setStalls] = useState(0)
  const [papers, setPapers] = useState<PaperSummary[] | null>(null)
  const [paperId, setPaperId] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  // The paper to analyse: ?paper=<id> (from an upload or a paper page), otherwise the newest paper.
  useEffect(() => {
    api.listPapers({ status: 'processed', limit: 200 }).then((r) => {
      const list = [...r.papers].sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))
      setPapers(list)
      const wanted = searchParams.get('paper')
      setPaperId(list.find((p) => p.id === wanted)?.id ?? list[0]?.id ?? null)
    }).catch(() => setPapers([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const dbReady = health?.database.status === 'connected'
  const ai = health?.config.llm
  const aiReady = ai?.status === 'ready' || ai?.status === 'configured'
  const aiRequired = health?.config.ai_required ?? true
  const aiBlocked = health != null && aiRequired && !aiReady
  const trimmed = question.trim()
  const tooShort = trimmed.length > 0 && trimmed.length < MIN_CHARS
  const running = busy || inv?.status === 'queued' || inv?.status === 'running'
  const paper = useMemo(() => papers?.find((p) => p.id === paperId) ?? null, [papers, paperId])

  const refreshRecent = useCallback(() => {
    api.listInvestigations(30).then((r) => setRecent(r.investigations)).catch(() => { /* list is optional */ })
  }, [])

  const follow = useCallback(async (id: string) => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setBusy(true)
    setError(null)
    try {
      const final = await pollInvestigation(id, setInv, { signal: ctrl.signal, onStall: setStalls })
      if (final.status === 'failed' && final.error) setError(new ApiError(final.error.message, null, final.error.code))
      refreshRecent()
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      const e = toApiError(err)
      if (e.status === 404) { storeId(null); setInv(null) }
      setError(e)
    } finally {
      if (abortRef.current === ctrl) setBusy(false)
    }
  }, [refreshRecent])

  // Open ?open=<id> (from the overview), else resume the investigation that was open before; stop polling on unmount.
  useEffect(() => {
    const requested = searchParams.get('open')
    const id = requested && /^inv_[0-9a-f]{12}$/.test(requested) ? requested : storedId()
    if (requested) {
      storeId(requested)
      setSearchParams((p) => { p.delete('open'); return p }, { replace: true })
    }
    if (id) void follow(id)
    refreshRecent()
    return () => abortRef.current?.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [follow, refreshRecent])

  const start = async () => {
    if (trimmed.length < MIN_CHARS || running || !paperId || aiBlocked) return
    setError(null)
    setInv(null)
    setBusy(true)
    try {
      const created = await api.startInvestigation(trimmed, paperId, { requirements: requirements.trim() || undefined, language: lang })
      setInv(created)
      storeId(created.id)
      track('investigation')
      refreshRecent()
      await follow(created.id)
    } catch (err) {
      setError(toApiError(err))
      setBusy(false)
    }
  }

  const open = (id: string) => {
    storeId(id)
    setInv(null)
    void follow(id)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const removeSaved = async (id: string) => {
    try {
      await api.deleteInvestigation(id)
      if (inv?.id === id) { storeId(null); setInv(null) }
      refreshRecent()
    } catch (err) { setError(toApiError(err)) }
  }

  const reset = () => {
    abortRef.current?.abort()
    storeId(null)
    setInv(null)
    setError(null)
    setBusy(false)
  }

  const result = inv?.status === 'completed' ? inv.result : null
  const noPapers = papers !== null && papers.length === 0

  return (
    <>
      <PageHeader
        title={t('investigate.title')}
        description={t('investigate.description')}
        actions={result && inv ? (
          <>
            <Button variant="secondary" onClick={reset}><RotateCcw className="h-4 w-4" /> {t('investigate.new')}</Button>
            <Button onClick={() => downloadText(reportFilename(inv), buildMarkdownExport(inv, t))}><Download className="h-4 w-4" /> {t('investigate.export')}</Button>
          </>
        ) : undefined}
      />

      <div className="space-y-6">
        {health && !dbReady && <Alert tone="error" title={t('error.unavailable.title')}>{t('error.unavailable')}</Alert>}
        {health && dbReady && aiBlocked && <Alert tone="error" title={t('investigate.aiDown.title')}>{t('investigate.aiDown.text')}</Alert>}

        {noPapers ? (
          <Card>
            <EmptyState icon={<FileText className="h-6 w-6" />} title={t('investigate.noPapers.title')} description={t('investigate.noPapers.text')}
              action={<ButtonLink to="/upload"><Upload className="h-4 w-4" />{t('nav.upload')}</ButtonLink>} />
          </Card>
        ) : (
          <div className="grid gap-6 xl:grid-cols-3">
            <Card className="xl:col-span-2">
              <CardHeader title={t('investigate.question')} subtitle={t('investigate.question.subtitle')}
                action={ai?.model && aiReady ? <Badge tone="brand"><Sparkles className="h-3 w-3" />{ai.model}</Badge> : undefined} />
              <form className="space-y-4 p-5" onSubmit={(e) => { e.preventDefault(); void start() }}>
                {papers === null ? <div className="skeleton h-16 w-full" /> : (
                  <PaperPicker papers={papers} selected={paperId} onSelect={setPaperId} disabled={running} />
                )}
                <div>
                  <label htmlFor="question" className="sr-only">{t('investigate.question')}</label>
                  <Textarea id="question" rows={3} value={question} maxLength={MAX_CHARS} disabled={running} dir="auto"
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void start() } }}
                    placeholder={t('investigate.placeholder')} className="text-[15px]" />
                </div>
                <div className="flex flex-wrap gap-2">
                  {EXAMPLES.map((key) => (
                    <button key={key} type="button" disabled={running} onClick={() => setQuestion(t(key))}
                      className="rounded-full border border-line bg-surface px-3 py-1 text-xs text-fg-muted transition-all duration-150 hover:-translate-y-px hover:border-brand/50 hover:text-brand active:scale-95 disabled:opacity-50">
                      {t(key)}
                    </button>
                  ))}
                </div>
                {showReq && (
                  <div className="animate-fade-up rounded-lg border border-accent/30 bg-accent-soft/50 p-3">
                    <label htmlFor="requirements" className="text-xs font-medium text-accent-fg">{t('investigate.requirements.label')}</label>
                    <Textarea id="requirements" rows={3} maxLength={3000} disabled={running} value={requirements} dir="auto"
                      onChange={(e) => setRequirements(e.target.value)} placeholder={t('investigate.requirements.placeholder')} className="mt-1.5" />
                  </div>
                )}
                <div className="flex flex-col gap-3 border-t border-line pt-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex flex-wrap items-center gap-4 text-xs text-fg-subtle">
                    <button type="button" onClick={() => setShowReq((v) => !v)} className="font-medium text-brand hover:text-brand-hover">
                      {showReq ? t('investigate.requirements.hide') : t('investigate.requirements.add')}{requirements.trim() ? ` (${t('investigate.requirements.added')})` : ''}
                    </button>
                    <span className={cx('tabular-nums', tooShort && 'text-warn-fg')}>
                      {tooShort ? t('investigate.tooShort', { min: MIN_CHARS }) : `${trimmed.length}/${MAX_CHARS}`} · {t('investigate.shortcut')}
                    </span>
                  </div>
                  <Button type="submit" size="lg" loading={running}
                    disabled={!paperId || trimmed.length < MIN_CHARS || (health != null && !dbReady) || aiBlocked}>
                    {!running && <Search className="h-4 w-4" />}
                    {running ? t('investigate.running') : t('investigate.submit')}
                  </Button>
                </div>
              </form>
            </Card>
            <HistoryList items={recent} currentId={inv?.id ?? null} onOpen={open} onDelete={(id) => void removeSaved(id)} />
          </div>
        )}

        {error && (
          <Alert tone="error" title={error.code === 'busy' ? t('investigate.busy.title') : t('investigate.failed.title')}
            action={trimmed.length >= MIN_CHARS && paperId ? <Button variant="secondary" size="sm" onClick={() => void start()} disabled={running}><RotateCcw className="h-4 w-4" /> {t('common.retry')}</Button> : undefined}>
            {errorText(t, error)}
          </Alert>
        )}

        {running && stalls > 0 && <Alert tone="warning" title={t('investigate.stalled.title')}>{t('investigate.stalled.text')}</Alert>}
        {running && <ProgressPanel inv={inv} paperTitle={inv?.paper_title ?? paper?.display_title ?? null} />}

        {result && inv && (
          <div className="space-y-4">
            <div className="flex animate-fade-up flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-line bg-surface px-5 py-3 text-sm shadow-card">
              <span className="min-w-0 flex-1 font-medium text-fg" dir="auto">{inv.question}</span>
              <Badge tone="ok"><CheckCircle2 className="h-3.5 w-3.5" /> {t('investigate.completed')}</Badge>
              {inv.paper_title && <Badge title={inv.paper_title}><FileText className="h-3 w-3" /><span className="max-w-[16rem] truncate">{inv.paper_title}</span></Badge>}
              <Badge tone={result.mode === 'llm' ? 'brand' : 'neutral'}>
                {result.mode === 'llm' ? <><Sparkles className="h-3 w-3" />{inv.model ?? t('investigate.ai')}</> : t('result.report.offline')}
              </Badge>
              <ConfidenceBadge level={result.confidence.level} />
              <span className="text-xs tabular-nums text-fg-subtle">{inv.duration_seconds?.toFixed(1)} s</span>
            </div>
            {inv.requirements && (
              <div className="rounded-lg border border-accent/30 bg-accent-soft/50 px-4 py-2 text-xs text-accent-fg" dir="auto">
                <span className="font-semibold">[R] {t('investigate.requirements.yours')}</span> {inv.requirements}
              </div>
            )}
            <InvestigationResultView result={result} model={inv.model} />
          </div>
        )}

        {!running && !result && !error && !noPapers && (
          <Card>
            <EmptyState icon={<FlaskConical className="h-6 w-6" />} title={t('investigate.empty.title')} description={t('investigate.empty.text')} />
          </Card>
        )}
      </div>
    </>
  )
}
