// Rendering of a completed investigation: summary, findings, comparisons, gaps, limitations,
// confidence and expandable page-level sources. Every [n] chip opens the matching source.
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, BookOpen, ChevronDown, ChevronRight, ExternalLink, FileText, GitCompare, Lightbulb, ListChecks,
  Network, Scale, ShieldQuestion,
} from 'lucide-react'
import { api } from '../services/api'
import { plain, splitCitations } from '../services/report'
import type { InvestigationResultBody, InvestigationSource } from '../types/api'
import { Alert, Card, CardHeader, cx } from './ui'

// ------------------------------------------------------------------ citations

const CiteContext = createContext<(n: number) => void>(() => {})

export function CitationChip({ n }: { n: number }) {
  const focus = useContext(CiteContext)
  return (
    <button
      type="button"
      onClick={() => focus(n)}
      title={`Show source ${n}`}
      className="mx-0.5 inline-flex min-w-[1.5rem] items-center justify-center rounded bg-indigo-50 px-1 text-[11px] font-semibold tabular-nums text-indigo-700 ring-1 ring-inset ring-indigo-200 hover:bg-indigo-100"
    >
      {n}
    </button>
  )
}

function Cites({ numbers }: { numbers: number[] }) {
  return <>{numbers.map((n) => <CitationChip key={n} n={n} />)}</>
}

/** Text with inline [n] / [unverified] markers rendered as chips. */
export function CitedText({ text }: { text: string }) {
  return (
    <>
      {splitCitations(plain(text)).map((p, i) =>
        p.kind === 'text' ? <span key={i}>{p.text}</span>
          : p.kind === 'flag' ? (
            <span key={i} title="Flagged by ResearchMind's verification: not supported by the cited sources" className="mx-0.5 rounded bg-red-100 px-1 text-[11px] font-semibold text-red-700">{p.text}</span>
          ) : (
            <span key={i} className="whitespace-nowrap">
              {p.numbers.map((n) => <CitationChip key={n} n={n} />)}
              {p.requirement && (
                <span title="Your own project requirement - not a published finding" className="mx-0.5 rounded bg-violet-100 px-1 text-[11px] font-semibold text-violet-700">R</span>
              )}
              {p.unverified && (
                <span title="This citation did not match any stored evidence" className="mx-0.5 rounded bg-amber-100 px-1 text-[11px] font-semibold text-amber-800">unverified</span>
              )}
            </span>
          ),
      )}
    </>
  )
}

