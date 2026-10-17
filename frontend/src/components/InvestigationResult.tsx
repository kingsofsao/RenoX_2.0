// Rendering of a completed investigation: summary, findings, gaps, limitations, confidence and
// expandable page-level sources. Every [n] chip opens the matching source.
import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, BookOpen, ChevronDown, ChevronRight, ExternalLink, FileText, Lightbulb, ListChecks, Network, Scale, ShieldQuestion, Shapes,
} from 'lucide-react'
import { useI18n } from '../i18n/I18nProvider'
import type { MessageKey } from '../i18n/en'
import { api } from '../services/api'
import { plain, splitCitations } from '../services/report'
import type { InvestigationResultBody, InvestigationSource } from '../types/api'
import { Alert, Badge, Card, CardHeader, cx } from './ui'

// ------------------------------------------------------------------ citations

const CiteContext = createContext<(n: number) => void>(() => {})

export function CitationChip({ n }: { n: number }) {
  const { t } = useI18n()
  const focus = useContext(CiteContext)
  return (
    <button type="button" onClick={() => focus(n)} title={t('result.showSource', { n })}
      className="mx-0.5 inline-flex min-w-[1.5rem] items-center justify-center rounded bg-brand-soft px-1 align-baseline text-[11px] font-semibold tabular-nums text-brand-fg ring-1 ring-inset ring-brand/25 transition-all hover:bg-brand hover:text-white active:scale-90">
      {n}
    </button>
  )
}

function Cites({ numbers }: { numbers: number[] }) {
  return <>{numbers.map((n) => <CitationChip key={n} n={n} />)}</>
}

/** Text with inline [n] / [unverified] markers rendered as chips. */
export function CitedText({ text }: { text: string }) {
  const { t } = useI18n()
  return (
    <>
      {splitCitations(plain(text)).map((p, i) =>
        p.kind === 'text' ? <span key={i}>{p.text}</span>
          : p.kind === 'flag' ? (
            <span key={i} title={t('result.flag.title')} className="mx-0.5 rounded bg-bad-soft px-1 text-[11px] font-semibold text-bad-fg">{t('result.flag')}</span>
          ) : (
            <span key={i} className="whitespace-nowrap">
              {p.numbers.map((n) => <CitationChip key={n} n={n} />)}
              {p.requirement && (
                <span title={t('result.requirement.title')} className="mx-0.5 rounded bg-accent-soft px-1 text-[11px] font-semibold text-accent-fg">R</span>
              )}
              {p.unverified && (
                <span title={t('result.unverified.title')} className="mx-0.5 rounded bg-warn-soft px-1 text-[11px] font-semibold text-warn-fg">{t('result.unverified')}</span>
              )}
            </span>
          ),
      )}
    </>
  )
}

// The AI writes section headings in English (the server parses them); show them in the UI language.
const HEADINGS: Record<string, MessageKey> = {
  'answer': 'report.h.answer',
  'evidence': 'report.h.evidence',
  'evidence from the paper': 'report.h.evidence',
  'evidence from the papers': 'report.h.evidence',
  'methods, data and results': 'report.h.methods',
  'conflicts and uncertainty': 'report.h.conflicts',
  'agreements and conflicts': 'report.h.conflicts',
  'comparison': 'report.h.methods',
  'limitations of the evidence': 'report.h.limitations',
  'candidate research gaps': 'report.h.gaps',
  'not covered by the evidence': 'report.h.notCovered',
  'confidence': 'report.h.confidence',
}

