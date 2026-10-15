import axios, { AxiosError } from 'axios'
import type {
  ApiErrorBody,
  GraphOverview,
  GraphStats,
  HealthResponse,
  Investigation,
  InvestigationSummary,
  LLMStatus,
  PaperDetailResponse,
  Project,
  PaperListResponse,
  PaperStatus,
  UploadResponse,
} from '../types/api'

// Empty base URL = same origin; the Vite dev/preview server proxies /api to FastAPI.
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? ''

export const http = axios.create({ baseURL: API_BASE_URL, timeout: 30_000 })

// Active project. Every paper, graph and investigation call is scoped to it via the URL;
// the backend resolves the project's own graph and folders, so data can never mix.
let activeProjectId = 'default'
export function setActiveProject(id: string) { activeProjectId = id }
export function getActiveProject(): string { return activeProjectId }
const scoped = (path: string) => `/api/projects/${encodeURIComponent(activeProjectId)}${path}`

/** Error with a user-presentable message, normalized from any axios failure. */
export class ApiError extends Error {
  readonly status: number | null
  readonly code: string

  constructor(message: string, status: number | null, code: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err
  if (axios.isAxiosError(err)) {
    const e = err as AxiosError<ApiErrorBody>
    const body = e.response?.data
    if (body && typeof body === 'object' && 'error' in body && body.error?.message) {
      return new ApiError(body.error.message, e.response?.status ?? null, body.error.code)
    }
    if (e.response) {
      return new ApiError(`Request failed (HTTP ${e.response.status}).`, e.response.status, 'http_error')
    }
    if (e.code === 'ECONNABORTED') return new ApiError('The request timed out.', null, 'timeout')
    return new ApiError('Cannot reach the ResearchMind API. Is the backend running on port 8000?', null, 'network_error')
  }
  return new ApiError(err instanceof Error ? err.message : 'Unexpected error.', null, 'unknown')
}

async function call<T>(fn: () => Promise<{ data: T }>): Promise<T> {
  try {
    return (await fn()).data
  } catch (err) {
    throw toApiError(err)
  }
}

export const api = {
  health: () => call(() => http.get<HealthResponse>('/api/health', { timeout: 20_000 })),

  listPapers: (params: { status?: PaperStatus; search?: string; limit?: number; offset?: number } = {}) =>
    call(() => http.get<PaperListResponse>(scoped('/papers'), { params })),

  getPaper: (id: string, page = 1, pageSize = 1) =>
    call(() => http.get<PaperDetailResponse>(scoped(`/papers/${encodeURIComponent(id)}`), { params: { page, page_size: pageSize } })),

  deletePaper: (id: string) => call(() => http.delete<void>(scoped(`/papers/${encodeURIComponent(id)}`))),

  paperFileUrl: (id: string) => `${API_BASE_URL}${scoped(`/papers/${encodeURIComponent(id)}/file`)}`,

  /** Upload PDFs. `onProgress` reports the byte transfer (0-100); server processing follows. */
  uploadPapers: (files: File[], onProgress?: (percent: number) => void) => {
    const form = new FormData()
    files.forEach((f) => form.append('files', f, f.name))
    return call(() =>
      http.post<UploadResponse>(scoped('/papers/upload'), form, {
        timeout: 10 * 60_000, // parsing + graph writes for large PDFs can take a while
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
        },
      }),
    )
  },

  graphStats: () => call(() => http.get<GraphStats>(scoped('/graph/stats'))),
  graphOverview: (limit = 60) => call(() => http.get<GraphOverview>(scoped('/graph/overview'), { params: { limit } })),

  /** Start an investigation in the background (202); poll `getInvestigation` for progress. */
  startInvestigation: (question: string, useLlm = true, requirements?: string) =>
    call(() => http.post<Investigation>(scoped('/investigations'), { question, wait: false, use_llm: useLlm, requirements: requirements || null })),
  llmStatus: () => call(() => http.get<LLMStatus>('/api/llm/status', { timeout: 10_000 })),
  getInvestigation: (id: string) =>
    call(() => http.get<Investigation>(scoped(`/investigations/${encodeURIComponent(id)}`), { timeout: 30_000 })),
  listInvestigations: (limit = 10, offset = 0) =>
    call(() => http.get<{ investigations: InvestigationSummary[]; total: number }>(scoped('/investigations'), { params: { limit, offset } })),
  deleteInvestigation: (id: string) => call(() => http.delete<void>(scoped(`/investigations/${encodeURIComponent(id)}`))),

  listProjects: () => call(() => http.get<{ projects: Project[] }>('/api/projects')),
  createProject: (name: string, description = '') => call(() => http.post<Project>('/api/projects', { name, description })),
  updateProject: (id: string, body: { name?: string; description?: string }) =>
    call(() => http.patch<Project>(`/api/projects/${encodeURIComponent(id)}`, body)),
  deleteProject: (id: string, confirmName: string) =>
    call(() => http.delete<void>(`/api/projects/${encodeURIComponent(id)}`, { data: { confirm_name: confirmName } })),
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => { clearTimeout(t); reject(new DOMException('Aborted', 'AbortError')) }, { once: true })
  })

/**
 * Poll an investigation until it completes or fails, reporting every snapshot.
 * Timeouts and network errors are retried (a local LLM can keep the backend busy for a while);
 * `onStall` reports consecutive failures so the UI can say it is still waiting.
 */
export async function pollInvestigation(
  id: string,
  onUpdate: (inv: Investigation) => void,
  { intervalMs = 1500, signal, maxErrors = 40, onStall }:
    { intervalMs?: number; signal?: AbortSignal; maxErrors?: number; onStall?: (failures: number) => void } = {},
): Promise<Investigation> {
  let errors = 0
  for (;;) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
    try {
      const inv = await api.getInvestigation(id)
      errors = 0
      onStall?.(0)
      onUpdate(inv)
      if (inv.status === 'completed' || inv.status === 'failed') return inv
    } catch (err) {
      const e = toApiError(err)
      if (e.status === 404 || ++errors >= maxErrors) throw e
      onStall?.(errors)
    }
    await sleep(intervalMs, signal)
  }
}
