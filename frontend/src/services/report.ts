// Pure helpers for investigation reports: citation parsing and Markdown export.
import { en, type MessageKey } from '../i18n/en'
import type { Investigation } from '../types/api'

export type TextPart =
  | { kind: 'text'; text: string }
  | { kind: 'cite'; numbers: number[]; unverified: boolean; requirement: boolean }
  | { kind: 'flag'; text: string }

const CITE = /\[((?:\d+|unverified|R)(?:\s*,\s*(?:\d+|unverified|R))*)\]|\[(quote not found in sources|uncited claim|attribution not supported)\]/g

/** Split text containing [1], [2, 3], [R] (user requirement), [unverified] or quote flags into parts. */
export function splitCitations(text: string): TextPart[] {
  const parts: TextPart[] = []
  let last = 0
  for (const m of text.matchAll(CITE)) {
    if (m.index! > last) parts.push({ kind: 'text', text: text.slice(last, m.index) })
    if (m[2]) {
      parts.push({ kind: 'flag', text: m[2] })
    } else {
      const tokens = m[1].split(',').map((t) => t.trim())
      parts.push({
        kind: 'cite', numbers: tokens.filter((t) => /^\d+$/.test(t)).map(Number),
        unverified: tokens.includes('unverified'), requirement: tokens.includes('R'),
      })
    }
    last = m.index! + m[0].length
  }
  if (last < text.length) parts.push({ kind: 'text', text: text.slice(last) })
  return parts
}