/** Minimal Markdown rendering for reports: headings, bullets, quotes and paragraphs, with citation chips. */
export function MarkdownReport({ markdown }: { markdown: string }) {
  const { t } = useI18n()
  const body = markdown.replace(/^\s*#\s+[^\n]*\n+/, '').replace(/\n## References\n[\s\S]*$/, '')
  const blocks: ReactNode[] = []
  let list: string[] = []
  const flush = () => {
    if (list.length) {
      blocks.push(<ul key={`l${blocks.length}`} className="ms-5 list-disc space-y-1">{list.map((li, i) => <li key={i}><CitedText text={li} /></li>)}</ul>)
      list = []
    }
  }
  body.split('\n').forEach((raw, i) => {
    const line = raw.trimEnd()
    if (/^\s*[-*]\s+/.test(line)) { list.push(line.replace(/^\s*[-*]\s+/, '')); return }
    flush()
    if (!line.trim()) return
    // The server's provenance note (model, source count) is already shown, translated, in the result header.
    if (/^>\s*(LLM report generated|Generated in \*\*offline mode)/.test(line)) return
    const h = line.match(/^(#{2,4})\s+(.*)$/)
    if (h) {
      const heading = plain(h[2]).trim()
      const key = HEADINGS[heading.toLowerCase()]
      blocks.push(<h3 key={i} className={cx('font-semibold text-fg', h[1].length === 2 ? 'mt-6 text-base' : 'mt-3 text-sm')}>{key ? t(key) : heading}</h3>)
    } else if (line.startsWith('>')) {
      blocks.push(<p key={i} className="rounded-md bg-brand-soft px-3 py-2 text-xs text-brand-fg"><CitedText text={line.replace(/^>\s?/, '')} /></p>)
    } else {
      blocks.push(<p key={i} className={cx(/^hypothesis:/i.test(line) && 'border-s-2 border-accent ps-3 italic')}><CitedText text={line} /></p>)
    }
  })
  flush()
  return <div dir="auto" className="space-y-2 text-sm leading-relaxed text-fg-muted">{blocks}</div>
}

function PaperRef({ id, title, page }: { id: string; title: string | null; page: number | null }) {
  const { t } = useI18n()
  return (
    <span className="text-xs text-fg-subtle">
      <Link to={`/papers/${id}`} className="font-medium text-fg-muted hover:text-brand hover:underline">{title ?? id}</Link>
      {page ? <>, {t('result.page', { page })}</> : null}
    </span>
  )
}

function Section({ icon, title, subtitle, count, children, action }: {
  icon: ReactNode; title: string; subtitle?: string; count?: number; children: ReactNode; action?: ReactNode
}) {
  return (
    <Card className="animate-fade-up">
      <CardHeader
        title={`${title}${count != null ? ` (${count})` : ''}`}
        subtitle={subtitle}
        action={<div className="flex items-center gap-2">{action}<span className="rounded-lg bg-brand-soft p-1.5 text-brand">{icon}</span></div>}
      />
      <div className="p-5">{children}</div>
    </Card>
  )
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm italic text-fg-subtle">{children}</p>
}

// ------------------------------------------------------------------ sections

const LEVEL_TONE = { high: 'ok', moderate: 'warn', low: 'bad' } as const

export function ConfidenceBadge({ level }: { level: 'low' | 'moderate' | 'high' }) {
  const { t } = useI18n()
  return <Badge tone={LEVEL_TONE[level]} className="rounded-full px-2 text-xs">{t(`confidence.${level}`)}</Badge>
}

function Findings({ r }: { r: InvestigationResultBody }) {
  const { t } = useI18n()
  return (
    <Section icon={<ListChecks className="h-4 w-4" />} title={t('result.findings')} count={r.findings.length} subtitle={t('result.findings.subtitle')}>
      {!r.findings.length ? <Empty>{t('result.findings.none')}</Empty> : (
        <ul className="space-y-2.5">
          {r.findings.map((f, i) => (
            <li key={i} className="flex gap-2 text-sm text-fg">
              <Badge tone={f.type === 'claim' ? 'brand' : 'ok'} className="mt-0.5 h-fit shrink-0 uppercase">{f.type === 'claim' ? t('result.claim') : t('result.finding')}</Badge>
              <span dir="auto">
                {f.text}<Cites numbers={f.citations} />
                {f.page ? <span className="ms-1 text-xs text-fg-subtle">{t('result.page', { page: f.page })}</span> : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  )
}

function Entities({ r }: { r: InvestigationResultBody }) {
  const { t } = useI18n()
  if (!r.method_comparison.length) return null
  const groups = [['method', t('paper.methods')], ['dataset', t('paper.datasets')]] as const
  return (
    <Section icon={<Shapes className="h-4 w-4" />} title={t('result.entities')} subtitle={t('result.entities.subtitle')}>
      <div className="space-y-4">
        {groups.map(([type, label]) => {
          const items = r.method_comparison.filter((m) => m.type === type)
          if (!items.length) return null
          return (
            <div key={type}>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-fg-subtle">{label}</p>
              <div className="flex flex-wrap gap-1.5">
                {items.map((m) => (
                  <span key={m.entity} className="inline-flex items-center rounded-md bg-surface-3 px-2 py-1 text-xs text-fg">
                    {m.entity}{m.papers[0] && <CitationChip n={m.papers[0].citation} />}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </Section>
  )
}

function Gaps({ r }: { r: InvestigationResultBody }) {
  const { t } = useI18n()
  const [open, setOpen] = useState<Set<string>>(new Set())
  const toggle = (id: string) => setOpen((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n })
  return (
    <Section icon={<Lightbulb className="h-4 w-4" />} title={t('result.gaps')} count={r.gaps.length} subtitle={t('result.gaps.subtitle')}>
      {!r.gaps.length ? <Empty>{t('result.gaps.none')}</Empty> : (
        <div className="space-y-3">
          {r.gaps.map((g) => (
            <div key={g.id} className="rounded-lg border border-line p-4 transition-colors hover:border-line-strong">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="accent" className="uppercase">{g.id} · {t('result.candidate')}</Badge>
                <Badge>{g.type.replace(/_/g, ' ')}</Badge>
              </div>
              <p className="mt-2 font-medium text-fg" dir="auto">{g.title}</p>
              <p className="mt-1 text-sm text-fg-muted" dir="auto">{g.rationale}<Cites numbers={g.citations} /></p>
              <button type="button" onClick={() => toggle(g.id)} className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-brand hover:text-brand-hover">
                {open.has(g.id) ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5 rtl:rotate-180" />}
                {t('result.gaps.evidence', { count: g.evidence.length })}
              </button>
              {open.has(g.id) && (
                <ul className="mt-2 animate-fade-in space-y-2 border-s-2 border-accent/40 ps-3">
                  {g.evidence.map((e, i) => (
                    <li key={i} className="text-sm">
                      <p className="text-fg-muted" dir="auto">“{e.quote}”<CitationChip n={e.citation} /></p>
                      <PaperRef id={e.paper_id} title={e.paper_title} page={e.page} />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
          <p className="flex items-start gap-1.5 text-xs text-fg-subtle"><ShieldQuestion className="mt-0.5 h-3.5 w-3.5 shrink-0" />{t('result.gaps.note')}</p>
        </div>
      )}
    </Section>
  )
}

function Limitations({ r }: { r: InvestigationResultBody }) {
  const { t } = useI18n()
  return (
    <Section icon={<AlertTriangle className="h-4 w-4" />} title={t('result.limitations')} count={r.limitations.length} subtitle={t('result.limitations.subtitle')}>
      {!r.limitations.length ? <Empty>{t('result.limitations.none')}</Empty> : (
        <ul className="space-y-2.5">
          {r.limitations.map((l, i) => (
            <li key={i} className="text-sm text-fg" dir="auto">
              <Badge tone={l.kind === 'future_work' ? 'brand' : 'warn'} className="me-2 uppercase">{l.kind === 'future_work' ? t('result.futureWork') : t('result.limitation')}</Badge>
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
  const { t } = useI18n()
  const c = r.confidence
  return (
    <Section icon={<Scale className="h-4 w-4" />} title={t('result.confidence')} action={<ConfidenceBadge level={c.level} />}>
      <ul className="space-y-1.5 text-sm text-fg-muted">
        {c.reasons.map((x, i) => <li key={`r${i}`} className="flex gap-2"><span className="text-ok">•</span>{x}</li>)}
        {c.uncertainties.map((x, i) => <li key={`u${i}`} className="flex gap-2"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" />{x}</li>)}
      </ul>
      {c.narrative && (
        <div className="mt-4 rounded-lg bg-surface-2 p-3 text-sm text-fg-muted" dir="auto">
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-fg-subtle">{t('result.assessment')}</p>
          <CitedText text={c.narrative} />
        </div>
      )}
    </Section>
  )
}

function SourceItem({ s, open, onToggle }: { s: InvestigationSource; open: boolean; onToggle: () => void }) {
  const { t } = useI18n()
  return (
    <li id={`source-${s.n}`} className={cx('scroll-mt-24 rounded-lg border transition-colors', open ? 'border-brand/40 bg-brand-soft/40' : 'border-line hover:border-line-strong')}>
      <button type="button" onClick={onToggle} className="flex w-full items-start gap-3 px-3 py-2.5 text-start" aria-expanded={open}>
        <span className="mt-0.5 inline-flex h-5 min-w-[1.5rem] items-center justify-center rounded bg-brand px-1 text-[11px] font-semibold text-white">{s.n}</span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-fg">{s.paper_title ?? s.paper_id}</span>
          <span className="text-xs text-fg-subtle">
            {s.page ? t('result.page', { page: s.page }) : t('result.pageUnknown')}{s.section ? ` · ${s.section}` : ''}{s.cited_in_report ? ` · ${t('result.cited')}` : ''}
          </span>
        </span>
        {open ? <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-fg-subtle" /> : <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-fg-subtle rtl:rotate-180" />}
      </button>
      {open && (
        <div className="animate-fade-in space-y-2 px-3 pb-3 ps-12">
          <blockquote className="border-s-2 border-brand/40 ps-3 text-sm text-fg-muted" dir="auto">“{s.quote}”</blockquote>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <Link to={`/papers/${s.paper_id}`} className="inline-flex items-center gap-1 font-medium text-brand hover:text-brand-hover"><BookOpen className="h-3.5 w-3.5" /> {t('result.paperDetails')}</Link>
            <a href={`${api.paperFileUrl(s.paper_id)}${s.page ? `#page=${s.page}` : ''}`} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 font-medium text-brand hover:text-brand-hover">
              <ExternalLink className="h-3.5 w-3.5" /> {s.page ? t('result.openPdfAt', { page: s.page }) : t('paper.openPdf')}
            </a>
            <code className="text-fg-subtle" title={t('result.chunkId')}>{s.chunk_id}</code>
          </div>
        </div>
      )}
    </li>
  )
}

// ------------------------------------------------------------------ main view

export function InvestigationResultView({ result: r, model }: { result: InvestigationResultBody; model?: string | null }) {
  const { t } = useI18n()
  const [openSources, setOpenSources] = useState<Set<number>>(new Set())
  const [showAll, setShowAll] = useState(false)
  const [showReport, setShowReport] = useState(r.mode === 'llm')
  const [showTrace, setShowTrace] = useState(false)

  const focus = useCallback((n: number) => {
    setShowAll(true)
    setOpenSources((s) => new Set(s).add(n))
    requestAnimationFrame(() => document.getElementById(`source-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  }, [])
  const toggle = (n: number) => setOpenSources((s) => { const x = new Set(s); if (x.has(n)) x.delete(n); else x.add(n); return x })
  const visibleSources = showAll ? r.sources : r.sources.slice(0, 8)

  if (!r.evidence_found) {
    return (
      <Card className="animate-fade-up">
        <div className="flex flex-col items-center px-6 py-12 text-center">
          <div className="mb-3 rounded-2xl bg-warn-soft p-3 text-warn"><ShieldQuestion className="h-6 w-6" /></div>
          <p className="font-medium text-fg">{t('result.noEvidence.title')}</p>
          <p className="mt-1 max-w-md text-sm text-fg-muted">{t('result.noEvidence.text')}</p>
        </div>
      </Card>
    )
  }

  return (
    <CiteContext.Provider value={focus}>
      <div className="space-y-6">
        {r.warnings.length > 0 && (
          <Alert tone="warning" title={t('result.warnings')}>
            <ul className="list-disc space-y-0.5 ps-4">{r.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
          </Alert>
        )}

        <Card className="animate-fade-up overflow-hidden border-brand/25">
          <div className="h-1 bg-gradient-to-r from-brand via-brand-strong to-transparent" />
          <CardHeader title={t('result.summary')} subtitle={t('result.summary.subtitle', { sources: r.sources.length })}
            action={<ConfidenceBadge level={r.confidence.level} />} />
          <div className="space-y-2 p-5 text-[15px] leading-relaxed text-fg" dir="auto">
            {r.summary.split('\n').filter((l) => l.trim()).map((line, i) => (
              <p key={i} className={cx(line.trim().startsWith('- ') && 'ps-3')}><CitedText text={line.replace(/^\s*-\s+/, '• ')} /></p>
            ))}
          </div>
        </Card>

        <div className="grid gap-6 xl:grid-cols-3">
          <div className="space-y-6 xl:col-span-2">
            <Card className="animate-fade-up">
              <button type="button" onClick={() => setShowReport((v) => !v)} className="flex w-full items-center justify-between px-5 py-4 text-start">
                <span className="flex items-center gap-2 text-sm font-semibold text-fg">
                  <FileText className="h-4 w-4 text-brand" />
                  {r.mode === 'llm' ? t('result.report.ai', { model: model ?? 'AI' }) : t('result.report.offline')}
                </span>
                {showReport ? <ChevronDown className="h-4 w-4 text-fg-subtle" /> : <ChevronRight className="h-4 w-4 text-fg-subtle rtl:rotate-180" />}
              </button>
              {showReport && (
                <div className="max-h-[75vh] animate-fade-in overflow-auto border-t border-line p-5"><MarkdownReport markdown={r.report_markdown} /></div>
              )}
            </Card>
            <Findings r={r} />
            <Entities r={r} />
            <Gaps r={r} />
            {(r.inferences.length > 0 || r.open_questions.length > 0) && (
              <Section icon={<ShieldQuestion className="h-4 w-4" />} title={t('result.inferences')} subtitle={t('result.inferences.subtitle')}>
                <div className="space-y-4 text-sm">
                  {r.inferences.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-accent-fg">{t('result.hypotheses')}</p>
                      <ul className="space-y-1.5">{r.inferences.map((x, i) => <li key={i} className="border-s-2 border-accent ps-3 italic text-fg-muted" dir="auto"><CitedText text={x.text} /></li>)}</ul>
                    </div>
                  )}
                  {r.open_questions.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-warn-fg">{t('result.openQuestions')}</p>
                      <ul className="list-disc space-y-1 ps-5 text-fg-muted" dir="auto">{r.open_questions.map((q, i) => <li key={i}>{q}</li>)}</ul>
                    </div>
                  )}
                </div>
              </Section>
            )}
            <Limitations r={r} />
            <ConfidencePanel r={r} />
            <Card>
              <button type="button" onClick={() => setShowTrace((v) => !v)} className="flex w-full items-center justify-between px-5 py-4 text-start">
                <span>
                  <span className="flex items-center gap-2 text-sm font-semibold text-fg"><Network className="h-4 w-4 text-brand" />{t('result.trace')}</span>
                  <span className="mt-0.5 block text-xs text-fg-muted">{t('result.trace.subtitle', { count: r.steps.length })}</span>
                </span>
                {showTrace ? <ChevronDown className="h-4 w-4 text-fg-subtle" /> : <ChevronRight className="h-4 w-4 text-fg-subtle rtl:rotate-180" />}
              </button>
              {showTrace && (
                <ol className="animate-fade-in space-y-1.5 border-t border-line p-4 text-xs" dir="ltr">
                  {r.steps.map((st, i) => (
                    <li key={i} className="flex gap-2">
                      <Network className={cx('mt-0.5 h-3.5 w-3.5 shrink-0', st.ok ? 'text-brand' : 'text-bad')} />
                      <span className="min-w-0">
                        <code className="font-semibold text-fg">{st.tool}</code>
                        <span className={cx('block', st.ok ? 'text-fg-subtle' : 'text-bad-fg')}>{st.summary}</span>
                      </span>
                    </li>
                  ))}
                </ol>
              )}
            </Card>
          </div>

          <div>
            <Card className="xl:sticky xl:top-6">
              <CardHeader title={t('result.sources', { count: r.sources.length })} subtitle={t('result.sources.subtitle')} />
              <div className="max-h-[70vh] overflow-y-auto p-3">
                {!r.sources.length ? <Empty>{t('result.sources.none')}</Empty> : (
                  <ul className="space-y-2">
                    {visibleSources.map((s) => <SourceItem key={s.n} s={s} open={openSources.has(s.n)} onToggle={() => toggle(s.n)} />)}
                  </ul>
                )}
                {r.sources.length > 8 && (
                  <button type="button" onClick={() => setShowAll((v) => !v)} className="mt-2 w-full rounded-md py-1.5 text-xs font-medium text-brand transition-colors hover:bg-brand-soft">
                    {showAll ? t('common.showFewer') : t('result.sources.all', { count: r.sources.length })}
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
