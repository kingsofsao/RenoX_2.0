import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CheckCircle2, Clock, Cpu, Download, FlaskConical, History, Loader2, Network, RotateCcw, Search, Sparkles, Upload, XCircle,
} from 'lucide-react'
import { ConfidenceBadge, InvestigationResultView } from '../components/InvestigationResult'
import { Alert, Button, Card, CardHeader, EmptyState, PageHeader, cx } from '../components/ui'
import { useHealth } from '../hooks/HealthContext'
import { ApiError, api, getActiveProject, pollInvestigation, toApiError } from '../services/api'
import { formatDate } from '../services/format'
import { buildMarkdownExport, downloadText, reportFilename } from '../services/report'
import type { Investigation, InvestigationSummary } from '../types/api'

const MIN_CHARS = 10
const MAX_CHARS = 1000
// Per project: reopening the page resumes that project's last investigation, never another project's.
const storageKey = () => `researchmind.investigation.current.${getActiveProject()}`
const EXAMPLES = [
  'Do graph attention models generalize to unseen proteins in drug-target prediction?',
  'How do protein language models compare with graph neural networks in cold-start settings?',
  'Which limitations recur across papers on binding affinity prediction?',
]

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
    const t = window.setInterval(() => setNow(Date.now()), 500)
    return () => window.clearInterval(t)
  }, [running])
  if (!startedAt) return 0
  return Math.max(0, (now - new Date(startedAt).getTime()) / 1000)
}

function ProgressPanel({ inv }: { inv: Investigation | null }) {
  const running = !inv || inv.status === 'queued' || inv.status === 'running'
  const elapsed = useElapsed(running, inv?.started_at ?? inv?.created_at ?? null)
  const events = inv?.progress ?? []
  const toolCalls = events.filter((e) => e.type === 'tool_call').length
  const listRef = useRef<HTMLOListElement>(null)
  useEffect(() => { listRef.current?.scrollTo({ top: listRef.current.scrollHeight }) }, [events.length])

  return (
    <Card>
      <CardHeader
        title="Investigating…"
        subtitle={inv?.mode === 'llm'
          ? `${inv.provider ?? 'LLM'} / ${inv.model ?? 'model'} is reasoning over evidence retrieved through MCP graph tools${inv.provider === 'ollama' ? ' (local models can take a few minutes)' : ''}`
          : 'Running the offline evidence plan over MCP graph tools'}
        action={<span className="inline-flex items-center gap-1.5 text-xs tabular-nums text-slate-500"><Clock className="h-3.5 w-3.5" />{elapsed.toFixed(0)} s · {toolCalls} tool calls</span>}
      />
      <div className="p-5">
        <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full w-1/3 animate-[progress_1.6s_ease-in-out_infinite] rounded-full bg-indigo-500" />
        </div>
        {events.length === 0 ? (
          <p className="inline-flex items-center gap-2 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin" /> Starting the investigation…</p>
        ) : (
          <ol ref={listRef} className="max-h-72 space-y-1.5 overflow-y-auto pr-1 text-sm" aria-live="polite">
            {events.map((e, i) => {
              const last = i === events.length - 1
              return (
                <li key={i} className="flex items-start gap-2">
                  {e.type === 'tool_call' ? <Network className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                    : e.type === 'tool_result' ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                      : e.type === 'error' ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
                        : last ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-slate-400" />
                          : <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />}
                  <span className={cx('min-w-0 flex-1 break-words', e.type === 'thought' ? 'italic text-slate-500' : 'text-slate-700')}>{e.message}</span>
                  <span className="shrink-0 text-xs tabular-nums text-slate-400">{e.at.toFixed(1)}s</span>
                </li>
              )
            })}
          </ol>
        )}
      </div>
    </Card>
  )
}

