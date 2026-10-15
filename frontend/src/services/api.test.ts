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
    expect(err.message).toMatch(/backend/i)
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
    const original = http.defaults.adapter
    http.defaults.adapter = async (config) => {
      seen.push(`${config.method} ${config.url}`)
      return { status: 200, statusText: '', headers: {}, config, data: { papers: [], investigations: [], total: 0 } }
    }
    try {
      setActiveProject('prj_0123456789')
      await api.listPapers()
      await api.graphStats()
      await api.listInvestigations()
      await api.startInvestigation('A long enough question?')
      expect(api.paperFileUrl('p_aaaaaaaaaaaa')).toContain('/api/projects/prj_0123456789/papers/p_aaaaaaaaaaaa/file')
      expect(seen).toEqual([
        'get /api/projects/prj_0123456789/papers',
        'get /api/projects/prj_0123456789/graph/stats',
        'get /api/projects/prj_0123456789/investigations',
        'post /api/projects/prj_0123456789/investigations',
      ])
    } finally {
      http.defaults.adapter = original
      setActiveProject('default')
    }
  })
})