/** Minimal Markdown rendering for reports: headings, bullets, quotes and paragraphs, with citation chips. */
export function MarkdownReport({ markdown }: { markdown: string }) {
  const body = markdown.replace(/^\s*#\s+[^\n]*\n+/, '').replace(/\n## References\n[\s\S]*$/, '')
  const blocks: ReactNode[] = []
  let list: string[] = []
  const flush = () => {
    if (list.length) {
      blocks.push(<ul key={`l${blocks.length}`} className="ml-5 list-disc space-y-1">{list.map((li, i) => <li key={i}><CitedText text={li} /></li>)}</ul>)
      list = []
    }
  }
  body.split('\n').forEach((raw, i) => {
    const line = raw.trimEnd()
    if (/^\s*[-*]\s+/.test(line)) { list.push(line.replace(/^\s*[-*]\s+/, '')); return }
    flush()
    if (!line.trim()) return
    const h = line.match(/^(#{2,4})\s+(.*)$/)
    if (h) {
      blocks.push(<h3 key={i} className={cx('font-semibold text-slate-900', h[1].length === 2 ? 'mt-5 text-base' : 'mt-3 text-sm')}>{plain(h[2])}</h3>)
    } else if (line.startsWith('>')) {
      blocks.push(<p key={i} className="rounded-md bg-indigo-50 px-3 py-2 text-xs text-indigo-900"><CitedText text={line.replace(/^>\s?/, '')} /></p>)
    } else {
      blocks.push(<p key={i} className={cx(/^hypothesis:/i.test(line) && 'border-l-2 border-violet-300 pl-3 italic')}><CitedText text={line} /></p>)
    }
  })
  flush()
  return <div className="space-y-2 text-sm leading-relaxed text-slate-700">{blocks}</div>
}

function PaperRef({ id, title, page }: { id: string; title: string | null; page: number | null }) {
  return (
    <span className="text-xs text-slate-500">
      <Link to={`/papers/${id}`} className="font-medium text-slate-600 hover:text-indigo-600 hover:underline">{title ?? id}</Link>
      {page ? <>, p. {page}</> : null}
    </span>
  )
}

function Section({ icon, title, subtitle, count, children, action }: {
  icon: ReactNode; title: string; subtitle?: string; count?: number; children: ReactNode; action?: ReactNode
}) {
  return (
    <Card>
      <CardHeader
        title={`${title}${count != null ? ` (${count})` : ''}`}
        subtitle={subtitle}
        action={<div className="flex items-center gap-2">{action}<span className="rounded-lg bg-indigo-50 p-1.5 text-indigo-600">{icon}</span></div>}
      />
      <div className="p-5">{children}</div>
    </Card>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm italic text-slate-400">{children}</p>
}

// ------------------------------------------------------------------ sections

const LEVEL_STYLE = {
  high: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  moderate: 'bg-amber-50 text-amber-800 ring-amber-600/20',
  low: 'bg-red-50 text-red-700 ring-red-600/20',
} as const

export function ConfidenceBadge({ level }: { level: 'low' | 'moderate' | 'high' }) {
  return <span className={cx('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium capitalize ring-1 ring-inset', LEVEL_STYLE[level])}>{level} confidence</span>
}

function Findings({ r }: { r: InvestigationResultBody }) {
  const byPaper = useMemo(() => {
    const m = new Map<string, typeof r.findings>()
    r.findings.forEach((f) => m.set(f.paper_id, [...(m.get(f.paper_id) ?? []), f]))
    return [...m.entries()]
  }, [r])
  return (
    <Section icon={<ListChecks className="h-4 w-4" />} title="Evidence-backed findings" count={r.findings.length}
      subtitle="Claims and findings retrieved from the graph, grouped by paper, most relevant first">
      {!r.findings.length ? <Empty>No findings were retrieved for this question.</Empty> : (
        <div className="space-y-5">
          {byPaper.map(([pid, items]) => (
            <div key={pid}>
              <Link to={`/papers/${pid}`} className="text-sm font-semibold text-slate-900 hover:text-indigo-600">{items[0].paper_title ?? pid}</Link>
              <ul className="mt-2 space-y-2">
                {items.map((f, i) => (
                  <li key={i} className="flex gap-2 text-sm text-slate-700">
                    <span className={cx('mt-0.5 h-fit shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase',
                      f.type === 'claim' ? 'bg-sky-50 text-sky-700' : 'bg-emerald-50 text-emerald-700')}>{f.type}</span>
                    <span>
                      {f.text}<Cites numbers={f.citations} />
                      {f.page ? <span className="ml-1 text-xs text-slate-400">p. {f.page}</span> : null}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Section>
  )
}

function Comparisons({ r }: { r: InvestigationResultBody }) {
  const conflicts = r.comparisons.filter((c) => c.kind === 'contradiction')
  const related = r.comparisons.filter((c) => c.kind === 'related')
  return (
    <Section icon={<GitCompare className="h-4 w-4" />} title="Cross-paper comparisons"
      subtitle="Conflicting and closely related statements, and the methods and datasets papers share">
      <div className="space-y-6">
        {!r.comparisons.length && <Empty>No cross-paper conflicts or closely related statements were detected for this question.</Empty>}
        {[['Conflicting results', conflicts, 'border-red-200 bg-red-50/40'], ['Closely related statements', related, 'border-slate-200 bg-slate-50/60']].map(
          ([label, items, style]) => (items as typeof conflicts).length > 0 && (
            <div key={label as string}>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{label as string}</p>
              <div className="space-y-3">
                {(items as typeof conflicts).map((c, i) => (
                  <div key={i} className={cx('rounded-lg border p-3', style as string)}>
                    <div className="grid gap-3 md:grid-cols-[1fr_auto_1fr]">
                      {[c.a, c.b].map((side, j) => (
                        <div key={j} className={cx(j === 1 && 'md:order-3')}>
                          <p className="text-sm text-slate-800">“{side.text}”<CitationChip n={side.citation} /></p>
                          <div className="mt-1"><PaperRef id={side.paper_id} title={side.paper_title} page={side.page} /></div>
                        </div>
                      ))}
                      <div className="flex items-center justify-center md:order-2">
                        <span className={cx('rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase',
                          c.kind === 'contradiction' ? 'bg-red-100 text-red-700' : 'bg-slate-200 text-slate-600')}>
                          {c.kind === 'contradiction' ? 'vs' : '≈'} {c.score.toFixed(2)}
                        </span>
                      </div>
                    </div>
                    <p className="mt-2 text-xs text-slate-500">{c.note}</p>
                  </div>
                ))}
              </div>
            </div>
          ),
        )}
        {r.method_comparison.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Methods and datasets across papers</p>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr><th className="px-3 py-2 font-medium">Entity</th><th className="px-3 py-2 font-medium">Type</th><th className="px-3 py-2 font-medium">Used by</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {r.method_comparison.map((m) => (
                    <tr key={`${m.type}:${m.entity}`}>
                      <td className="px-3 py-2 font-medium text-slate-900">{m.entity}</td>
                      <td className="px-3 py-2 capitalize text-slate-500">{m.type}</td>
                      <td className="px-3 py-2 text-slate-700">
                        {m.papers.map((p, i) => (
                          <span key={p.paper_id}>{i > 0 && <span className="text-slate-300"> · </span>}
                            <Link to={`/papers/${p.paper_id}`} className="hover:text-indigo-600">{p.paper_title ?? p.paper_id}</Link><CitationChip n={p.citation} />
                          </span>
                        ))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Section>
  )
}

function Gaps({ r }: { r: InvestigationResultBody }) {
  const [open, setOpen] = useState<Set<string>>(new Set())
  const toggle = (id: string) => setOpen((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })
  return (
    <Section icon={<Lightbulb className="h-4 w-4" />} title="Candidate research gaps" count={r.gaps.length}
      subtitle="Hypotheses supported by evidence in your papers — verify against the wider literature before treating any as novel">
      {!r.gaps.length ? <Empty>No candidate gaps with verifiable evidence were found.</Empty> : (
        <div className="space-y-3">
          {r.gaps.map((g) => (
            <div key={g.id} className="rounded-lg border border-slate-200 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-violet-50 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-violet-700">{g.id} · candidate</span>
                <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">{g.support_papers} papers</span>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium uppercase text-slate-600">{g.type.replace(/_/g, ' ')}</span>
                {g.score != null && <span className="text-xs tabular-nums text-slate-400">score {g.score}</span>}
              </div>
              <p className="mt-2 font-medium text-slate-900">{g.title}</p>
              <p className="mt-1 text-sm text-slate-600">{g.rationale}<Cites numbers={g.citations} /></p>
              <button type="button" onClick={() => toggle(g.id)} className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-500">
                {open.has(g.id) ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                Supporting evidence ({g.evidence.length})
              </button>
              {open.has(g.id) && (
                <ul className="mt-2 space-y-2 border-l-2 border-violet-100 pl-3">
                  {g.evidence.map((e, i) => (
                    <li key={i} className="text-sm">
                      <p className="text-slate-700">“{e.quote}”<CitationChip n={e.citation} /></p>
                      <PaperRef id={e.paper_id} title={e.paper_title} page={e.page} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          <p className="flex items-start gap-1.5 text-xs text-slate-500"><ShieldQuestion className="mt-0.5 h-3.5 w-3.5 shrink-0" />{r.gaps[0]?.note}</p>
        </div>
      )}
    </Section>
  )
}

function Limitations({ r }: { r: InvestigationResultBody }) {
  return (
    <Section icon={<AlertTriangle className="h-4 w-4" />} title="Limitations of the evidence" count={r.limitations.length}
      subtitle="Limitations and future work stated by the authors of the relevant papers">
      {!r.limitations.length ? <Empty>No limitations were extracted for the relevant papers.</Empty> : (
        <ul className="space-y-2">
          {r.limitations.map((l, i) => (
            <li key={i} className="text-sm text-slate-700">
              <span className={cx('mr-2 rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase',
                l.kind === 'future_work' ? 'bg-sky-50 text-sky-700' : 'bg-amber-50 text-amber-800')}>{l.kind === 'future_work' ? 'future work' : 'limitation'}</span>
              {l.text}<Cites numbers={l.citations} />
              <div className="mt-0.5"><PaperRef id={l.paper_id} title={l.paper_title} page={l.page} /></div>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}

function ConfidencePanel({ r }: { r: InvestigationResultBody }) {
  const c = r.confidence
  return (
    <Section icon={<Scale className="h-4 w-4" />} title="Confidence and uncertainty" action={<ConfidenceBadge level={c.level} />}>
      <ul className="space-y-1.5 text-sm text-slate-700">
        {c.reasons.map((x, i) => <li key={`r${i}`} className="flex gap-2"><span className="text-emerald-600">•</span>{x}</li>)}
        {c.uncertainties.map((x, i) => <li key={`u${i}`} className="flex gap-2"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />{x}</li>)}
      </ul>
      {c.narrative && (
        <div className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Agent's assessment</p>
          <CitedText text={c.narrative} />
        </div>
      )}
    </Section>
  )
}

function SourceItem({ s, open, onToggle }: { s: InvestigationSource; open: boolean; onToggle: () => void }) {
  return (
    <li id={`source-${s.n}`} className={cx('scroll-mt-24 rounded-lg border transition-colors', open ? 'border-indigo-200 bg-indigo-50/30' : 'border-slate-200')}>
      <button type="button" onClick={onToggle} className="flex w-full items-start gap-3 px-3 py-2.5 text-left" aria-expanded={open}>
        <span className="mt-0.5 inline-flex h-5 min-w-[1.5rem] items-center justify-center rounded bg-indigo-600 px-1 text-[11px] font-semibold text-white">{s.n}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-slate-900">{s.paper_title ?? s.paper_id}</span>
          <span className="text-xs text-slate-500">{s.page ? `Page ${s.page}` : 'Page unknown'}{s.section ? ` · ${s.section}` : ''}{s.year ? ` · ${s.year}` : ''}{s.cited_in_report ? ' · cited in report' : ''}</span>
        </span>
        {open ? <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-slate-400" /> : <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-slate-400" />}
      </button>
      {open && (
        <div className="space-y-2 px-3 pb-3 pl-12">
          <blockquote className="border-l-2 border-indigo-200 pl-3 text-sm text-slate-700">“{s.quote}”</blockquote>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <Link to={`/papers/${s.paper_id}`} className="inline-flex items-center gap-1 font-medium text-indigo-600 hover:text-indigo-500"><BookOpen className="h-3.5 w-3.5" /> Paper details</Link>
            <a href={`${api.paperFileUrl(s.paper_id)}${s.page ? `#page=${s.page}` : ''}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-indigo-600 hover:text-indigo-500">
              <ExternalLink className="h-3.5 w-3.5" /> Open PDF{s.page ? ` at page ${s.page}` : ''}
            </a>
            <code className="text-slate-400" title="Evidence chunk id in the knowledge graph">{s.chunk_id}</code>
          </div>
        </div>
      )}
    </li>
  )
}

function EmptyStateNote() {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center">
      <div className="mb-3 rounded-full bg-amber-50 p-3 text-amber-600"><ShieldQuestion className="h-6 w-6" /></div>
      <p className="font-medium text-slate-900">No answer without evidence</p>
      <p className="mt-1 max-w-md text-sm text-slate-500">
        ResearchMind only answers from your ingested papers. Nothing in them was relevant enough to cite, so no findings, comparisons or gaps are shown.
        Upload papers on this topic or rephrase the question.
      </p>
    </div>
  )
}

// ------------------------------------------------------------------ main view

export function InvestigationResultView({ result: r, provider, model }: { result: InvestigationResultBody; provider?: string | null; model?: string | null }) {
  const [openSources, setOpenSources] = useState<Set<number>>(new Set())
  const [showAll, setShowAll] = useState(false)
  const [showReport, setShowReport] = useState(r.mode === 'llm')

  const focus = useCallback((n: number) => {
    setShowAll(true)
    setOpenSources((s) => new Set(s).add(n))
    requestAnimationFrame(() => document.getElementById(`source-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  }, [])
  const toggle = (n: number) => setOpenSources((s) => { const x = new Set(s); if (x.has(n)) x.delete(n); else x.add(n); return x })
  const visibleSources = showAll ? r.sources : r.sources.slice(0, 8)

  if (!r.evidence_found) {
    return (
      <div className="space-y-6">
        <Alert tone="warning" title="Your papers don't cover this question">
          {r.summary}
        </Alert>
        <Card>
          <EmptyStateNote />
        </Card>
      </div>
    )
  }

  return (
    <CiteContext.Provider value={focus}>
      <div className="space-y-6">
        {r.warnings.length > 0 && (
          <Alert tone="warning" title="Check these notes">
            <ul className="list-disc space-y-0.5 pl-4">{r.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
          </Alert>
        )}

        <Card className="border-indigo-100">
          <CardHeader title="Summary" subtitle={`Answer drawn from ${r.sources.length} verified passages in ${r.papers.length} papers`}
            action={<ConfidenceBadge level={r.confidence.level} />} />
          <div className="space-y-2 p-5 text-[15px] leading-relaxed text-slate-800">
            {r.summary.split('\n').filter((l) => l.trim()).map((line, i) => (
              <p key={i} className={cx(line.trim().startsWith('- ') && 'pl-3')}><CitedText text={line.replace(/^\s*-\s+/, '• ')} /></p>
            ))}
          </div>
        </Card>

        <div className="grid gap-6 xl:grid-cols-3">
          <div className="space-y-6 xl:col-span-2">
            <Findings r={r} />
            <Comparisons r={r} />
            <Gaps r={r} />
            {(r.inferences.length > 0 || r.open_questions.length > 0) && (
              <Section icon={<ShieldQuestion className="h-4 w-4" />} title="Model inferences and open questions"
                subtitle="Inferences are generated by the model, not stated in the papers. Open questions are what the evidence does not answer.">
                <div className="space-y-4 text-sm">
                  {r.inferences.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-violet-700">Model inferences (hypotheses)</p>
                      <ul className="space-y-1.5">{r.inferences.map((x, i) => <li key={i} className="border-l-2 border-violet-300 pl-3 italic text-slate-700"><CitedText text={x.text} /></li>)}</ul>
                    </div>
                  )}
                  {r.open_questions.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-amber-700">Not answered by the evidence</p>
                      <ul className="list-disc space-y-1 pl-5 text-slate-700">{r.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
                    </div>
                  )}
                </div>
              </Section>
            )}
            <Limitations r={r} />
            <ConfidencePanel r={r} />
            <Card>
              <button type="button" onClick={() => setShowReport((v) => !v)} className="flex w-full items-center justify-between px-5 py-4 text-left">
                <span className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <FileText className="h-4 w-4 text-indigo-600" />
                  {r.mode === 'llm' ? `LLM analysis (${provider ?? 'LLM'} / ${model ?? 'model'})` : 'Offline extractive report'}
                </span>
                {showReport ? <ChevronDown className="h-4 w-4 text-slate-400" /> : <ChevronRight className="h-4 w-4 text-slate-400" />}
              </button>
              {showReport && (
                <div className="max-h-[75vh] overflow-auto border-t border-slate-100 p-5"><MarkdownReport markdown={r.report_markdown} /></div>
              )}
            </Card>
            <Card>
              <CardHeader title="Investigation trace" subtitle="MCP tool calls the agent made over the graph" />
              <ol className="space-y-1.5 p-4 text-xs">
                {r.steps.map((st, i) => (
                  <li key={i} className="flex gap-2">
                    <Network className={cx('mt-0.5 h-3.5 w-3.5 shrink-0', st.ok ? 'text-indigo-500' : 'text-red-500')} />
                    <span className="min-w-0">
                      <code className="font-semibold text-slate-800">{st.tool}</code>
                      {st.source === 'coverage' && <span className="ml-1 rounded bg-slate-100 px-1 text-[10px] text-slate-500">coverage</span>}
                      <span className={cx('block', st.ok ? 'text-slate-500' : 'text-red-600')}>{st.summary}</span>
                    </span>
                  </li>
                ))}
              </ol>
            </Card>
          </div>

          <div>
            <Card className="xl:sticky xl:top-6">
              <CardHeader title={`Sources (${r.sources.length})`} subtitle="Page-level evidence verified against the knowledge graph" />
              <div className="max-h-[70vh] overflow-y-auto p-3">
                {!r.sources.length ? <Empty>No sources.</Empty> : (
                  <ul className="space-y-2">
                    {visibleSources.map((s) => <SourceItem key={s.n} s={s} open={openSources.has(s.n)} onToggle={() => toggle(s.n)} />)}
                  </ul>
                )}
                {r.sources.length > 8 && (
                  <button type="button" onClick={() => setShowAll((v) => !v)} className="mt-2 w-full rounded-md py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50">
                    {showAll ? 'Show fewer' : `Show all ${r.sources.length} sources`}
                  </button>
                )}
              </div>
            </Card>
          </div>
        </div>
      </div>
    </CiteContext.Provider>
  )
}

