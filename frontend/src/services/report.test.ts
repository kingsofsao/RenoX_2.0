// MOCKED unit tests: no network. Investigation payloads are hand-built; HTTP is a stub adapter.
import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios'
import { afterEach, describe, expect, it } from 'vitest'
import { ApiError, http, pollInvestigation } from './api'
import { buildMarkdownExport, plain, reportFilename, splitCitations } from './report'
import type { Investigation } from '../types/api'

const P1 = 'p_aaaaaaaaaaa1'
const P2 = 'p_bbbbbbbbbbb2'

function sampleInvestigation(overrides: Partial<Investigation> = {}): Investigation {
  return {
    id: 'inv_0123456789ab', project_id: 'default', question: 'Do GAT models generalize to unseen proteins?', status: 'completed', mode: 'offline',
    llm_configured: false, provider: null, model: null, requirements: null, created_at: '2026-10-15T04:00:00+00:00', started_at: '2026-10-15T04:00:00+00:00',
    finished_at: '2026-10-15T04:00:04+00:00', duration_seconds: 4.2, progress: [], error: null,
    result: {
      mode: 'offline', evidence_found: true, summary: 'Evidence is mixed [1], [2].', inferences: [], open_questions: [],
      report_markdown: '# Investigation: q\n\n## Answer\nEvidence is mixed [1].\n\n## References\n\n1. *A*, p. 2',
      findings: [{ type: 'finding', text: 'GAT generalizes well.', paper_id: P1, paper_title: 'Paper A', year: 2024, page: 2, relevance: 0.9, citations: [1] }],
      comparisons: [{ kind: 'contradiction', score: 0.81, note: 'Opposing results.',
        a: { text: 'GAT generalizes well.', paper_id: P1, paper_title: 'Paper A', page: 2, citation: 1 },
        b: { text: 'Graph models do not generalize.', paper_id: P2, paper_title: 'Paper B', page: 1, citation: 2 } }],
      method_comparison: [{ entity: 'Graph Attention Network', type: 'method', papers: [{ paper_id: P1, paper_title: 'Paper A', citation: 1 }] }],
      gaps: [{ id: 'G1', title: 'Cold-start proteins untested', type: 'recurring_limitation', rationale: 'Two papers.', score: 0.7, status: 'candidate',
        evidence: [{ citation: 2, paper_id: P2, paper_title: 'Paper B', page: 1, quote: 'not covered' }], citations: [2], note: 'Hypothesis.', support_papers: 2 }],
      limitations: [{ text: 'No cold-start split.', kind: 'limitation', paper_id: P1, paper_title: 'Paper A', page: 3, citations: [1] }],
      confidence: { level: 'moderate', reasons: ['2 verified passages.'], uncertainties: ['Papers disagree.'], narrative: null },
      sources: [
        { n: 1, chunk_id: `${P1}:c004`, paper_id: P1, paper_title: 'Paper A', year: 2024, page: 2, section: 'Results', quote: 'GAT generalizes well.', cited_in_report: true },
        { n: 2, chunk_id: `${P2}:c002`, paper_id: P2, paper_title: 'Paper B', year: 2023, page: 1, section: null, quote: 'Graph models do not generalize.', cited_in_report: false },
      ],
      papers: [{ paper_id: P1, title: 'Paper A', year: 2024, sources: 1 }, { paper_id: P2, title: 'Paper B', year: 2023, sources: 1 }],
      steps: [{ tool: 'search_evidence', args: {}, summary: '5 passages from 3 papers', source: 'agent', ok: true }],
      warnings: [],
    },
    ...overrides,
  }
}