/** Strip light Markdown emphasis for plain-text display. */
export function plain(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, '$1').replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, '$1$2').replace(/`([^`]+)`/g, '$1')
}

type T = (key: MessageKey, vars?: Record<string, string | number>) => string
/** English, for callers without the UI's translator (tests, scripts). */
export const englishT: T = (key, vars) =>
  (en[key] ?? key).replace(/\{(\w+)\}/g, (m, k: string) => (vars && k in vars ? String(vars[k]) : m))

const cites = (ns: number[]) => (ns.length ? ` [${ns.join(', ')}]` : '')
const oneLine = (s: string) => s.replace(/\s+/g, ' ').trim()

/** Remove the agent report's title and its References section (the export has its own Sources list). */
function narrativeBody(markdown: string): string {
  return markdown
    .replace(/^\s*#\s+[^\n]*\n+/, '')
    .replace(/\n## References\n[\s\S]*$/, '')
    .trim()
}

export function reportFilename(inv: Pick<Investigation, 'question' | 'created_at'>): string {
  const slug = inv.question.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 60) || 'investigation'
  return `researchmind-${inv.created_at.slice(0, 10)}-${slug}.md`
}

/** Full Markdown export of a completed investigation, with numbered, page-level sources, in the UI language. */
export function buildMarkdownExport(inv: Investigation, t: T = englishT): string {
  const r = inv.result
  const out: string[] = [`# ${t('export.title', { question: inv.question })}`, '']
  if (inv.paper_title || inv.paper_ids?.length) {
    out.push(`- **${t('export.paper')}:** ${inv.paper_title ?? ''}${inv.paper_ids?.length ? ` (\`${inv.paper_ids[0]}\`)` : ''}`)
  }
  if (r) out.push(`- **${t('export.mode')}:** ${r.mode === 'llm' ? t('export.mode.ai', { model: inv.model ?? 'AI' }) : t('result.report.offline')}`)
  out.push(`- **${t('export.started')}:** ${inv.started_at ?? inv.created_at}`)
  if (inv.duration_seconds != null) out.push(`- **${t('export.duration')}:** ${inv.duration_seconds.toFixed(1)} s`)
  if (r) out.push(`- **${t('result.confidence')}:** ${t(`confidence.${r.confidence.level}`)}`, `- **${t('export.evidence')}:** ${t('export.evidence.count', { count: r.sources.length })}`)
  out.push('', `> ${t('export.disclaimer')}`, '')

  if (!r) {
    out.push(`## ${t('export.error')}`, '', inv.error?.message ?? '—', '')
    return out.join('\n')
  }

  if (inv.requirements) out.push(`## ${t('investigate.requirements.yours')} [R]`, '', `_${t('export.requirements.note')}_`, '', inv.requirements, '')
  out.push(`## ${t('result.summary')}`, '', r.summary, '')

  out.push(`## ${t('result.findings')}`, '')
  if (!r.findings.length) out.push(`_${t('result.findings.none')}_`)
  for (const f of r.findings) {
    out.push(`- **${f.type === 'claim' ? t('result.claim') : t('result.finding')}** — ${oneLine(f.text)}${f.page ? ` (${t('result.page', { page: f.page })})` : ''}${cites(f.citations)}`)
  }
  out.push('')

  if (r.method_comparison.length) {
    out.push(`## ${t('result.entities')}`, '')
    for (const m of r.method_comparison) out.push(`- ${m.type === 'method' ? t('export.method') : t('export.dataset')}: ${m.entity}${cites(m.papers.map((p) => p.citation))}`)
    out.push('')
  }

  out.push(`## ${t('result.gaps')}`, '', `_${t('result.gaps.note')}_`, '')
  if (!r.gaps.length) out.push(`_${t('result.gaps.none')}_`, '')
  for (const g of r.gaps) {
    out.push(`### ${g.id}. ${oneLine(g.title)}`, '', `- ${g.rationale}${cites(g.citations)}`)
    for (const e of g.evidence) out.push(`- [${e.citation}] ${e.page ? `${t('result.page', { page: e.page })} — ` : ''}"${oneLine(e.quote)}"`)
    out.push('')
  }

  if (r.inferences.length) {
    out.push(`## ${t('result.hypotheses')}`, '')
    for (const x of r.inferences) out.push(`- ${oneLine(x.text)}`)
    out.push('')
  }
  if (r.open_questions.length) {
    out.push(`## ${t('result.openQuestions')}`, '')
    for (const q of r.open_questions) out.push(`- ${oneLine(q)}`)
    out.push('')
  }
  out.push(`## ${t('result.limitations')}`, '')
  if (!r.limitations.length) out.push(`_${t('result.limitations.none')}_`)
  for (const l of r.limitations) out.push(`- (${l.kind === 'future_work' ? t('result.futureWork') : t('result.limitation')}) ${oneLine(l.text)}${cites(l.citations)}`)
  out.push('')

  out.push(`## ${t('result.confidence')}`, '', `**${t('result.confidence')}: ${t(`confidence.${r.confidence.level}`)}**`, '')
  for (const x of r.confidence.reasons) out.push(`- ${x}`)
  for (const x of r.confidence.uncertainties) out.push(`- ⚠ ${x}`)
  if (r.confidence.narrative) out.push('', `${t('result.assessment')}: ${r.confidence.narrative}`)
  out.push('')

  if (r.warnings.length) {
    out.push(`## ${t('result.warnings')}`, '')
    for (const w of r.warnings) out.push(`- ${w}`)
    out.push('')
  }

  const narrative = narrativeBody(r.report_markdown)
  if (narrative) out.push(`## ${t('export.narrative')}`, '', narrative.replace(/^## /gm, '### '), '')

  out.push(`## ${t('export.sources')}`, '')
  for (const s of r.sources) {
    out.push(`${s.n}. *${s.paper_title ?? s.paper_id}*${s.year ? ` (${s.year})` : ''}${s.page ? `, ${t('result.page', { page: s.page })}` : ''}${s.section ? `, ${s.section}` : ''} — "${oneLine(s.quote)}" \`${s.chunk_id}\``)
  }
  out.push('')

  out.push(`## ${t('result.trace')}`, '')
  for (const st of r.steps) out.push(`- \`${st.tool}\`: ${st.summary}`)
  out.push('')
  return out.join('\n')
}

export function downloadText(filename: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' }))
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
