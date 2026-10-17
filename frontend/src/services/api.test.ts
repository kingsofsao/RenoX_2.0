// MOCKED unit tests: no network. Axios errors are constructed by hand.
import { AxiosError, AxiosHeaders, type AxiosResponse } from 'axios'
import { describe, expect, it } from 'vitest'
import { ApiError, toApiError } from './api'
import { formatBytes, shortHash } from './format'

function axiosErrorWith(status: number, data: unknown): AxiosError {
  const response = { status, data, statusText: '', headers: {}, config: { headers: new AxiosHeaders() } } as AxiosResponse
  return new AxiosError('Request failed', 'ERR_BAD_RESPONSE', undefined, undefined, response)
}

describe('toApiError', () => {
  it('uses the API error envelope message and code', () => {
    const err = toApiError(axiosErrorWith(503, { error: { code: 'database_unavailable', message: 'The graph database is currently unavailable.' } }))
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(503)
    expect(err.code).toBe('database_unavailable')
    expect(err.message).toContain('graph database')
  })

  it('falls back to the HTTP status for non-JSON errors', () => {
    expect(toApiError(axiosErrorWith(502, '<html>Bad gateway</html>')).message).toBe('Request failed (HTTP 502).')
  })

  it('explains network failures', () => {
    const err = toApiError(new AxiosError('Network Error', 'ERR_NETWORK'))
    expect(err.code).toBe('network_error')
    expect(err.message).toMatch(/ResearchMind service/)
  })
})

describe('format helpers', () => {
  it('formats bytes', () => {
    expect(formatBytes(null)).toBe('—')
    expect(formatBytes(512)).toBe('512 B')
    expect(formatBytes(2048)).toBe('2.0 KB')
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB')
  })
  it('shortens hashes', () => {
    expect(shortHash('abcdef0123456789', 6)).toBe('abcdef…')
  })
})

describe('project scoping', () => {
  it('sends every data call to the active project', async () => {
    const { api, http, setActiveProject } = await import('./api')
    const seen: string[] = []
    const bodies: unknown[] = []
    const original = http.defaults.adapter
    http.defaults.adapter = async (config) => {
      seen.push(`${config.method} ${config.url}`)
      if (config.data) bodies.push(JSON.parse(config.data as string))
      return { status: 200, statusText: '', headers: {}, config, data: { papers: [], investigations: [], total: 0 } }
    }
    try {
      setActiveProject('prj_0123456789')
      await api.listPapers()
      await api.graphStats()
      await api.listInvestigations()
      await api.startInvestigation('A long enough question?', 'p_aaaaaaaaaaaa', { language: 'de' })
      expect(api.paperFileUrl('p_aaaaaaaaaaaa')).toContain('/api/projects/prj_0123456789/papers/p_aaaaaaaaaaaa/file')
      expect(seen).toEqual([
        'get /api/projects/prj_0123456789/papers',
        'get /api/projects/prj_0123456789/graph/stats',
        'get /api/projects/prj_0123456789/investigations',
        'post /api/projects/prj_0123456789/investigations',
      ])
      // exactly one paper and the UI language; there is no whole-library option
      expect(bodies[0]).toEqual({ question: 'A long enough question?', paper_id: 'p_aaaaaaaaaaaa', wait: false, requirements: null, language: 'de' })
    } finally {
      http.defaults.adapter = original
      setActiveProject('')
    }
  })
})

describe('security', () => {
  it('only redirects to same-site paths after sign-in', async () => {
    const { safeNext } = await import('../auth/redirect')
    expect(safeNext('?next=%2Finvestigate%3Fpaper%3Dp_1')).toBe('/investigate?paper=p_1')
    for (const evil of ['?next=https://evil.example', '?next=//evil.example', '?next=/%5Cevil.example', '?next=javascript:alert(1)', '']) {
      expect(safeNext(evil)).toBe('/')
    }
  })

  it('sends the CSRF cookie back as a header on state-changing requests only', async () => {
    const { http } = await import('./api')
    const headers: Record<string, unknown>[] = []
    const original = http.defaults.adapter
    const g = globalThis as { document?: { cookie: string } }
    const hadDocument = 'document' in g
    g.document = { cookie: 'other=1; rm_csrf=tok%2Den; x=y' }
    http.defaults.adapter = async (config) => {
      headers.push({ ...config.headers })
      return { status: 200, statusText: '', headers: {}, config, data: {} }
    }
    try {
      await http.get('/api/auth/me')
      await http.post('/api/projects', { name: 'x' })
      expect(headers[0]['X-CSRF-Token']).toBeUndefined()
      expect(headers[1]['X-CSRF-Token']).toBe('tok-en')
    } finally {
      http.defaults.adapter = original
      if (!hadDocument) delete g.document
    }
  })
})