describe('splitCitations', () => {
  it('splits single, grouped and unverified citations', () => {
    expect(splitCitations('A [1] and B [2, 3] or C [unverified].')).toEqual([
      { kind: 'text', text: 'A ' }, { kind: 'cite', numbers: [1], unverified: false, requirement: false },
      { kind: 'text', text: ' and B ' }, { kind: 'cite', numbers: [2, 3], unverified: false, requirement: false },
      { kind: 'text', text: ' or C ' }, { kind: 'cite', numbers: [], unverified: true, requirement: false }, { kind: 'text', text: '.' },
    ])
  })
  it('recognises requirement citations and quote flags', () => {
    expect(splitCitations('Needs X [R] per [4, R]. "Made up" [quote not found in sources]')).toEqual([
      { kind: 'text', text: 'Needs X ' }, { kind: 'cite', numbers: [], unverified: false, requirement: true },
      { kind: 'text', text: ' per ' }, { kind: 'cite', numbers: [4], unverified: false, requirement: true },
      { kind: 'text', text: '. "Made up" ' }, { kind: 'flag', text: 'quote not found in sources' },
    ])
  })
  it('leaves ordinary brackets alone', () => {
    expect(splitCitations('range [a, b] here')).toEqual([{ kind: 'text', text: 'range [a, b] here' }])
  })
  it('strips emphasis', () => {
    expect(plain('**bold** and *it* and `code`')).toBe('bold and it and code')
  })
})

describe('buildMarkdownExport', () => {
  it('contains every section with numbered page-level sources', () => {
    const md = buildMarkdownExport(sampleInvestigation())
    for (const h of ['# Investigation:', '## Summary', '## Evidence-backed findings', '## Cross-paper comparisons', '## Candidate research gaps',
      '## Limitations of the evidence', '## Confidence and uncertainty', '## Narrative report', '## Sources', '## Investigation trace']) {
      expect(md).toContain(h)
    }
    expect(md).toContain('1. *Paper A* (2024), p. 2, Results — "GAT generalizes well." `p_aaaaaaaaaaa1:c004`')
    expect(md).toContain('not claims of novelty')
    expect(md).toContain('**Confidence: moderate**')
    // The agent's own References section is replaced by the Sources list (same numbering)
    expect(md.match(/## References/g)).toBeNull()
  })
  it('exports failed investigations with the error', () => {
    const md = buildMarkdownExport(sampleInvestigation({ status: 'failed', result: null, error: { code: 'investigation_failed', message: 'Boom.' } }))
    expect(md).toContain('## Error')
    expect(md).toContain('Boom.')
  })
  it('builds a safe filename', () => {
    expect(reportFilename({ question: 'Do GAT models / generalize?', created_at: '2026-10-15T04:00:00Z' }))
      .toBe('researchmind-2026-10-15-do-gat-models-generalize.md')
  })
})

describe('pollInvestigation', () => {
  const original = http.defaults.adapter
  afterEach(() => { http.defaults.adapter = original })

  function stub(responses: { status: number; data: unknown }[]): AxiosAdapter {
    return async (config: InternalAxiosRequestConfig) => {
      const r = responses.shift()!
      const response = { status: r.status, statusText: '', headers: {}, config, data: r.data }
      if (r.status >= 400) {
        const { AxiosError } = await import('axios')
        throw new AxiosError('fail', 'ERR_BAD_RESPONSE', config, undefined, response)
      }
      return response
    }
  }

  it('polls until completed and reports each snapshot', async () => {
    const running = sampleInvestigation({ status: 'running', result: null })
    http.defaults.adapter = stub([{ status: 200, data: running }, { status: 503, data: {} }, { status: 200, data: sampleInvestigation() }])
    const seen: string[] = []
    const final = await pollInvestigation('inv_0123456789ab', (i) => seen.push(i.status), { intervalMs: 1 })
    expect(final.status).toBe('completed')
    expect(seen).toEqual(['running', 'completed']) // the transient 503 was retried
  })

  it('stops on 404', async () => {
    http.defaults.adapter = stub([{ status: 404, data: { error: { code: 'http_error', message: 'Investigation not found.' } } }])
    await expect(pollInvestigation('inv_0123456789ab', () => {}, { intervalMs: 1 })).rejects.toBeInstanceOf(ApiError)
  })
})