function RecentList({ items, currentId, onOpen, onDelete }: { items: InvestigationSummary[]; currentId: string | null; onOpen: (id: string) => void; onDelete: (id: string) => void }) {
  if (!items.length) return null
  return (
    <Card>
      <CardHeader title="Saved investigations" subtitle="Saved in this project; reopen any time" />
      <ul className="divide-y divide-slate-100">
        {items.map((it) => (
          <li key={it.id}>
            <div className="group flex items-start">
            <button type="button" onClick={() => onOpen(it.id)}
              className={cx('flex w-full items-start gap-3 px-5 py-2.5 text-left hover:bg-slate-50', it.id === currentId && 'bg-indigo-50/50')}>
              <History className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 text-sm text-slate-800">{it.question}</span>
                <span className="text-xs text-slate-500">{formatDate(it.created_at)} · {it.status}{it.mode ? ` · ${it.mode}` : ''}</span>
              </span>
            </button>
            {it.status !== 'running' && it.status !== 'queued' && (
              <button type="button" onClick={() => onDelete(it.id)} title="Delete this saved investigation"
                className="mr-3 mt-2.5 rounded p-1 text-xs text-slate-300 opacity-0 hover:bg-red-50 hover:text-red-600 group-hover:opacity-100">✕</button>
            )}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function InvestigatePage() {
  const { health } = useHealth()
  const [question, setQuestion] = useState('')
  const [useLlm, setUseLlm] = useState(true)
  const [requirements, setRequirements] = useState('')
  const [showReq, setShowReq] = useState(false)
  const [inv, setInv] = useState<Investigation | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [recent, setRecent] = useState<InvestigationSummary[]>([])
  const [stalls, setStalls] = useState(0)
  const abortRef = useRef<AbortController | null>(null)

  const dbStatus = health?.database.status
  const dbReady = dbStatus === 'connected'
  const llm = health?.config.llm
  const llmConfigured = health?.config.llm_configured ?? false
  // Anthropic is not contacted by the status check ("configured"); Ollama must be reachable with the model installed.
  const llmReady = llm?.status === 'ready' || llm?.status === 'configured'
  const llmLabel = llm && llm.provider !== 'none' ? `${llm.provider} / ${llm.model ?? 'no model set'}` : null
  const trimmed = question.trim()
  const tooShort = trimmed.length > 0 && trimmed.length < MIN_CHARS
  const running = busy || inv?.status === 'queued' || inv?.status === 'running'

  const refreshRecent = useCallback(() => {
    api.listInvestigations(20).then((r) => setRecent(r.investigations)).catch(() => { /* list is optional */ })
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

  // Resume the investigation that was open before navigating away; stop polling on unmount.
  useEffect(() => {
    const id = storedId()
    if (id) {
      void follow(id)
    }
    refreshRecent()
    return () => abortRef.current?.abort()
  }, [follow, refreshRecent])

  const start = async () => {
    if (trimmed.length < MIN_CHARS || running) return
    setError(null)
    setInv(null)
    setBusy(true)
    try {
      const created = await api.startInvestigation(trimmed, useLlm && llmReady, requirements.trim() || undefined)
      setInv(created)
      storeId(created.id)
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
  }

  const removeSaved = async (id: string) => {
    if (!window.confirm('Delete this saved investigation?')) return
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

  return (
    <>
      <PageHeader
        title="Investigate"
        description="Ask a research question. The agent searches your knowledge graph through MCP tools, compares evidence across papers and reports candidate gaps — every statement cited to a paper and page."
        actions={result && inv ? (
          <>
            <Button variant="secondary" onClick={reset}><RotateCcw className="h-4 w-4" /> New investigation</Button>
            <Button onClick={() => downloadText(reportFilename(inv), buildMarkdownExport(inv))}><Download className="h-4 w-4" /> Export Markdown</Button>
          </>
        ) : undefined}
      />

      <div className="space-y-6">
        {health && !dbReady && (
          <Alert tone="error" title="Knowledge graph not available">
            {dbStatus === 'not_configured'
              ? 'FALKORDB_URL is not set in backend/.env, so there is no graph to investigate.'
              : 'The API cannot reach FalkorDB right now. Investigations will start once the database is connected.'}
          </Alert>
        )}
        {health && dbReady && !llmConfigured && (
          <Alert tone="info" title="No LLM configured — offline investigation mode">
            Investigations run a fixed evidence plan over the same MCP graph tools and produce an extractive, fully cited report.
            For LLM reasoning set <code>LLM_PROVIDER=ollama</code> and <code>LLM_MODEL</code> in <code>backend/.env</code> (see README) and restart the API.
          </Alert>
        )}
        {health && dbReady && llmConfigured && !llmReady && llm && (
          <Alert tone="warning" title={`LLM unavailable (${llmLabel}) — offline reports only`}>
            {llm.message} Investigations still run in offline mode.
          </Alert>
        )}

        <div className="grid gap-6 xl:grid-cols-3">
          <Card className="xl:col-span-2">
            <CardHeader title="Research question" subtitle="Specific, answerable questions work best. The agent only uses your ingested papers." />
            <form className="space-y-3 p-5" onSubmit={(e) => { e.preventDefault(); void start() }}>
              <label htmlFor="question" className="sr-only">Research question</label>
              <textarea
                id="question"
                rows={3}
                value={question}
                maxLength={MAX_CHARS}
                disabled={running}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); void start() } }}
                placeholder="e.g. Do graph attention models generalize to unseen proteins in drug-target prediction?"
                className="w-full resize-y rounded-lg border border-slate-300 p-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:bg-slate-50 disabled:text-slate-500"
              />
              {showReq && (
                <div className="rounded-lg border border-violet-200 bg-violet-50/40 p-3">
                  <label htmlFor="requirements" className="text-xs font-medium text-violet-900">
                    Your project requirements (optional) — compared with the papers, cited as [R], never treated as published evidence
                  </label>
                  <textarea id="requirements" rows={3} maxLength={3000} disabled={running} value={requirements}
                    onChange={(e) => setRequirements(e.target.value)}
                    placeholder="e.g. CK KidBrace: an infant wearable that monitors heart rate, temperature and SpO2 and alerts parents through a mobile app."
                    className="mt-1.5 w-full resize-y rounded-md border border-violet-200 bg-white p-2 text-sm text-slate-900 focus:border-violet-500 focus:outline-none focus:ring-2 focus:ring-violet-500/20" />
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((ex) => (
                  <button key={ex} type="button" disabled={running} onClick={() => setQuestion(ex)}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-50">
                    {ex}
                  </button>
                ))}
              </div>
              <div className="flex flex-col gap-3 border-t border-slate-100 pt-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500">
                  <label className={cx('inline-flex items-center gap-2', !llmReady && 'opacity-60')} title={llm?.message}>
                    <input type="checkbox" className="h-4 w-4 rounded border-slate-300 text-indigo-600" checked={useLlm && llmReady}
                      disabled={!llmReady || running} onChange={(e) => setUseLlm(e.target.checked)} />
                    <Cpu className="h-3.5 w-3.5" /> Use LLM reasoning
                    {llmLabel ? (
                      <span className={cx('rounded px-1.5 py-0.5 text-[10px] font-medium', llmReady ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800')}>
                        {llmLabel} · {llm?.status.replace('_', ' ')}
                      </span>
                    ) : ' (not configured)'}
                  </label>
                  <button type="button" onClick={() => setShowReq((v) => !v)} className="font-medium text-indigo-600 hover:text-indigo-500">
                    {showReq ? 'Hide' : 'Add'} project requirements{requirements.trim() ? ' ✓' : ''}
                  </button>
                  <span className={cx('tabular-nums', tooShort && 'text-amber-600')}>
                    {tooShort ? `At least ${MIN_CHARS} characters` : `${trimmed.length}/${MAX_CHARS}`} · Ctrl+Enter to run
                  </span>
                </div>
                <Button type="submit" disabled={running || trimmed.length < MIN_CHARS || (health != null && !dbReady)}>
                  {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  {running ? 'Investigating…' : 'Investigate'}
                </Button>
              </div>
            </form>
          </Card>
          <RecentList items={recent} currentId={inv?.id ?? null} onOpen={open} onDelete={(id) => void removeSaved(id)} />
        </div>

        {error && (
          <Alert tone="error" title={error.code === 'no_papers' ? 'No papers to investigate' : error.code === 'busy' ? 'Investigations busy' : 'Investigation failed'}
            action={error.code === 'no_papers'
              ? <Link to="/upload"><Button variant="secondary"><Upload className="h-4 w-4" /> Upload PDFs</Button></Link>
              : trimmed.length >= MIN_CHARS ? <Button variant="secondary" onClick={() => void start()} disabled={running}><RotateCcw className="h-4 w-4" /> Retry</Button> : undefined}>
            {error.message}
          </Alert>
        )}

        {running && stalls > 0 && (
          <Alert tone="warning" title="The backend is busy — still waiting">
            The API has not answered {stalls} status check{stalls === 1 ? '' : 's'} in a row. This is normal while a local model runs on the CPU;
            the investigation continues in the background.
          </Alert>
        )}
        {running && <ProgressPanel inv={inv} />}

        {result && inv && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm shadow-sm">
              <span className="min-w-0 flex-1 font-medium text-slate-900">{inv.question}</span>
              <span className="inline-flex items-center gap-1 text-xs text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" /> Completed</span>
              <span className={cx('rounded-full px-2 py-0.5 text-xs', result.mode === 'llm' ? 'bg-indigo-50 text-indigo-700' : 'bg-slate-100 text-slate-600')}>
                {result.mode === 'llm' ? `LLM report · ${inv.provider} / ${inv.model}` : 'Offline extractive report (no LLM)'}
              </span>
              <ConfidenceBadge level={result.confidence.level} />
              <span className="text-xs tabular-nums text-slate-500">{inv.duration_seconds?.toFixed(1)} s · {result.steps.length} tool calls</span>
            </div>
            {inv.requirements && (
              <div className="rounded-lg border border-violet-200 bg-violet-50/40 px-4 py-2 text-xs text-violet-900">
                <span className="font-semibold">[R] Your requirements:</span> {inv.requirements}
              </div>
            )}
            <InvestigationResultView result={result} provider={inv.provider} model={inv.model} />
          </div>
        )}

        {!running && !result && !error && (
          <Card>
            <EmptyState
              icon={<FlaskConical className="h-6 w-6" />}
              title="Ask your first research question"
              description="Findings, cross-paper comparisons, candidate research gaps and page-level citations will appear here."
            />
          </Card>
        )}
      </div>
    </>
  )
}
